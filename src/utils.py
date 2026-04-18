import logging
import os
from datetime import datetime
from uuid import uuid4


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("hermes_office_agent")
    logger.setLevel(log_level)
    
    # 如果已经有 handler，不再重复添加
    if logger.handlers:
        return logger
    
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    os.makedirs("logs", exist_ok=True)
    file_handler = logging.FileHandler("logs/combined.log")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger


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
