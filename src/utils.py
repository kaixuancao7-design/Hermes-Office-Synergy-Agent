import os
from datetime import datetime
from uuid import uuid4

from src.data.emoji_map import EMOJI_MAP


def setup_logging(log_level: str = "INFO"):
    """
    日志初始化函数（兼容旧接口）
    实际日志配置已移至 src.logging_config 模块
    """
    from src.logging_config import setup_logging as new_setup_logging, get_logger
    new_setup_logging(log_level=log_level)
    return get_logger("gateway")


def safe_log_string(text: str) -> str:
    """
    安全的日志字符串处理函数，移除或替换无法在控制台显示的字符
    """
    if text is None:
        return ""
    
    # 替换常见的 emoji 字符
    for emoji, replacement in EMOJI_MAP.items():
        text = text.replace(emoji, replacement)
    
    return text


def generate_id() -> str:
    return str(uuid4())


def get_timestamp() -> int:
    return int(datetime.now().timestamp())


def ensure_directory(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def truncate_text(text: str, max_length: int = 500) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."