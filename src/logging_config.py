"""日志配置模块"""
import logging
import logging.handlers
import os
from typing import Optional, Dict, Any
from contextvars import ContextVar
from datetime import datetime

# 请求ID上下文字段
request_id_var = ContextVar("request_id", default=None)
user_id_var = ContextVar("user_id", default=None)


class RequestIDFilter(logging.Filter):
    """请求ID过滤器 - 自动添加请求ID和用户ID到日志记录"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        record.user_id = user_id_var.get() or "-"
        return True


class CustomFormatter(logging.Formatter):
    """自定义日志格式化器 - 线程安全版本"""

    DEFAULT_FORMAT = (
        "%(asctime)s.%(msecs)03d | %(levelname)s | %(request_id)s | %(user_id)s | "
        "%(name)s:%(lineno)d | %(message)s"
    )

    DEBUG_FORMAT = (
        "%(asctime)s.%(msecs)03d | %(levelname)s | %(request_id)s | %(user_id)s | "
        "%(name)s:%(lineno)d | %(funcName)s | %(message)s"
    )

    ERROR_FORMAT = (
        "%(asctime)s.%(msecs)03d | %(levelname)s | %(request_id)s | %(user_id)s | "
        "%(name)s:%(lineno)d | %(funcName)s | %(message)s\n%(exc_text)s"
    )

    def format(self, record: logging.LogRecord) -> str:
        """线程安全的格式化方法"""
        if record.levelno == logging.DEBUG:
            fmt = self.DEBUG_FORMAT
        elif record.levelno >= logging.ERROR:
            fmt = self.ERROR_FORMAT
        else:
            fmt = self.DEFAULT_FORMAT

        if not hasattr(record, 'exc_text') or record.exc_text is None:
            record.exc_text = ""

        formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


def setup_logging(
    log_level: str = "INFO",
    log_dir: str = "./logs",
    max_file_size: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    modules: Optional[Dict[str, str]] = None
) -> logging.Logger:
    """
    配置日志系统

    Args:
        log_level: 全局日志级别
        log_dir: 日志目录
        max_file_size: 单个日志文件最大大小
        backup_count: 备份文件数量
        modules: 模块日志级别配置

    Returns:
        根日志记录器
    """
    os.makedirs(log_dir, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    root_logger.handlers.clear()

    request_id_filter = RequestIDFilter()

    formatter = CustomFormatter()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(request_id_filter)
    root_logger.addHandler(console_handler)

    global_file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "hermes.log"),
        maxBytes=max_file_size,
        backupCount=backup_count,
        encoding="utf-8"
    )
    global_file_handler.setLevel(logging.INFO)
    global_file_handler.setFormatter(formatter)
    global_file_handler.addFilter(request_id_filter)
    root_logger.addHandler(global_file_handler)

    error_file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "error.log"),
        maxBytes=max_file_size,
        backupCount=backup_count,
        encoding="utf-8"
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(formatter)
    error_file_handler.addFilter(request_id_filter)
    root_logger.addHandler(error_file_handler)

    module_configs = modules or {
        "api": "INFO",
        "model": "INFO",
        "im": "INFO",
        "memory": "INFO",
        "skill": "INFO",
        "tool": "INFO",
        "engine": "DEBUG",
        "gateway": "DEBUG",
        "services": "INFO"
    }

    for module_name, module_level in module_configs.items():
        module_logger = logging.getLogger(f"hermes.{module_name}")
        module_logger.setLevel(getattr(logging, module_level.upper()))
        module_logger.propagate = False

        module_logger.handlers.clear()

        module_file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, f"{module_name}.log"),
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding="utf-8"
        )
        module_file_handler.setLevel(logging.DEBUG)
        module_file_handler.setFormatter(formatter)
        module_file_handler.addFilter(request_id_filter)
        module_logger.addHandler(module_file_handler)

    return root_logger


def get_logger(module_name: str) -> logging.Logger:
    """
    获取模块级日志记录器

    Args:
        module_name: 模块名称
    Returns:
        模块专属日志记录器
    """
    return logging.getLogger(f"hermes.{module_name}")


def set_request_context(request_id: Optional[str] = None, user_id: Optional[str] = None) -> None:
    """
    设置请求上下文
    Args:
        request_id: 请求ID
        user_id: 用户ID
    """
    if request_id:
        request_id_var.set(request_id)
    if user_id:
        user_id_var.set(user_id)


def clear_request_context() -> None:
    """清除请求上下文"""
    request_id_var.set(None)
    user_id_var.set(None)


def get_request_id() -> Optional[str]:
    """获取当前请求ID"""
    return request_id_var.get()


def get_user_id() -> Optional[str]:
    """获取当前用户ID"""
    return user_id_var.get()


def log_method_call(logger: logging.Logger, level: int = logging.DEBUG):
    """
    装饰器：记录方法调用

    Args:
        logger: 日志记录器
        level: 日志级别
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            logger.log(level, f"Entering {func_name} with args={args}, kwargs={kwargs}")
            try:
                result = func(*args, **kwargs)
                logger.log(level, f"Exiting {func_name} with result={result}")
                return result
            except Exception as e:
                logger.error(f"Error in {func_name}: {str(e)}", exc_info=True)
                raise
        return wrapper
    return decorator