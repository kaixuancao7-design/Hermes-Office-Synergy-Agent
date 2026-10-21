"""技能自动生成器 — 从复杂执行轨迹自动生成可复用技能

触发条件：ReAct 引擎完成一个任务且工具调用次数 >= TOOL_CALL_THRESHOLD
生成流程：成功轨迹 → LLM 结构化分析 → 待审核 SkillDraft（不写正式技能文件）
"""

import json
import re
from typing import Optional
from src.types import ExecutionTrace, SkillDraft, SkillStep
from src.data.database import db
from src.utils import generate_id, get_timestamp
from src.plugins.model_routers import call_model
from src.logging_config import get_logger

logger = get_logger("engine")

# 技能自动生成提示词
AUTO_SKILL_PROMPT = """你是一个智能办公助手，刚刚完成了一个复杂任务。请分析以下执行记录，生成一个可复用的技能定义。

## 用户查询
{query}

## 工具调用序列
{tool_sequence}

## 最终响应
{final_response}

## 要求
分析以上执行过程，提取出一个可复用的技能模式。请用 JSON 格式返回（只返回 JSON，不要任何其他文字）：

{{
  "skill_name": "技能名称（中文，语义化，如：财务报告自动生成）",
  "description": "技能描述（1-2句话，说明该技能的功能和适用场景）",
  "trigger_patterns": ["触发短语1", "触发短语2", ...]（5-10个中英文触发关键词/短语）,
  "steps": [
    {{
      "action": "步骤动作（如 analyze_input, web_search, document_search 等）",
      "parameters": {{"instruction": "该步骤的具体指令描述"}}
    }},
    ...
  ],
  "confidence": 0.0-1.0（你对这个技能质量的信心分数，0.5以下表示质量较低）
}}

注意：
1. steps 应该将工具调用序列泛化为可复用的步骤，而不是原样复制
2. trigger_patterns 应该包含中英文关键词，覆盖用户可能的不同表达方式
3. confidence 请根据任务复杂度、工具调用是否合理、结果是否完整来打分
4. 如果任务太简单（只是普通问答），可以返回 confidence < 0.3 表示不适合生成技能"""


class SkillAutoGenerator:
    """从执行轨迹自动生成技能

    在 ReAct 引擎完成任务后异步触发（asyncio.create_task），
    不阻塞用户响应。
    """

    TOOL_CALL_THRESHOLD = 5  # 工具调用 >= 此值才触发生成
    MIN_CONFIDENCE = 0.3     # LLM 置信度 < 此值不生成

    def should_trigger(self, trace: ExecutionTrace) -> bool:
        """判断是否应该为该轨迹生成技能"""
        return (
            trace.step_count >= self.TOOL_CALL_THRESHOLD
            and len(trace.tool_sequence) >= self.TOOL_CALL_THRESHOLD
            and bool(trace.final_response.strip())
            and all(call.success and call.result is not None for call in trace.tool_sequence)
        )

    # ========================================================================
    # 核心生成逻辑
    # ========================================================================

    async def generate_from_trace(self, trace: ExecutionTrace) -> Optional[str]:
        """从执行轨迹生成技能

        Args:
            trace: ReAct 引擎执行轨迹

        Returns:
            生成的 SkillDraft ID，失败时返回 None
        """
        if not self.should_trigger(trace):
            return None
        source_key = f"trace:{trace.user_id}:{trace.trace_id}"
        existing = db.get_learning_source(source_key)
        if existing:
            return existing
        logger.info(f"[AUTO_SKILL] Analyzing trace {trace.trace_id[:8]}..."
                     f" | tool_calls={len(trace.tool_sequence)}"
                     f" | mode={trace.mode}")

        try:
            # 1. 构建 LLM 提示词
            prompt = self._build_prompt(trace)

            # 2. 调用 LLM 生成技能定义
            llm_response = await call_model(prompt)
            if not llm_response or not llm_response.strip():
                logger.warning("[AUTO_SKILL] LLM returned empty response")
                return None

            # 3. 解析 LLM 响应
            skill_def = self._parse_llm_response(llm_response)
            if skill_def is None:
                # 重试一次
                logger.info("[AUTO_SKILL] First parse failed, retrying...")
                llm_response = await call_model(
                    prompt + "\n\n请只返回 JSON，不要任何其他内容。"
                )
                skill_def = self._parse_llm_response(llm_response)

            if skill_def is None:
                logger.warning("[AUTO_SKILL] Failed to parse LLM response after retry")
                return None

            # 4. 检查置信度
            import math
            confidence = float(skill_def.get("confidence", 0.0))
            if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                return None
            if confidence < self.MIN_CONFIDENCE:
                logger.info(f"[AUTO_SKILL] Confidence too low ({confidence:.2f}), skipping")
                return None

            # 5. 创建 SkillDraft
            draft = self._create_draft(trace, skill_def, confidence)
            from src.services.skill_verification import validate_definition
            validate_definition(draft)
            # Only drafts are persisted; reviewed publication owns filesystem export.
            return db.save_learning_draft(source_key, draft)

        except Exception as e:
            logger.error(f"[AUTO_SKILL] Generation failed: {e}", exc_info=True)
            return None

    # ========================================================================
    # 内部方法
    # ========================================================================

    def _build_prompt(self, trace: ExecutionTrace) -> str:
        """构建 LLM 提示词"""
        tool_lines = []
        for i, tc in enumerate(trace.tool_sequence, 1):
            params_summary = json.dumps(tc.parameters, ensure_ascii=False)[:200]
            result_summary = (tc.result or "")[:200]
            tool_lines.append(
                f"  {i}. tool={tc.tool_id}"
                f" | params={params_summary}"
                f" | result={result_summary}"
                f" | success={tc.success}"
            )

        return AUTO_SKILL_PROMPT.format(
            query=trace.query[:500],
            tool_sequence="\n".join(tool_lines) if tool_lines else "(none)",
            final_response=trace.final_response[:500],
        )

    @staticmethod
    def _parse_llm_response(response: str) -> Optional[dict]:
        """解析 LLM JSON 响应"""
        # 提取 JSON 块（去掉可能的前后文字）
        json_match = re.search(r'\{[^{}]*"skill_name"[^{}]*\}', response, re.DOTALL)
        if not json_match:
            # 尝试匹配任意 JSON 对象
            json_match = re.search(r'\{.*\}', response, re.DOTALL)

        if not json_match:
            return None

        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            return None

    def _create_draft(self, trace: ExecutionTrace, skill_def: dict,
                      confidence: float) -> SkillDraft:
        """从 LLM 输出创建 SkillDraft"""
        from src.types import SkillStep

        steps = [SkillStep.model_validate({**step, "id": step.get("id") or f"step-{index+1}"})
                 for index, step in enumerate(skill_def.get("steps", []))]

        status = "pending_review" if confidence >= 0.6 else "draft"

        return SkillDraft(
            id=generate_id(),
            skill_name=skill_def.get("skill_name", "Auto-Generated Skill"),
            description=skill_def.get("description", "Auto-generated from execution trace"),
            trigger_patterns=skill_def.get("trigger_patterns", []),
            steps=steps,
            original_context=trace.query,
            original_output="",
            corrected_output=trace.final_response,
            user_intent="auto_generated",
            user_id=trace.user_id,
            created_at=get_timestamp(),
            status=status,
            metadata={"source": "auto_generated", "source_trace_id": trace.trace_id, "confidence": confidence},
        )


# 全局实例
skill_auto_generator = SkillAutoGenerator()
