"""工具函数集合"""
import uuid
import time
import os
import re
from typing import Any, Optional


def generate_id() -> str:
    """生成唯一ID"""
    return str(uuid.uuid4())[:8]


def get_timestamp() -> int:
    """获取当前时间戳（毫秒）"""
    return int(time.time() * 1000)


def ensure_directory(path: str) -> bool:
    """确保目录存在"""
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except Exception as e:
        return False


def safe_log_string(content: Any, max_length: int = 500) -> str:
    """安全的日志字符串，防止敏感信息和过长内容"""
    if content is None:
        return "None"
    
    try:
        str_content = str(content)
        # 限制长度
        if len(str_content) > max_length:
            str_content = str_content[:max_length] + "..."
        
        # 移除敏感信息模式
        patterns = [
            (r'[a-zA-Z0-9]+@[a-zA-Z0-9]+\.[a-zA-Z]+', '[REDACTED_EMAIL]'),
            (r'1[3-9]\d{9}', '[REDACTED_PHONE]'),
            (r'[a-fA-F0-9]{32,}', '[REDACTED_HASH]'),
        ]
        
        for pattern, replacement in patterns:
            str_content = re.sub(pattern, replacement, str_content)
        
        return str_content
    except Exception:
        return str(content)[:max_length]


def format_error_message(error: Exception, context: Optional[dict] = None) -> str:
    """格式化错误消息"""
    msg = f"错误: {str(error)}"
    if context:
        context_str = ", ".join([f"{k}={v}" for k, v in context.items()])
        msg += f" | 上下文: {context_str}"
    return msg


def parse_json_safe(data: str) -> Optional[dict]:
    """安全地解析JSON字符串"""
    try:
        import json
        return json.loads(data)
    except Exception:
        return None


def truncate_text(text: str, max_length: int = 1000, suffix: str = "...") -> str:
    """截断文本"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + suffix
