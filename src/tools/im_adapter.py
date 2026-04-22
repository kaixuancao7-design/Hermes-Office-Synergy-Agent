"""IM适配工具 - 专为IM应用环境设计的工具适配层"""
from typing import Dict, Any, Optional, List, Union
from src.logging_config import get_logger

logger = get_logger("tool")

# IM环境常量
IM_MAX_MESSAGE_LENGTH = 8000  # IM消息最大长度
IM_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB - IM文件上传限制
IM_SUPPORTED_FILE_TYPES = [
    ".txt", ".md", ".docx", ".xlsx", ".xls", ".pptx", ".pdf",
    ".json", ".xml", ".html", ".rtf", ".csv", ".tsv",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp"
]


class IMFileParser:
    """IM环境文件解析器 - 适配IM文件大小限制和格式要求"""
    
    def __init__(self):
        self.max_file_size = IM_MAX_FILE_SIZE
        self.supported_types = IM_SUPPORTED_FILE_TYPES
    
    def validate_file(self, file_name: str, file_size: int = 0) -> Dict[str, Any]:
        """
        验证文件是否符合IM环境要求
        
        Args:
            file_name: 文件名
            file_size: 文件大小（字节）
        
        Returns:
            验证结果
        """
        import os
        _, ext = os.path.splitext(file_name)
        ext = ext.lower()
        
        if ext not in self.supported_types:
            return {
                "valid": False,
                "error": f"不支持的文件类型: {ext}，支持的类型: {', '.join(self.supported_types)}",
                "supported": False
            }
        
        if file_size > self.max_file_size:
            return {
                "valid": False,
                "error": f"文件大小超过限制（最大{self.max_file_size/1024/1024:.0f}MB）",
                "supported": True
            }
        
        return {"valid": True, "supported": True, "message": "文件验证通过"}
    
    def parse_for_im(self, file_path: str, file_content: Optional[bytes] = None, 
                     max_content_length: int = IM_MAX_MESSAGE_LENGTH) -> Dict[str, Any]:
        """
        解析文件内容并适配IM消息格式
        
        Args:
            file_path: 文件路径
            file_content: 文件二进制内容
            max_content_length: 最大内容长度
        
        Returns:
            解析结果，包含适配IM的内容
        """
        from .file_parser import file_parser
        
        # 先验证文件
        file_size = len(file_content) if file_content else 0
        validation = self.validate_file(file_path, file_size)
        if not validation["valid"]:
            return {
                "success": False,
                "error": validation["error"],
                "content": "",
                "truncated": False,
                "metadata": {}
            }
        
        # 解析文件
        result = file_parser.parse(file_path, file_content)
        
        if not result["success"]:
            return result
        
        # 适配IM消息长度
        content = result["content"]
        truncated = False
        
        if len(content) > max_content_length:
            content = content[:max_content_length - 3] + "..."
            truncated = True
        
        return {
            "success": True,
            "content": content,
            "truncated": truncated,
            "original_length": len(result["content"]),
            "display_length": len(content),
            "metadata": result["metadata"],
            "file_name": file_path.split("/")[-1].split("\\")[-1]
        }
    
    def format_file_summary(self, file_path: str, content: str, 
                           show_preview: bool = True, preview_length: int = 200) -> str:
        """
        格式化文件摘要为IM消息格式
        
        Args:
            file_path: 文件路径
            content: 文件内容
            show_preview: 是否显示预览
            preview_length: 预览长度
        
        Returns:
            格式化的消息文本
        """
        import os
        file_name = os.path.basename(file_path)
        file_size = len(content)
        
        lines = []
        lines.append(f"📄 **{file_name}**")
        lines.append(f"📊 文件大小: {self._format_size(file_size)}")
        
        if show_preview and content:
            preview = content[:preview_length] if len(content) > preview_length else content
            if len(content) > preview_length:
                preview += "..."
            lines.append(f"\n📝 内容预览:\n{preview}")
        
        return "\n".join(lines)
    
    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / 1024 / 1024:.1f} MB"


class IMMessagingTool:
    """IM消息处理工具 - 处理IM消息格式、长度限制等"""
    
    def __init__(self):
        self.max_length = IM_MAX_MESSAGE_LENGTH
    
    def split_message(self, content: str, max_length: Optional[int] = None) -> List[str]:
        """
        将长消息分割为多条IM消息
        
        Args:
            content: 原始内容
            max_length: 每条消息最大长度
        
        Returns:
            消息列表
        """
        max_len = max_length or self.max_length
        
        if len(content) <= max_len:
            return [content]
        
        messages = []
        start = 0
        
        while start < len(content):
            # 在合适的位置分割（优先在段落、句子边界分割）
            end = min(start + max_len, len(content))
            
            # 尝试在换行或句号处分割
            split_pos = content.rfind("\n", start, end)
            if split_pos == -1 or split_pos < start + max_len * 0.8:
                split_pos = content.rfind("。", start, end)
            if split_pos == -1 or split_pos < start + max_len * 0.8:
                split_pos = content.rfind("！", start, end)
            if split_pos == -1 or split_pos < start + max_len * 0.8:
                split_pos = content.rfind("？", start, end)
            if split_pos == -1 or split_pos < start + max_len * 0.8:
                split_pos = content.rfind("；", start, end)
            if split_pos == -1 or split_pos < start + max_len * 0.8:
                split_pos = content.rfind("。", start, end)
            if split_pos == -1:
                split_pos = end - 1
            
            messages.append(content[start:split_pos + 1].strip())
            start = split_pos + 1
        
        return messages
    
    def truncate_message(self, content: str, max_length: Optional[int] = None, 
                        ellipsis: str = "...") -> str:
        """
        截断消息到指定长度
        
        Args:
            content: 原始内容
            max_length: 最大长度
            ellipsis: 省略符号
        
        Returns:
            截断后的内容
        """
        max_len = max_length or self.max_length
        
        if len(content) <= max_len:
            return content
        
        return content[:max_len - len(ellipsis)] + ellipsis
    
    def format_quote(self, content: str, author: str = "") -> str:
        """
        格式化引用消息
        
        Args:
            content: 引用内容
            author: 作者
        
        Returns:
            格式化的引用消息
        """
        if author:
            return f"> **{author}**: {content}"
        return f"> {content}"
    
    def format_list(self, items: List[str], numbered: bool = False) -> str:
        """
        格式化列表消息
        
        Args:
            items: 列表项
            numbered: 是否有序
        
        Returns:
            格式化的列表消息
        """
        lines = []
        for i, item in enumerate(items, 1):
            if numbered:
                lines.append(f"{i}. {item}")
            else:
                lines.append(f"- {item}")
        return "\n".join(lines)
    
    def format_table(self, headers: List[str], rows: List[List[str]]) -> str:
        """
        格式化表格为IM消息格式（使用Markdown表格）
        
        Args:
            headers: 表头
            rows: 数据行
        
        Returns:
            格式化的表格消息
        """
        if not headers or not rows:
            return "无数据"
        
        # 构建表格
        lines = []
        
        # 表头
        lines.append("| " + " | ".join(headers) + " |")
        
        # 分隔线
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        
        # 数据行
        for row in rows:
            # 截断过长的单元格内容
            truncated_row = [str(cell)[:50] + "..." if len(str(cell)) > 50 else str(cell) for cell in row]
            lines.append("| " + " | ".join(truncated_row) + " |")
        
        return "\n".join(lines)
    
    def format_card(self, title: str, content: str, 
                   buttons: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        格式化卡片消息（用于支持卡片的IM平台）
        
        Args:
            title: 卡片标题
            content: 卡片内容
            buttons: 按钮列表，每个按钮包含 title 和 url
        
        Returns:
            卡片消息结构
        """
        card = {
            "type": "card",
            "title": title,
            "content": content,
            "buttons": buttons or []
        }
        return card
    
    def extract_mentions(self, content: str) -> List[str]:
        """
        提取消息中的@提及
        
        Args:
            content: 消息内容
        
        Returns:
            提及的用户ID或名称列表
        """
        import re
        # 匹配 @用户名 格式
        mentions = re.findall(r'@(\S+)', content)
        return mentions
    
    def escape_special_chars(self, content: str) -> str:
        """
        转义IM消息中的特殊字符
        
        Args:
            content: 原始内容
        
        Returns:
            转义后的内容
        """
        # 转义常见特殊字符
        special_chars = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        }
        
        for char, replacement in special_chars.items():
            content = content.replace(char, replacement)
        
        return content
    
    def validate_message(self, content: str) -> Dict[str, Any]:
        """
        验证消息是否符合IM平台要求
        
        Args:
            content: 消息内容
        
        Returns:
            验证结果
        """
        issues = []
        
        if not content or not content.strip():
            issues.append("消息内容为空")
        
        if len(content) > self.max_length:
            issues.append(f"消息长度超过限制（最大{self.max_length}字符）")
        
        # 检查是否包含敏感内容（简单检查）
        sensitive_words = ["敏感词1", "敏感词2", "敏感词3"]
        for word in sensitive_words:
            if word in content:
                issues.append(f"包含敏感内容: {word}")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "length": len(content)
        }


class IMUserContext:
    """IM用户上下文管理 - 管理用户会话状态"""
    
    def __init__(self):
        self.user_contexts: Dict[str, Dict[str, Any]] = {}
    
    def set_context(self, user_id: str, key: str, value: Any):
        """
        设置用户上下文
        
        Args:
            user_id: 用户ID
            key: 上下文键
            value: 上下文值
        """
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = {}
        
        self.user_contexts[user_id][key] = value
    
    def get_context(self, user_id: str, key: str, default: Any = None) -> Any:
        """
        获取用户上下文
        
        Args:
            user_id: 用户ID
            key: 上下文键
            default: 默认值
        
        Returns:
            上下文值
        """
        return self.user_contexts.get(user_id, {}).get(key, default)
    
    def remove_context(self, user_id: str, key: str):
        """
        删除用户上下文
        
        Args:
            user_id: 用户ID
            key: 上下文键
        """
        if user_id in self.user_contexts and key in self.user_contexts[user_id]:
            del self.user_contexts[user_id][key]
    
    def clear_context(self, user_id: str):
        """
        清除用户所有上下文
        
        Args:
            user_id: 用户ID
        """
        if user_id in self.user_contexts:
            del self.user_contexts[user_id]
    
    def get_user_session(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户完整会话
        
        Args:
            user_id: 用户ID
        
        Returns:
            用户会话数据
        """
        return self.user_contexts.get(user_id, {})
    
    def update_session(self, user_id: str, session_data: Dict[str, Any]):
        """
        更新用户会话
        
        Args:
            user_id: 用户ID
            session_data: 会话数据
        """
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = {}
        
        self.user_contexts[user_id].update(session_data)
    
    def set_last_message(self, user_id: str, message: str):
        """
        设置用户最后一条消息
        
        Args:
            user_id: 用户ID
            message: 消息内容
        """
        self.set_context(user_id, "last_message", message)
    
    def get_last_message(self, user_id: str) -> Optional[str]:
        """
        获取用户最后一条消息
        
        Args:
            user_id: 用户ID
        
        Returns:
            最后一条消息
        """
        return self.get_context(user_id, "last_message")


# 单例实例
im_file_parser = IMFileParser()
im_messaging_tool = IMMessagingTool()
im_user_context = IMUserContext()


# 便捷函数
def parse_file_for_im(file_path: str, file_content: Optional[bytes] = None) -> Dict[str, Any]:
    """解析文件并适配IM环境"""
    return im_file_parser.parse_for_im(file_path, file_content)


def split_message(content: str, max_length: Optional[int] = None) -> List[str]:
    """分割长消息"""
    return im_messaging_tool.split_message(content, max_length)


def format_quote(content: str, author: str = "") -> str:
    """格式化引用消息"""
    return im_messaging_tool.format_quote(content, author)


def format_list(items: List[str], numbered: bool = False) -> str:
    """格式化列表消息"""
    return im_messaging_tool.format_list(items, numbered)


def format_table(headers: List[str], rows: List[List[str]]) -> str:
    """格式化表格消息"""
    return im_messaging_tool.format_table(headers, rows)


def get_user_context(user_id: str, key: str, default: Any = None) -> Any:
    """获取用户上下文"""
    return im_user_context.get_context(user_id, key, default)


def set_user_context(user_id: str, key: str, value: Any):
    """设置用户上下文"""
    return im_user_context.set_context(user_id, key, value)
