"""PPT工作流管理器 — 基于LangGraph StateGraph + interrupt()

图结构:
  __start__ → planning → confirm ←──────────┐
                            ↓ (是)            │ (详细/其他)
                          generate            │
                            ↓                 │
                       quality_check          │
                            ↓                 │
                          __end__             │
                                              │
                          confirm ←───────────┘ (通过条件边回环)

LangGraph 特性:
  - interrupt() 实现 human-in-the-loop（用户确认）
  - MemorySaver checkpoints 自动持久化状态（阶段4迁移到SqliteSaver）
  - 条件边实现确认回环，每次回环触发新的 interrupt()
"""

from typing import Dict, Any, List, Optional, Tuple, TypedDict

from src.logging_config import get_logger
from src.services.template_matcher import template_matcher
from src.engine.quality_gate import QualityGate
from src.engine.strategist_planner import StrategistPlanner
from src.tools.ppt_generator import PPTGeneratorBase

logger = get_logger("engine.ppt_workflow")


# ============================================================================
# LangGraph State
# ============================================================================

class PPTState(TypedDict, total=False):
    """PPT工作流状态"""
    user_id: str
    intent_type: str
    content: str
    document_content: str
    template_matches: List[Dict[str, Any]]
    selected_template: Optional[Dict[str, Any]]
    design_spec: Optional[Dict[str, Any]]
    slides: List[Dict[str, Any]]
    output_path: str
    quality_result: Optional[Dict[str, Any]]
    error_message: str
    final_message: str
    # 确认流程控制
    awaiting_confirmation: bool
    confirm_prompt: str
    user_response: str
    show_details: bool
    invalid_response: str


# ============================================================================
# PPTWorkflow — LangGraph 版本
# ============================================================================

class PPTWorkflow:
    """PPT工作流管理器 — 基于 LangGraph StateGraph"""

    def __init__(self):
        self._contexts: Dict[str, bool] = {}
        self._generator = PPTGeneratorBase()
        self._quality_gate = QualityGate(strict_mode=False)
        self._planner = StrategistPlanner()
        self._graph = self._build_graph()
        logger.info("[PPT_WORKFLOW] LangGraph PPT工作流初始化完成")

    # ========================================================================
    # 图构建
    # ========================================================================

    def _build_graph(self):
        """构建LangGraph StateGraph"""
        try:
            from langgraph.graph import StateGraph, START, END
            from src.engine.checkpointer import get_checkpointer

            graph = StateGraph(PPTState)

            graph.add_node("planning", self._planning_node)
            graph.add_node("confirm", self._confirm_node)
            graph.add_node("generate", self._generate_node)
            graph.add_node("quality_check", self._quality_check_node)

            graph.add_edge(START, "planning")
            graph.add_edge("planning", "confirm")

            # confirm → generate 或 confirm → confirm（回环重新确认）
            graph.add_conditional_edges(
                "confirm",
                self._route_after_confirm,
                {"generate": "generate", "confirm": "confirm"},
            )

            graph.add_edge("generate", "quality_check")
            graph.add_conditional_edges(
                "quality_check",
                self._route_after_quality,
                {"end": END},
            )

            return graph.compile(checkpointer=get_checkpointer())

        except ImportError:
            logger.warning("[PPT_WORKFLOW] langgraph未安装，工作流不可用")
            return None

    # ========================================================================
    # 图节点
    # ========================================================================

    def _planning_node(self, state: PPTState) -> PPTState:
        """规划节点 — 模板匹配 + 设计规格"""
        user_id = state.get("user_id", "")
        content = state.get("content", "")
        document_content = state.get("document_content", "")

        logger.info(f"[PPT_WORKFLOW] 规划阶段: user_id={user_id}")

        text_to_match = content or document_content
        matches = template_matcher.match_layout(text_to_match, style_hint=None)
        state["template_matches"] = [
            {"id": m.template_id, "name": m.name, "score": m.score,
             "description": m.description, "tags": m.tags}
            for m in matches
        ]

        if matches:
            best = matches[0]
            state["selected_template"] = {
                "template_id": best.template_id,
                "name": best.name,
                "score": best.score,
            }
            logger.info(f"[PPT_WORKFLOW] 模板匹配: {best.name}, score={best.score}")

            template_spec = template_matcher.get_template_by_id(best.template_id)
            if template_spec:
                state["design_spec"] = {
                    "canvas_format": template_spec.get("canvas", "16:9"),
                    "style": best.name,
                    "color_scheme": template_spec.get("color_scheme", {}),
                    "font_plan": template_spec.get("font_family", {}),
                    "template_id": best.template_id,
                    "template_name": best.name,
                }

        state["awaiting_confirmation"] = True
        state["confirm_prompt"] = self._build_planning_response(state)
        return state

    def _confirm_node(self, state: PPTState) -> PPTState:
        """确认节点 — interrupt() 等待用户

        每次进入本节点时调用 interrupt() 暂停图执行。
        用户响应后通过条件边决定下一步:
          - "是" → generate
          - "详细"/其他 → 回环到 confirm（重新 interrupt）
        """
        try:
            from langgraph.types import interrupt
        except ImportError:
            state["awaiting_confirmation"] = False
            return state

        # 构建提示消息
        if state.get("show_details"):
            prompt = self._planner.build_confirmation_message()
            state["show_details"] = False
        elif state.get("invalid_response"):
            prompt = (
                f"无法识别您的回复，请回复 `是` 开始生成PPT，"
                f"或回复 `详细` 查看自定义设置。"
            )
            state["invalid_response"] = ""
        else:
            prompt = state.get("confirm_prompt", "是否继续生成PPT？")

        logger.info(f"[PPT_WORKFLOW] 等待用户确认 | prompt={prompt[:50]}")

        user_decision = interrupt(prompt)
        state["user_response"] = str(user_decision) if user_decision else ""

        decision_lower = state["user_response"].lower().strip()
        logger.info(f"[PPT_WORKFLOW] 用户响应: {decision_lower}")

        if decision_lower in ("是", "yes", "y", "确认", "继续", "ok", "好"):
            state["awaiting_confirmation"] = False
            state["final_message"] = "正在生成PPT..."
            logger.info("[PPT_WORKFLOW] 用户确认，进入生成阶段")
        else:
            state["awaiting_confirmation"] = True
            if decision_lower in ("详细", "custom", "设置", "details", "more"):
                state["show_details"] = True
                state["invalid_response"] = ""
                logger.info("[PPT_WORKFLOW] 用户请求详细设置，回环")
            else:
                state["show_details"] = False
                state["invalid_response"] = state["user_response"]
                logger.info(f"[PPT_WORKFLOW] 无法识别用户输入: {decision_lower}，回环")

        return state

    def _generate_node(self, state: PPTState) -> PPTState:
        """生成节点 — 生成幻灯片并输出PPT文件"""
        user_id = state.get("user_id", "")
        content = state.get("content", "")
        document_content = state.get("document_content", "")
        selected_template = state.get("selected_template", {})

        logger.info(f"[PPT_WORKFLOW] 生成阶段: user_id={user_id}")

        slides = state.get("slides", [])
        if not slides:
            slides = self._generate_slides_from_content(content or document_content)

        if selected_template:
            try:
                slides = template_matcher.apply_template_style(
                    selected_template.get("template_id", ""), slides
                )
            except Exception:
                pass

        try:
            title = self._extract_title(content or document_content)
            output_path = self._generator.generate_ppt(title, slides)
            state["output_path"] = output_path
            state["slides"] = slides
            state["error_message"] = ""
            logger.info(f"[PPT_WORKFLOW] PPT生成成功: {output_path}")
        except Exception as e:
            state["error_message"] = str(e)
            state["output_path"] = ""
            logger.error(f"[PPT_WORKFLOW] PPT生成失败: {str(e)}")

        return state

    def _quality_check_node(self, state: PPTState) -> PPTState:
        """质量检查节点"""
        output_path = state.get("output_path", "")
        error_message = state.get("error_message", "")

        if error_message:
            state["final_message"] = f"PPT生成失败: {error_message}"
            return state

        logger.info(f"[PPT_WORKFLOW] 质量检查: {output_path}")
        quality_result = self._quality_gate.gate(output_path)

        if quality_result.passed:
            report = self._quality_gate.format_report(quality_result)
            state["final_message"] = (
                f"PPT生成完成\n\n{report}\n\n文件已保存: {output_path}"
            )
        elif quality_result.errors:
            report = self._quality_gate.format_report(quality_result)
            state["final_message"] = f"PPT质量检查未通过\n\n{report}"
        else:
            report = self._quality_gate.format_report(quality_result)
            state["final_message"] = (
                f"PPT生成完成(有警告)\n\n{report}\n\n文件已保存: {output_path}"
            )

        state["quality_result"] = {
            "passed": quality_result.passed,
            "errors": quality_result.errors,
            "warnings": getattr(quality_result, "warnings", []),
        }
        return state

    # ========================================================================
    # 条件路由
    # ========================================================================

    def _route_after_confirm(self, state: PPTState) -> str:
        """确认后的路由: 生成 或 回环重新确认"""
        if state.get("awaiting_confirmation", False):
            return "confirm"
        return "generate"

    def _route_after_quality(self, state: PPTState) -> str:
        """质量检查后总是结束"""
        return "end"

    # ========================================================================
    # 公开API — 与 message_router.py 完全兼容
    # ========================================================================

    def start_workflow(
        self,
        user_id: str,
        intent_type: str,
        content: str = "",
        document_content: str = "",
    ) -> Tuple[str, dict]:
        """启动PPT工作流。运行图直到 confirm 节点的 interrupt() 暂停。"""
        if self._graph is None:
            return "PPT工作流不可用（langgraph未安装）", {}

        self._contexts[user_id] = True

        initial_state: PPTState = {
            "user_id": user_id,
            "intent_type": intent_type,
            "content": content,
            "document_content": document_content,
            "template_matches": [],
            "selected_template": None,
            "design_spec": None,
            "slides": [],
            "output_path": "",
            "quality_result": None,
            "error_message": "",
            "final_message": "",
            "awaiting_confirmation": False,
            "confirm_prompt": "",
            "user_response": "",
            "show_details": False,
            "invalid_response": "",
        }

        logger.info(f"[PPT_WORKFLOW] 启动: user_id={user_id}, intent={intent_type}")

        config = {"configurable": {"thread_id": f"ppt_{user_id}"}}
        result = self._graph.invoke(initial_state, config)

        return result.get("final_message", ""), result

    def continue_workflow(
        self,
        user_id: str,
        user_response: str,
    ) -> Tuple[str, dict]:
        """继续工作流。用 Command(resume=...) 恢复 interrupt()。"""
        if self._graph is None:
            return "PPT工作流不可用", {}

        try:
            from langgraph.types import Command
        except ImportError:
            return "PPT工作流不可用", {}

        logger.info(f"[PPT_WORKFLOW] 继续: user_id={user_id}, response={user_response}")

        config = {"configurable": {"thread_id": f"ppt_{user_id}"}}
        result = self._graph.invoke(Command(resume=user_response), config)

        final_message = result.get("final_message", "")

        # 完成后清理
        if not result.get("awaiting_confirmation", False):
            self._contexts.pop(user_id, None)
            logger.info(f"[PPT_WORKFLOW] 完成: user_id={user_id}")

        return final_message, result

    def is_awaiting_confirmation(self, user_id: str) -> bool:
        """检查用户是否在 confirm 节点的 interrupt() 处等待"""
        if self._graph is None:
            return False

        try:
            config = {"configurable": {"thread_id": f"ppt_{user_id}"}}
            state = self._graph.get_state(config)
            if state is None:
                return False
            return state.next == ("confirm",) if state.next else False
        except Exception:
            return False

    def get_context(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取工作流当前状态"""
        if self._graph is None:
            return None
        try:
            config = {"configurable": {"thread_id": f"ppt_{user_id}"}}
            state = self._graph.get_state(config)
            return dict(state.values) if (state and state.values) else None
        except Exception:
            return None

    def get_state(self, user_id: str) -> str:
        """获取工作流状态字符串"""
        if self.is_awaiting_confirmation(user_id):
            return "awaiting_confirmation"
        ctx = self.get_context(user_id)
        if not ctx:
            return "idle"
        if ctx.get("error_message"):
            return "failed"
        if ctx.get("output_path"):
            return "completed"
        return "idle"

    # ========================================================================
    # 内部辅助
    # ========================================================================

    def _build_planning_response(self, state: PPTState) -> str:
        lines = ["**PPT生成准备中...**\n"]
        template_matches = state.get("template_matches", [])
        design_spec = state.get("design_spec")

        if template_matches:
            lines.append("**推荐模板：**\n")
            for i, m in enumerate(template_matches[:3], 1):
                lines.append(f"{i}. **{m.get('name', 'N/A')}** (匹配度: {m.get('score', 0):.1f})")
                desc = m.get("description", "")
                if desc:
                    lines.append(f"   - {desc}")
                tags = m.get("tags", [])
                if tags:
                    lines.append(f"   - 匹配: {', '.join(tags)}")
            lines.append("")

        if design_spec:
            lines.append("**设计规格：**\n")
            lines.append(f"- 画布: {design_spec.get('canvas_format', '16:9')}")
            lines.append(f"- 风格: {design_spec.get('style', 'N/A')}")
            color = design_spec.get("color_scheme", {})
            if color:
                lines.append(f"- 主色: {color.get('primary', 'N/A')}")
            lines.append("")

        lines.append("是否使用以上设置生成PPT？\n")
        lines.append("回复 `是` 继续，或回复 `详细` 进行自定义设置。")
        return "\n".join(lines)

    def _generate_slides_from_content(self, content: str) -> List[Dict[str, Any]]:
        slides = [{"type": "title", "title": self._extract_title(content), "content": ""}]
        for section in content.split("\n\n")[:8]:
            section = section.strip()
            if not section:
                continue
            lines = section.split("\n")
            slides.append({
                "type": "content",
                "title": lines[0][:50] if lines else "内容",
                "content": "\n".join(lines[1:]) if len(lines) > 1 else section,
            })
        slides.append({"type": "closing", "title": "谢谢", "content": ""})
        return slides

    def _extract_title(self, content: str) -> str:
        if not content:
            return "PPT演示"
        first_line = content.strip().split("\n")[0] if content else "PPT演示"
        return first_line[:47] + "..." if len(first_line) > 50 else first_line


# 全局实例
ppt_workflow = PPTWorkflow()
