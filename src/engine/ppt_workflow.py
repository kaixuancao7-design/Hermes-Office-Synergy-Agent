"""PPT工作流管理器 - 整合模板匹配、规格锁定、质量门控和策略规划"""

from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field

from src.logging_config import get_logger
from src.services.template_matcher import template_matcher, TemplateMatch
from src.engine.spec_lock import SpecLock, spec_lock_manager
from src.engine.quality_gate import QualityGate
from src.engine.strategist_planner import (
    StrategistPlanner,
    DesignSpec,
    ConfirmationStatus
)
from src.tools.ppt_generator import PPTGeneratorBase
from src.engine.mcp import mcp_manager, ContextType, ContextScope, ContextState

logger = get_logger("engine.ppt_workflow")


class WorkflowState(Enum):
    """工作流状态"""
    IDLE = "idle"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    PLANNING = "planning"
    OUTLINE_BUILDING = "outline_building"
    OUTLINE_CONFIRMING = "outline_confirming"
    GENERATING = "generating"
    QUALITY_CHECKING = "quality_checking"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PPTWorkflowContext:
    """PPT工作流上下文"""
    user_id: str
    intent_type: str
    content: str = ""
    document_content: str = ""
    template_matches: List[TemplateMatch] = field(default_factory=list)
    selected_template: Optional[TemplateMatch] = None
    design_spec: Optional[DesignSpec] = None
    spec_lock: Optional[SpecLock] = None
    slides: List[Dict[str, Any]] = field(default_factory=list)
    outline: List[Dict[str, Any]] = field(default_factory=list)
    output_path: str = ""
    quality_result: Any = None
    state: WorkflowState = WorkflowState.IDLE
    error_message: str = ""


class PPTWorkflow:
    """PPT工作流管理器 - 整合所有PPT生成相关组件"""

    def __init__(self):
        self._contexts: Dict[str, PPTWorkflowContext] = {}
        self._generator = PPTGeneratorBase()
        self._quality_gate = QualityGate(strict_mode=False)
        self._planner = StrategistPlanner()
        self._mcp_context_ids: Dict[str, str] = {}  # user_id -> mcp_context_id

    def _get_context(self, user_id: str) -> PPTWorkflowContext:
        """获取或创建用户的工作流上下文"""
        if user_id not in self._contexts:
            self._contexts[user_id] = PPTWorkflowContext(
                user_id=user_id,
                intent_type=""
            )
        return self._contexts[user_id]

    def _clear_context(self, user_id: str):
        """清除用户的工作流上下文"""
        if user_id in self._contexts:
            del self._contexts[user_id]
        if user_id in self._mcp_context_ids:
            del self._mcp_context_ids[user_id]

    def _update_mcp_context(self, user_id: str, ctx: PPTWorkflowContext):
        """更新MCP上下文状态"""
        mcp_ctx_id = self._mcp_context_ids.get(user_id)
        if not mcp_ctx_id:
            return

        mcp_ctx = mcp_manager.get_context(mcp_ctx_id)
        if not mcp_ctx:
            return

        mcp_ctx.set_data({
            "intent_type": ctx.intent_type,
            "content": ctx.content,
            "state": ctx.state.value if hasattr(ctx.state, 'value') else str(ctx.state),
            "slides_count": len(ctx.slides),
            "output_path": ctx.output_path,
            "error_message": ctx.error_message
        })

        if ctx.state == WorkflowState.COMPLETED:
            mcp_ctx.update_state(ContextState.COMPLETED)
        elif ctx.state == WorkflowState.FAILED:
            mcp_ctx.update_state(ContextState.FAILED)
        elif ctx.state == WorkflowState.AWAITING_CONFIRMATION:
            mcp_ctx.update_state(ContextState.PAUSED)
        elif ctx.state in {WorkflowState.IDLE, WorkflowState.PLANNING, WorkflowState.QUALITY_CHECKING, WorkflowState.GENERATING}:
            mcp_ctx.update_state(ContextState.ACTIVE)
        else:
            mcp_ctx.update_state(ContextState.ACTIVE)

    def start_workflow(
        self,
        user_id: str,
        intent_type: str,
        content: str = "",
        document_content: str = ""
    ) -> Tuple[str, PPTWorkflowContext]:
        """
        启动PPT工作流

        Args:
            user_id: 用户ID
            intent_type: 意图类型
            content: 用户原始内容/需求
            document_content: 文档内容

        Returns:
            (响应消息, 工作流上下文)
        """
        ctx = self._get_context(user_id)
        ctx.intent_type = intent_type
        ctx.content = content
        ctx.document_content = document_content

        # 创建MCP上下文
        mcp_ctx = mcp_manager.create_context(
            context_type=ContextType.PPT_WORKFLOW,
            scope=ContextScope.USER,
            user_id=user_id,
            initial_data={
                "intent_type": intent_type,
                "content": content,
                "state": ctx.state.value if hasattr(ctx.state, 'value') else str(ctx.state),
                "slides_count": 0,
                "output_path": ""
            }
        )
        self._mcp_context_ids[user_id] = mcp_ctx.get_metadata().context_id
        logger.info(f"[PPT_WORKFLOW] MCP上下文创建: {self._mcp_context_ids[user_id]}")

        logger.info(f"[PPT_WORKFLOW] 启动工作流: user_id={user_id}, intent={intent_type}")

        return self._process_state(ctx)

    def continue_workflow(
        self,
        user_id: str,
        user_response: str
    ) -> Tuple[str, PPTWorkflowContext]:
        """
        继续工作流（处理用户响应）

        Args:
            user_id: 用户ID
            user_response: 用户响应

        Returns:
            (响应消息, 工作流上下文)
        """
        ctx = self._get_context(user_id)

        if ctx.state == WorkflowState.AWAITING_CONFIRMATION:
            return self._handle_confirmation_response(ctx, user_response)

        if ctx.state == WorkflowState.OUTLINE_CONFIRMING:
            return self._handle_outline_confirmation_response(ctx, user_response)

        logger.warning(f"[PPT_WORKFLOW] 无需继续工作流: state={ctx.state}")
        return "工作流已完成或无需处理", ctx

    def _process_state(self, ctx: PPTWorkflowContext) -> Tuple[str, PPTWorkflowContext]:
        """根据当前状态处理工作流"""
        state_handlers = {
            WorkflowState.IDLE: self._handle_idle,
            WorkflowState.AWAITING_CONFIRMATION: self._handle_awaiting_confirmation,
            WorkflowState.PLANNING: self._handle_planning,
            WorkflowState.OUTLINE_BUILDING: self._handle_outline_building,
            WorkflowState.OUTLINE_CONFIRMING: self._handle_outline_confirming,
            WorkflowState.GENERATING: self._handle_generating,
            WorkflowState.QUALITY_CHECKING: self._handle_quality_checking,
        }

        handler = state_handlers.get(ctx.state, self._handle_idle)
        return handler(ctx)

    def _handle_idle(self, ctx: PPTWorkflowContext) -> Tuple[str, PPTWorkflowContext]:
        """处理空闲状态 - 开始工作流"""
        ctx.state = WorkflowState.PLANNING
        return self._handle_planning(ctx)

    def _handle_planning(self, ctx: PPTWorkflowContext) -> Tuple[str, PPTWorkflowContext]:
        """处理规划阶段 - 模板匹配"""
        logger.info(f"[PPT_WORKFLOW] 规划阶段: user_id={ctx.user_id}")

        matches = template_matcher.match_layout(
            ctx.content or ctx.document_content,
            style_hint=None
        )
        ctx.template_matches = matches

        if matches:
            ctx.selected_template = matches[0]
            logger.info(f"[PPT_WORKFLOW] 模板匹配: {matches[0].name}, score={matches[0].score}")

            template_spec = template_matcher.get_template_by_id(matches[0].template_id)
            if template_spec:
                spec_lock = SpecLock.from_template(matches[0].template_id, template_spec)
                ctx.spec_lock = spec_lock
                ctx.design_spec = DesignSpec(
                    canvas_format=template_spec.get("canvas", "16:9"),
                    style=matches[0].name,
                    color_scheme=template_spec.get("color_scheme", {}),
                    font_plan=template_spec.get("font_family", {}),
                    template_id=matches[0].template_id,
                    template_name=matches[0].name
                )

        response = self._build_planning_response(ctx)
        ctx.state = WorkflowState.AWAITING_CONFIRMATION
        self._update_mcp_context(ctx.user_id, ctx)
        return response, ctx

    def _build_planning_response(self, ctx: PPTWorkflowContext) -> str:
        """构建规划阶段响应"""
        lines = ["**PPT生成准备中...**\n"]

        if ctx.template_matches:
            lines.append("**推荐模板：**\n")
            for i, m in enumerate(ctx.template_matches[:3], 1):
                lines.append(f"{i}. **{m.name}** (匹配度: {m.score:.1f})")
                lines.append(f"   - {m.description}")
                if m.tags:
                    lines.append(f"   - 匹配: {', '.join(m.tags)}")
            lines.append("")

        if ctx.design_spec:
            spec = ctx.design_spec
            lines.append("**设计规格：**\n")
            lines.append(f"- 画布: {spec.canvas_format}")
            lines.append(f"- 风格: {spec.style}")
            if spec.color_scheme:
                lines.append(f"- 主色: {spec.color_scheme.get('primary', 'N/A')}")
            lines.append("")

        lines.append("是否使用以上设置生成PPT？\n")
        lines.append("回复 `是` 继续，或回复 `详细` 进行自定义设置。")

        return "\n".join(lines)

    def _handle_awaiting_confirmation(self, ctx: PPTWorkflowContext) -> Tuple[str, PPTWorkflowContext]:
        """处理等待确认状态"""
        confirmation_msg = self._planner.build_confirmation_message()
        return confirmation_msg, ctx

    def _handle_confirmation_response(
        self,
        ctx: PPTWorkflowContext,
        user_response: str
    ) -> Tuple[str, PPTWorkflowContext]:
        """处理用户确认响应"""
        logger.info(f"[PPT_WORKFLOW] 处理确认响应: {user_response}")

        if user_response.lower() in ["是", "yes", "y", "确认", "继续"]:
            ctx.state = WorkflowState.OUTLINE_BUILDING
            self._update_mcp_context(ctx.user_id, ctx)
            return self._handle_outline_building(ctx)

        if user_response.lower() in ["详细", "custom", "设置"]:
            ctx.state = WorkflowState.AWAITING_CONFIRMATION
            self._update_mcp_context(ctx.user_id, ctx)
            return self._handle_awaiting_confirmation(ctx)

        quick_confirm = self._planner.build_quick_confirmation()
        return quick_confirm, ctx

    def _handle_outline_building(self, ctx: PPTWorkflowContext) -> Tuple[str, PPTWorkflowContext]:
        """处理大纲构建阶段"""
        logger.info(f"[PPT_WORKFLOW] 大纲构建阶段: user_id={ctx.user_id}")

        ctx.outline = self._generate_outline_from_content(ctx)

        ctx.state = WorkflowState.OUTLINE_CONFIRMING
        self._update_mcp_context(ctx.user_id, ctx)

        response = self._build_outline_response(ctx)
        return response, ctx

    def _build_outline_response(self, ctx: PPTWorkflowContext) -> str:
        """构建大纲确认响应"""
        lines = ["**PPT大纲预览：**\n"]

        for i, section in enumerate(ctx.outline, 1):
            title = section.get("title", "")
            content = section.get("content", "")
            lines.append(f"**{i}. {title}**")
            if content:
                if isinstance(content, list):
                    for item in content[:3]:
                        lines.append(f"   - {item}")
                else:
                    lines.append(f"   {content[:100]}..." if len(str(content)) > 100 else f"   {content}")
            lines.append("")

        lines.append("---")
        lines.append("是否确认以上大纲？")
        lines.append("回复 `是` 继续生成PPT，")
        lines.append("回复 `修改+序号+新内容` 修改对应章节（如：`修改 2 新标题`），")
        lines.append("或回复 `重新生成` 重新生成大纲。")

        return "\n".join(lines)

    def _handle_outline_confirming(self, ctx: PPTWorkflowContext) -> Tuple[str, PPTWorkflowContext]:
        """处理大纲确认阶段"""
        confirmation_msg = self._planner.build_confirmation_message()
        return confirmation_msg, ctx

    def _handle_outline_confirmation_response(
        self,
        ctx: PPTWorkflowContext,
        user_response: str
    ) -> Tuple[str, PPTWorkflowContext]:
        """处理大纲确认响应"""
        logger.info(f"[PPT_WORKFLOW] 处理大纲确认响应: {user_response}")

        response_lower = user_response.lower().strip()

        if response_lower in ["是", "yes", "y", "确认", "确认大纲", "生成ppt", "生成"]:
            ctx.state = WorkflowState.GENERATING
            self._update_mcp_context(ctx.user_id, ctx)
            return self._handle_generating(ctx)

        if response_lower in ["重新生成", "regenerate", "重新生成大纲"]:
            ctx.state = WorkflowState.OUTLINE_BUILDING
            self._update_mcp_context(ctx.user_id, ctx)
            return self._handle_outline_building(ctx)

        if response_lower.startswith("修改 ") or response_lower.startswith("改 "):
            parts = user_response.split(" ", 2)
            if len(parts) >= 3:
                try:
                    idx = int(parts[1]) - 1
                    new_title = parts[2].strip()
                    if 0 <= idx < len(ctx.outline):
                        ctx.outline[idx]["title"] = new_title
                        logger.info(f"[PPT_WORKFLOW] 修改大纲第{idx+1}项为: {new_title}")
                except ValueError:
                    pass

            ctx.state = WorkflowState.OUTLINE_CONFIRMING
            self._update_mcp_context(ctx.user_id, ctx)
            response = self._build_outline_response(ctx)
            return response, ctx

        ctx.state = WorkflowState.OUTLINE_CONFIRMING
        self._update_mcp_context(ctx.user_id, ctx)
        response = self._build_outline_response(ctx)
        return response, ctx

    def _generate_outline_from_content(self, ctx: PPTWorkflowContext) -> List[Dict[str, Any]]:
        """从内容生成PPT大纲"""
        content = ctx.document_content or ctx.content
        sections = self._split_content_sections(content)

        outline = []
        for section in sections[:8]:
            section = section.strip()
            if not section:
                continue

            lines = section.split("\n")
            title = lines[0].strip() if lines else "内容"
            body = "\n".join(lines[1:]).strip() if len(lines) > 1 else section

            if len(title) < 2:
                continue

            outline.append({
                "title": title[:80],
                "content": body
            })

        return outline

    def _generate_slides_from_outline(self, ctx: PPTWorkflowContext) -> List[Dict[str, Any]]:
        """从大纲生成幻灯片结构"""
        slides = []

        title = self._extract_title(ctx.content or ctx.document_content)
        slides.append({
            "type": "title",
            "title": title,
            "content": ""
        })

        for section in ctx.outline:
            section_title = section.get("title", "")
            section_content = section.get("content", "")

            if not section_title or len(section_title) < 2:
                continue

            slides.append({
                "type": "content",
                "title": section_title,
                "content": section_content
            })

        slides.append({
            "type": "closing",
            "title": "谢谢观看",
            "content": ""
        })

        return slides

    def _handle_generating(self, ctx: PPTWorkflowContext) -> Tuple[str, PPTWorkflowContext]:
        """处理生成阶段"""
        logger.info(f"[PPT_WORKFLOW] 生成阶段: user_id={ctx.user_id}")

        ctx.state = WorkflowState.GENERATING
        self._update_mcp_context(ctx.user_id, ctx)

        if ctx.outline:
            ctx.slides = self._generate_slides_from_outline(ctx)
        elif not ctx.slides:
            ctx.slides = self._generate_slides_from_content(ctx)

        if ctx.spec_lock:
            styled_slides = template_matcher.apply_template_style(
                ctx.selected_template.template_id,
                ctx.slides
            )
        else:
            styled_slides = ctx.slides

        try:
            title = self._extract_title(ctx.content or ctx.document_content)
            output_path = self._generator.generate_ppt(title, styled_slides)
            ctx.output_path = output_path
            logger.info(f"[PPT_WORKFLOW] PPT生成成功: {output_path}")

            ctx.state = WorkflowState.QUALITY_CHECKING
            return self._handle_quality_checking(ctx)

        except Exception as e:
            logger.error(f"[PPT_WORKFLOW] PPT生成失败: {str(e)}")
            ctx.state = WorkflowState.FAILED
            ctx.error_message = str(e)
            self._update_mcp_context(ctx.user_id, ctx)
            return f"PPT生成失败: {str(e)}", ctx

    def _handle_quality_checking(self, ctx: PPTWorkflowContext) -> Tuple[str, PPTWorkflowContext]:
        """处理质量检查阶段"""
        logger.info(f"[PPT_WORKFLOW] 质量检查: {ctx.output_path}")

        ctx.state = WorkflowState.QUALITY_CHECKING

        quality_result = self._quality_gate.gate(ctx.output_path)

        if quality_result.passed:
            ctx.quality_result = quality_result
            ctx.state = WorkflowState.COMPLETED
            self._update_mcp_context(ctx.user_id, ctx)

            report = self._quality_gate.format_report(quality_result)
            return f"**PPT生成完成！**\n\n{report}\n\n文件已保存至: `{ctx.output_path}`", ctx

        if quality_result.errors:
            ctx.state = WorkflowState.FAILED
            report = self._quality_gate.format_report(quality_result)
            self._update_mcp_context(ctx.user_id, ctx)
            return f"**PPT质量检查未通过：**\n\n{report}", ctx

        ctx.quality_result = quality_result
        ctx.state = WorkflowState.COMPLETED
        self._update_mcp_context(ctx.user_id, ctx)
        report = self._quality_gate.format_report(quality_result)
        return f"**PPT生成完成（有警告）：**\n\n{report}\n\n文件已保存至: `{ctx.output_path}`", ctx

    def _generate_slides_from_content(self, ctx: PPTWorkflowContext) -> List[Dict[str, Any]]:
        """从内容生成幻灯片结构"""
        slides = []
        content = ctx.content or ctx.document_content

        title = self._extract_title(content)
        slides.append({
            "type": "title",
            "title": title,
            "content": ""
        })

        sections = self._split_content_sections(content)
        seen_titles = set()
        slide_count = 0

        for section in sections:
            if slide_count >= 10:
                break
            section = section.strip()
            if not section:
                continue

            lines = section.split("\n")
            slide_title = lines[0].strip() if lines else "内容"

            if len(slide_title) < 2:
                continue

            normalized_title = slide_title.lower()[:30]
            if normalized_title in seen_titles:
                continue
            seen_titles.add(normalized_title)

            slide_count += 1
            slides.append({
                "type": "content",
                "title": slide_title[:80],
                "content": "\n".join(lines[1:]).strip() if len(lines) > 1 else section
            })

        slides.append({
            "type": "closing",
            "title": "谢谢观看",
            "content": ""
        })

        return slides

    def _split_content_sections(self, content: str) -> List[str]:
        """智能分割内容为多个章节"""
        lines = content.split("\n")

        sections = []
        current_section = []
        in_section = False

        for line in lines:
            stripped = line.strip()

            if not stripped:
                if current_section:
                    current_section.append(stripped)
                continue

            is_main_header = (
                stripped.startswith("一、") or stripped.startswith("二、") or
                stripped.startswith("三、") or stripped.startswith("四、") or
                stripped.startswith("五、") or stripped.startswith("六、") or
                stripped.startswith("（一）") or stripped.startswith("（二）") or
                stripped.startswith("（三）")
            )

            if stripped.startswith("# ") or stripped.startswith("## ") or stripped.startswith("### "):
                if current_section:
                    sections.append("\n".join(current_section))
                    current_section = []
                current_section.append(stripped)
                in_section = True
            elif is_main_header:
                if current_section:
                    sections.append("\n".join(current_section))
                    current_section = []
                current_section.append(stripped)
                in_section = True
            else:
                current_section.append(stripped)

        if current_section:
            sections.append("\n".join(current_section))

        if not sections and content.strip():
            sections = [s.strip() for s in content.split("\n\n") if s.strip()]

        return [s for s in sections if s.strip()]

    def _extract_title(self, content: str) -> str:
        """从内容中提取标题"""
        if not content:
            return "PPT演示"

        lines = content.strip().split("\n")
        first_line = lines[0] if lines else "PPT演示"

        if len(first_line) > 50:
            first_line = first_line[:47] + "..."

        return first_line

    def get_context(self, user_id: str) -> Optional[PPTWorkflowContext]:
        """获取工作流上下文"""
        return self._contexts.get(user_id)

    def get_state(self, user_id: str) -> WorkflowState:
        """获取工作流状态"""
        ctx = self._contexts.get(user_id)
        return ctx.state if ctx else WorkflowState.IDLE

    def is_awaiting_confirmation(self, user_id: str) -> bool:
        """检查是否正在等待用户确认"""
        ctx = self._contexts.get(user_id)
        if not ctx:
            return False
        return ctx.state in [WorkflowState.AWAITING_CONFIRMATION, WorkflowState.OUTLINE_CONFIRMING]


ppt_workflow = PPTWorkflow()
