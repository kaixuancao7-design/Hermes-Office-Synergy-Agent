"""技能步骤执行器 — 按顺序执行技能的每个步骤并生成最终回复

核心设计：
1. 遍历 Skill.steps，对每一步判断 action 是"工具调用"还是"语义LLM动作"
2. 工具调用 → tool_executor.execute(action, params)，包装在 run_in_executor 中
3. LLM动作 → call_model(prompt)，将 instruction + 累积上下文传给 LLM
4. 每步结果追加到累积上下文中，供后续步骤使用
5. 全部步骤完成后，通过 LLM 生成面向用户的最终回复
6. 捕获 ExecutionTrace 用于后续技能自学习管道

复用模式来自 react_engine.py:
  - 异步工具执行: loop.run_in_executor (react_engine.py:439)
  - 上下文累积: context += f"\n工具 [{tool_id}] 执行结果:\n{result}" (react_engine.py:278)
  - 最终回答: call_model(prompt) (react_engine.py:471-472)
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.types import Skill, SkillStep, ExecutionTrace, ToolCallRecord
from src.plugins import get_tool_executor
from src.plugins.model_routers import call_model
from src.config import settings
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger

logger = get_logger("engine")


@dataclass
class SkillExecutionResult:
    """技能执行结果（含渐进式披露信息）"""
    response: str                          # 面向用户的最终回复
    skill_id: str                          # 执行的技能 ID
    skill_name: str                        # 技能名称
    skill_type: str = ""                   # 技能类型（preset/custom/learned）
    match_score: float = 0.0               # 匹配置信度
    disclosure: str = ""                   # 预执行披露头（🔧 使用技能「xxx」...）
    step_progress: List[str] = field(default_factory=list)  # 逐步执行进度
    trace: Optional[ExecutionTrace] = None # 执行轨迹（供自学习管道使用）
    steps_executed: int = 0                # 成功执行的步骤数
    steps_failed: int = 0                  # 失败的步骤数
    step_results: List[Dict[str, Any]] = field(default_factory=list)


class SkillStepExecutor:
    """技能步骤执行器 — 按技能定义的步骤顺序执行工具/LLM调用

    用法:
        executor = SkillStepExecutor()
        result = await executor.execute_skill(skill, user_query, user_id)
        return result.response
    """

    # 预匹配阈值：高于 TriggerMatcher 默认的 0.3，确保高置信度匹配
    SKILL_MATCH_THRESHOLD = 0.5

    # 最大步骤数（防止无限循环）
    MAX_STEPS = 20

    # 单步超时（秒）
    STEP_TIMEOUT = 60

    # 技能类型中文标签
    TYPE_LABELS = {"preset": "预设", "custom": "自定义", "learned": "学习"}

    def __init__(self):
        self._tool_executor = None

    # =========================================================================
    # 渐进式披露：向用户展示技能执行过程
    # =========================================================================

    def build_disclosure(self, skill: Skill, score: float) -> str:
        """生成预执行披露头 — 告知用户匹配到了哪个技能"""
        type_label = self.TYPE_LABELS.get(skill.type, skill.type)
        return (
            f"🔧 使用技能「{skill.name}」({type_label}) — 共 {len(skill.steps)} 步\n"
            f"   置信度: {score*100:.0f}% | 版本: {skill.version}"
        )

    @staticmethod
    def build_footer(skill_name: str, skill_type: str, score: float) -> str:
        """生成执行后归因页脚 — 告知用户技能执行完成并提供控制选项"""
        type_labels = {"preset": "预设", "custom": "自定义", "learned": "学习"}
        type_label = type_labels.get(skill_type, skill_type)
        return (
            f"\n\n────────────────────\n"
            f"⚡ 技能: {skill_name} | 类型: {type_label} | "
            f"置信度: {score*100:.0f}%\n"
            f"💡 回复「不用技能」可直接对话 | 回复「技能列表」查看所有可用技能"
        )

    @staticmethod
    def build_near_miss_suggestion(near_misses) -> str:
        """为接近匹配（0.3-0.5 分）的技能生成建议文本"""
        if not near_misses:
            return ""
        skill, score = near_misses[0]
        desc = skill.description[:80] + ("..." if len(skill.description) > 80 else "")
        return (
            f"\n\n💡 您的问题可能适合使用「{skill.name}」技能"
            f"（{desc}）。\n"
            f"   回复「使用技能」即可调用该技能。"
        )

    def _load_reference_docs(self, skill: Skill) -> Dict[str, str]:
        """Tier 3: 按需加载技能参考文档

        从 skill.metadata.references 中读取文档路径列表，
        在技能执行前加载到内存中，供 LLM 步骤作为领域知识参考。

        skill.metadata 格式:
          {
            "references": [
              "docs/accounting_standards.md",
              "docs/financial_templates.json"
            ]
          }

        Returns:
            {filepath: content} 字典，加载失败的文档不包含在内
        """
        refs = skill.metadata.get("references", [])
        if not refs:
            return {}

        # 确保 references 是列表
        if not isinstance(refs, list):
            return {}

        ref_docs = {}
        for ref_path in refs:
            if not isinstance(ref_path, str):
                continue
            try:
                with open(ref_path, "r", encoding="utf-8") as f:
                    content = f.read()
                ref_docs[ref_path] = content
                logger.info(
                    f"[SKILL_EXEC:T3] Loaded reference doc | "
                    f"skill={skill.name} | path={ref_path} | "
                    f"size={len(content)} chars"
                )
            except FileNotFoundError:
                logger.warning(
                    f"[SKILL_EXEC:T3] Reference not found | "
                    f"skill={skill.name} | path={ref_path}"
                )
            except Exception as e:
                logger.warning(
                    f"[SKILL_EXEC:T3] Cannot load reference | "
                    f"skill={skill.name} | path={ref_path} | error={str(e)}"
                )

        if ref_docs:
            logger.info(
                f"[SKILL_EXEC:T3] Loaded {len(ref_docs)}/{len(refs)} reference docs "
                f"for skill={skill.name}"
            )

        return ref_docs

    def _get_tool_executor(self):
        """懒加载工具执行器，优先使用插件系统，失败则尝试直接实例化"""
        if self._tool_executor is not None:
            return self._tool_executor

        # 方式 1: 通过插件系统获取
        executor = get_tool_executor()
        if executor is not None:
            self._tool_executor = executor
            return self._tool_executor

        # 方式 2: 插件系统未初始化，尝试直接实例化 BasicToolExecutor
        try:
            from src.plugins.tool_executors import BasicToolExecutor
            self._tool_executor = BasicToolExecutor()
            logger.info("[SKILL_EXEC] Initialized BasicToolExecutor directly (plugin system unavailable)")
            return self._tool_executor
        except Exception as e:
            logger.warning(f"[SKILL_EXEC] Cannot initialize tool executor: {e}")

        return None

    # =========================================================================
    # 主入口
    # =========================================================================

    async def execute_skill(
        self,
        skill: Skill,
        query: str,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        match_score: float = 0.0,
    ) -> SkillExecutionResult:
        """执行技能的全部步骤并生成最终回复

        Args:
            skill: 要执行的技能对象
            query: 用户原始查询
            user_id: 用户 ID
            metadata: 附加元数据（file_key, message_id 等）
            match_score: 技能匹配置信度（用于渐进式披露）

        Returns:
            SkillExecutionResult: 包含最终回复、披露信息和执行轨迹
        """
        start_time = time.time()
        total_steps = len(skill.steps)
        logger.info(
            f"[SKILL_EXEC] Starting skill execution | skill={skill.name} | "
            f"steps={total_steps} | user_id={user_id} | score={match_score:.2f}"
        )

        # 生成预执行披露头
        disclosure = self.build_disclosure(skill, match_score or 1.0)

        # Tier 3: 按需加载参考文档（技能 metadata.references 中指定的文档路径）
        ref_docs = self._load_reference_docs(skill)

        # 累积上下文（初始值为用户查询）
        context = query
        if ref_docs:
            ref_summary = "\n\n".join(
                f"### 参考文档: {path}\n{content[:2000]}"
                for path, content in ref_docs.items()
            )
            context += f"\n\n## 参考文档（Tier 3 按需加载）:\n{ref_summary}"

        # 执行轨迹记录
        trace_records: List[ToolCallRecord] = []
        step_results: List[Dict[str, Any]] = []
        step_progress: List[str] = []
        steps_executed = 0
        steps_failed = 0

        # 按顺序执行每个步骤
        for i, step in enumerate(skill.steps):
            if i >= self.MAX_STEPS:
                logger.warning(f"[SKILL_EXEC] Reached MAX_STEPS={self.MAX_STEPS}, stopping")
                break

            step_start = time.time()
            step_id = step.id or f"step-{i}"
            action = step.action
            logger.info(
                f"[SKILL_EXEC] Step {i+1}/{len(skill.steps)} | "
                f"id={step_id} | action={action}"
            )

            try:
                # 判断 action 是工具调用还是语义 LLM 动作
                if self._is_tool_action(action):
                    result_text = await self._execute_tool_step(
                        step, context, user_id, metadata
                    )
                else:
                    result_text = await self._execute_llm_step(
                        step, context, query
                    )

                elapsed_ms = (time.time() - step_start) * 1000
                steps_executed += 1

                # 渐进式披露：记录步骤执行进度
                step_desc = step.description or step.action
                result_len = len(result_text)
                step_progress.append(
                    f"✅ 步骤 {i+1}/{total_steps}: {step_desc} "
                    f"— 完成 ({result_len} 字符)"
                )

                # 追加到累积上下文
                context += f"\n\n[Step {i+1}: {action}]\n{result_text}"

                step_results.append({
                    "step_id": step_id,
                    "action": action,
                    "success": True,
                    "elapsed_ms": elapsed_ms,
                    "result_length": result_len,
                })

                trace_records.append(ToolCallRecord(
                    tool_id=action,
                    parameters=step.parameters,
                    result=result_text[:500],  # 截断用于轨迹存储
                    success=True,
                    elapsed_ms=elapsed_ms,
                    step_index=i,
                ))

                logger.info(
                    f"[SKILL_EXEC] Step {i+1} OK | action={action} | "
                    f"elapsed={elapsed_ms:.0f}ms | result_len={len(result_text)}"
                )

                # 支持条件跳转: 如果步骤定义了 next_step_id，检查是否要跳过后续步骤
                if step.next_step_id and i + 1 < len(skill.steps):
                    next_step = skill.steps[i + 1]
                    if next_step.id != step.next_step_id:
                        logger.debug(
                            f"[SKILL_EXEC] Skipping to step {step.next_step_id} "
                            f"(current next is {next_step.id})"
                        )

            except asyncio.TimeoutError:
                elapsed_ms = (time.time() - step_start) * 1000
                steps_failed += 1
                error_msg = f"步骤执行超时（>{self.STEP_TIMEOUT}s）"
                step_desc = step.description or step.action
                step_progress.append(
                    f"⏱️ 步骤 {i+1}/{total_steps}: {step_desc} — 超时"
                )
                context += f"\n\n[Step {i+1}: {action} - 失败]\n{error_msg}"
                step_results.append({
                    "step_id": step_id, "action": action,
                    "success": False, "error": error_msg, "elapsed_ms": elapsed_ms,
                })
                logger.warning(f"[SKILL_EXEC] Step {i+1} TIMEOUT | action={action}")

            except Exception as e:
                elapsed_ms = (time.time() - step_start) * 1000
                steps_failed += 1
                error_msg = str(e)
                step_desc = step.description or step.action
                step_progress.append(
                    f"❌ 步骤 {i+1}/{total_steps}: {step_desc} — 失败"
                )
                context += f"\n\n[Step {i+1}: {action} - 失败]\n{error_msg}"
                step_results.append({
                    "step_id": step_id, "action": action,
                    "success": False, "error": error_msg, "elapsed_ms": elapsed_ms,
                })
                logger.error(
                    f"[SKILL_EXEC] Step {i+1} FAILED | action={action} | "
                    f"error={error_msg[:200]}"
                )

        # 生成最终回复
        total_elapsed = (time.time() - start_time) * 1000
        logger.info(
            f"[SKILL_EXEC] All steps done | skill={skill.name} | "
            f"executed={steps_executed} | failed={steps_failed} | "
            f"total_elapsed={total_elapsed:.0f}ms"
        )

        final_response = await self._generate_final_response(
            query=query,
            context=context,
            skill=skill,
            steps_executed=steps_executed,
            steps_failed=steps_failed,
            step_progress=step_progress,
        )

        # 构建执行轨迹
        trace = ExecutionTrace(
            trace_id=generate_id(),
            user_id=user_id,
            query=query,
            tool_sequence=trace_records,
            final_response=final_response,
            step_count=len(trace_records),
            mode="skill_driven",
            created_at=get_timestamp(),
        )

        return SkillExecutionResult(
            response=final_response,
            skill_id=skill.id,
            skill_name=skill.name,
            skill_type=skill.type,
            match_score=match_score or 1.0,
            disclosure=disclosure,
            step_progress=step_progress,
            trace=trace,
            steps_executed=steps_executed,
            steps_failed=steps_failed,
            step_results=step_results,
        )

    # =========================================================================
    # 工具 vs LLM 分发
    # =========================================================================

    # 已知工具 ID 硬编码列表（插件系统不可用时的回退）
    _KNOWN_TOOL_IDS = {
        "document_search", "memory_search", "web_search",
        "code_execution", "file_operations",
        "feishu_file_read", "generate_ppt", "generate_ppt_from_content",
        "ppt_template_match", "ppt_spec_lock", "ppt_generate_outline",
        "ppt_generate_content", "ppt_generate_file", "ppt_quality_check",
        "ppt_feishu_send", "ppt_context_store",
        "read_file",
    }

    def _is_tool_action(self, action: str) -> bool:
        """判断 action 是否是已注册的工具 ID

        双重检查策略:
          1. 先查硬编码的已知工具 ID 列表（覆盖所有标准工具，包括 PPT 和非 PPT）
          2. 再查运行时工具执行器的注册表（覆盖动态注册的工具）

        不在任何注册表中的 action（如 summarize, analyze, extract 等）
        被视为语义 LLM 动作。
        """
        # 优先使用硬编码列表（覆盖所有标准工具，不受插件初始化状态影响）
        if action in self._KNOWN_TOOL_IDS:
            return True

        # 补充检查运行时工具执行器（覆盖动态注册的工具）
        executor = self._get_tool_executor()
        if executor is not None:
            try:
                return action in executor.get_tools()
            except Exception:
                pass

        return False

    # =========================================================================
    # 工具步骤执行
    # =========================================================================

    async def _execute_tool_step(
        self,
        step: SkillStep,
        context: str,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """执行工具调用步骤

        包装同步 tool_executor.execute() 在 run_in_executor 中，
        遵循 react_engine.py:439 的相同模式。
        """
        executor = self._get_tool_executor()
        if executor is None:
            raise RuntimeError("工具执行器未初始化")

        # 构建工具参数: 合并步骤定义参数 + 用户/上下文信息
        params = self._build_tool_params(step, context, user_id, metadata)
        tool_id = step.action

        logger.debug(
            f"[SKILL_EXEC:TOOL] Calling tool | tool={tool_id} | "
            f"params_keys={list(params.keys())}"
        )

        try:
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: executor.execute(tool_id, params)),
                timeout=self.STEP_TIMEOUT,
            )
        except asyncio.TimeoutError:
            raise
        except Exception as e:
            logger.error(f"[SKILL_EXEC:TOOL] Tool execution error | tool={tool_id} | {e}")
            return f"工具执行失败: {str(e)}"

        # 提取结果文本
        if isinstance(result, dict):
            if result.get("success"):
                data = result.get("result", result.get("data", ""))
                if isinstance(data, str):
                    return data
                elif isinstance(data, (list, dict)):
                    # 序列化结构化结果为可读文本
                    return self._format_structured_result(data)
                return str(data)
            else:
                error = result.get("error", "未知错误")
                return f"工具返回错误: {error}"
        return str(result)

    def _build_tool_params(
        self,
        step: SkillStep,
        context: str,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """构建工具调用参数

        合并顺序:
          1. 步骤定义的 parameters（基础参数 + instruction）
          2. 动态注入 user_id, query（从上下文中提取）
          3. metadata 中的 file_key, message_id 等
        """
        params = dict(step.parameters) if step.parameters else {}

        # 注入用户 ID
        params.setdefault("user_id", user_id)

        # 根据工具类型注入动态参数
        tool_id = step.action

        # 搜索类工具: 从上下文提取搜索关键词
        if tool_id in ("document_search", "memory_search", "web_search"):
            if "query" not in params or not params["query"]:
                # 使用步骤的 instruction 作为搜索 query
                params["query"] = step.parameters.get("instruction", context[:200])

        # 文件操作: 注入路径和内容
        if tool_id == "file_operations":
            if "operation" not in params:
                params["operation"] = "read"

        # 飞书文件读取: 传递 file_key / message_id
        if tool_id == "feishu_file_read" and metadata:
            for key in ("file_key", "message_id", "file_name"):
                if key in metadata and key not in params:
                    params[key] = metadata[key]

        # 代码执行: 注入代码
        if tool_id == "code_execution":
            if "language" not in params:
                params["language"] = "python"

        return params

    def _format_structured_result(self, data) -> str:
        """将结构化结果（list/dict）格式化为可读文本"""
        import json
        try:
            if isinstance(data, list) and len(data) > 0:
                # 如果是 dict 列表，尝试提取关键字段
                if isinstance(data[0], dict):
                    lines = []
                    for i, item in enumerate(data[:10]):  # 最多10条
                        title = item.get("title", item.get("name", f"项目 {i+1}"))
                        summary = item.get("summary", item.get("content", ""))
                        if summary:
                            summary = str(summary)[:200]
                        lines.append(f"- **{title}**: {summary}")
                    if len(data) > 10:
                        lines.append(f"... 及其他 {len(data) - 10} 条结果")
                    return "\n".join(lines)
                return "\n".join(f"- {item}" for item in data[:20])
            elif isinstance(data, dict):
                return json.dumps(data, ensure_ascii=False, indent=2)
            return str(data)
        except Exception:
            return str(data)

    # =========================================================================
    # LLM 语义步骤执行
    # =========================================================================

    async def _execute_llm_step(
        self,
        step: SkillStep,
        context: str,
        query: str,
    ) -> str:
        """执行语义 LLM 步骤

        将步骤的 instruction + 累积上下文 + 用户原始查询组合成 prompt，
        调用 LLM 获取结果。
        """
        instruction = step.parameters.get("instruction", f"执行 {step.action} 操作")
        output_format = step.parameters.get("output_format", "")

        prompt_parts = [
            f"## 任务: {instruction}",
            f"## 操作类型: {step.action}",
        ]

        if output_format:
            prompt_parts.append(f"## 输出格式要求: {output_format}")

        prompt_parts.extend([
            f"## 已有上下文:\n{context[:4000]}",  # 限制上下文长度，避免超出 token 限制
            f"## 用户原始问题: {query}",
            "",
            "请根据以上上下文和任务要求，完成当前步骤并输出结果。",
        ])

        prompt = "\n\n".join(prompt_parts)

        logger.debug(
            f"[SKILL_EXEC:LLM] Calling LLM | action={step.action} | "
            f"instruction_len={len(instruction)} | context_len={len(context)}"
        )

        try:
            response = await asyncio.wait_for(
                call_model(prompt, settings.MODEL_ROUTER_TYPE),
                timeout=self.STEP_TIMEOUT,
            )
            if response and response.strip():
                return response.strip()
            return f"（{step.action} 步骤未生成输出）"
        except asyncio.TimeoutError:
            raise
        except Exception as e:
            logger.error(f"[SKILL_EXEC:LLM] LLM call failed | action={step.action} | {e}")
            return f"LLM 调用失败: {str(e)}"

    # =========================================================================
    # 最终回复生成
    # =========================================================================

    async def _generate_final_response(
        self,
        query: str,
        context: str,
        skill: Skill,
        steps_executed: int = 0,
        steps_failed: int = 0,
        step_progress: List[str] = None,
    ) -> str:
        """基于所有步骤的累积上下文生成面向用户的最终回复

        遵循 react_engine.py:467-478 的相同模式。
        包含步骤执行进度，让 LLM 了解完整的执行过程。
        """
        logger.info(
            f"[SKILL_EXEC:FINAL] Generating final response | "
            f"skill={skill.name} | context_len={len(context)}"
        )

        status_note = ""
        if steps_failed > 0:
            status_note = (
                f"\n（注意：{steps_failed} 个步骤执行失败，"
                f"以下回复基于 {steps_executed} 个成功步骤的结果）"
            )

        # 构建步骤进度摘要
        step_summary = ""
        if step_progress:
            step_summary = "## 步骤执行记录:\n" + "\n".join(step_progress) + "\n\n"

        prompt = (
            f"你是一个企业办公助手。你按照「{skill.name}」技能的工作流程执行了以下步骤。\n"
            f"技能描述: {skill.description}\n\n"
            f"{step_summary}"
            f"## 执行过程与结果:\n{context}\n\n"
            f"## 用户原始问题: {query}\n"
            f"{status_note}\n"
            f"请基于以上执行结果，给用户一个清晰、完整、专业的回复。"
            f"回复应直接回应用户的问题，引用执行过程中的关键发现和数据。"
        )

        try:
            response = await call_model(prompt, settings.MODEL_ROUTER_TYPE)
            if response and response.strip():
                return response.strip()
            return "根据技能流程分析，我已处理完您的请求。详细结果请见上述执行过程。"
        except Exception as e:
            logger.error(f"[SKILL_EXEC:FINAL] Final response generation failed | {e}")
            # 降级: 直接返回累积的上下文摘要
            if len(context) > 500:
                return (
                    f"已完成「{skill.name}」技能流程（{steps_executed} 个步骤），"
                    f"但由于模型暂时不可用，无法生成完整回复。以下是执行摘要：\n\n"
                    f"{context[:800]}..."
                )
            return f"已完成「{skill.name}」技能流程，但最终回复生成失败。请稍后重试。"

    # =========================================================================
    # 技能匹配辅助
    # =========================================================================

    def match_skill_for_query(self, query: str, user_id: str = None) -> Optional[Skill]:
        """检查是否有技能匹配用户查询（预匹配入口）

        使用 TriggerMatcher 进行技能匹配，阈值高于默认值，
        确保只有高置信度匹配才会触发自动执行。
        """
        try:
            from src.skills.triggers import trigger_matcher
        except ImportError:
            logger.warning("[SKILL_EXEC] TriggerMatcher not available")
            return None

        matched = trigger_matcher.find_relevant_skill(query, user_id)
        if matched is None:
            return None

        score = trigger_matcher._calculate_match_score(matched, query.lower())
        if score >= self.SKILL_MATCH_THRESHOLD:
            logger.info(
                f"[SKILL_EXEC] Skill matched | name={matched.name} | "
                f"score={score:.2f} | threshold={self.SKILL_MATCH_THRESHOLD}"
            )
            return matched

        logger.debug(
            f"[SKILL_EXEC] Skill scored below threshold | "
            f"name={matched.name} | score={score:.2f} < {self.SKILL_MATCH_THRESHOLD}"
        )
        return None


# 全局单例
skill_executor = SkillStepExecutor()
