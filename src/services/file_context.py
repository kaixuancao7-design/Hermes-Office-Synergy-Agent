"""File context extraction shared by direct answers and presentation routing."""
from src.logging_config import get_logger

logger = get_logger("gateway")


class FileContextService:
    def __init__(self, database, get_executor):
        self.database = database
        self.get_executor = get_executor

    def _get_recent_file_content(self, user_id: str) -> str:
        """获取最近上传的文件内容"""
        from src.data.vector_store import rag_manager

        try:
            # 搜索最近添加的文档（基于时间戳或元数据）
            # 使用特殊查询词搜索最近上传的文件
            results = rag_manager.query("__recent_upload__", k=3, user_id=user_id)

            if results:
                # 按时间排序，获取最新的
                sorted_results = sorted(results,
                                      key=lambda x: x.get("metadata", {}).get("timestamp", 0),
                                      reverse=True)
                # 合并内容
                contents = []
                for result in sorted_results[:2]:  # 最多取2个最近的文件
                    content = result.get("content", "")
                    if content and len(content) > 50:  # 确保是有效内容
                        contents.append(content)

                if contents:
                    return "\n\n---\n\n".join(contents)

        except Exception as e:
            logger.error(f"获取最近文件内容失败: {str(e)}")

        # 如果向量库中没有找到，尝试从最近消息中提取文件内容
        return self._extract_file_content_from_messages(user_id)

    def _extract_file_content_from_messages(self, user_id: str) -> str:
        """从最近消息中提取文件内容"""
        recent_messages = self.database.get_recent_messages(user_id, 10)

        # 查找助手回复中包含文件内容的消息（通常文件上传后助手会回复文件内容）
        file_contents = []
        for msg in recent_messages:
            if msg.role == "assistant" and msg.content:
                content = msg.content.strip()
                # 检查是否是文件内容（不是简单的"收到文件"回复）
                if len(content) > 100 and not content.startswith("{"):
                    file_contents.append(content)

        if file_contents:
            return "\n\n---\n\n".join(file_contents[:2])

        return ""

    def _extract_valid_text(self, messages) -> str:
        """从消息列表中提取有效文本内容"""
        def is_valid_text(content):
            if not content or not content.strip():
                return False
            # 检查是否是文件上传的JSON格式
            content = content.strip()
            if content.startswith('{') and content.endswith('}'):
                # 可能是文件上传消息，检查是否包含file_key
                try:
                    import json
                    data = json.loads(content)
                    if 'file_key' in data or 'file_name' in data:
                        return False
                except:
                    pass
            return True

        valid_messages = [m for m in messages if is_valid_text(m.content)]
        return "\n".join(m.content for m in valid_messages)

    def _extract_document_content(self, user_id: str, metadata: dict) -> str:
        """提取文档内容"""
        from src.data.database import db

        file_key = metadata.get("file_key")
        file_message_id = metadata.get("message_id", "")

        if not file_key:
            recent_messages = self.database.get_recent_messages(user_id, 5)
            for msg in recent_messages:
                if msg.metadata and msg.role == "user":
                    file_key = msg.metadata.get("file_key")
                    if file_key:
                        file_message_id = msg.metadata.get("message_id", "") or msg.id or ""
                        break

        if file_key:
            tool_executor = self.get_executor()
            if tool_executor:
                try:
                    result = tool_executor.execute("feishu_file_read", {
                        "file_key": file_key,
                        "message_id": file_message_id,
                        "user_id": user_id
                    })
                    if result.get("success") and result.get("result", {}).get("content"):
                        return result["result"]["content"]
                except Exception as e:
                    logger.error(f"[PPT_HANDLER] 文件读取异常: {str(e)}")

        recent_messages = self.database.get_recent_messages(user_id, 20)
        valid_messages = [
            m for m in recent_messages
            if m.content and m.content.strip()
            and not (m.content.strip().startswith('{') and m.content.strip().endswith('}'))
        ]
        file_contents = [m.content for m in valid_messages if m.role == "assistant"]
        if not file_contents:
            file_contents = [m.content for m in valid_messages]

        return "\n".join(file_contents)
