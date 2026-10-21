"""Presentation message handling independent of the transport router."""
from src.types import Intent
from src.logging_config import get_logger

logger = get_logger("gateway")


class PresentationMessageService:
    def __init__(self, workflow, file_context):
        self.workflow = workflow
        self.file_context = file_context

    async def _handle_ppt_generation(self, user_id: str, intent: Intent, context: str, metadata: dict = None) -> str:
        """处理PPT生成相关意图 - 使用LangGraph PPT工作流"""
        logger.info(f"[PPT_HANDLER] 开始PPT生产: user_id={user_id}, intent={intent.type}")

        metadata = metadata or {}

        if await self.workflow.is_awaiting_confirmation(user_id):
            logger.info("[PPT_HANDLER] 检测到等待确认状态，继续工作流")
            response, ctx = await self.workflow.continue_workflow(user_id, context)
            self._clear_ppt_workflow_context(user_id)
            return response

        document_content = self.file_context._extract_document_content(user_id, metadata)
        response, ctx = await self.workflow.start_workflow(
            user_id=user_id, intent_type=intent.type,
            content=context, document_content=document_content,
        )
        self._clear_ppt_workflow_context(user_id)
        return response

    def _clear_ppt_workflow_context(self, user_id: str):
        """清除PPT工作流上下文（LangGraph 版本由 checkpointer 自动管理）"""
        # LangGraph StateGraph 通过 checkpointer 管理状态，无需手动清理内存
        # 保留 _contexts 兼容：移除活跃用户标记
        if hasattr(self.workflow, '_contexts') and user_id in self.workflow._contexts:
            self.workflow._contexts.pop(user_id, None)
            logger.debug(f"[PPT_HANDLER] 清除工作流上下文: user_id={user_id}")
