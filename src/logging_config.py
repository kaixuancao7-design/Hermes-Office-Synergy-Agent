"""日志配置模块 - 支持结构化日志、多输出目标、分级控制"""
import logging
import logging.handlers
import os
import json
import asyncio
from typing import Optional, Dict, Any, List
from contextvars import ContextVar
from datetime import datetime
from enum import Enum

# 请求ID上下文字段
request_id_var = ContextVar("request_id", default=None)
user_id_var = ContextVar("user_id", default=None)
session_id_var = ContextVar("session_id", default=None)


class LogOutputType(Enum):
    """日志输出类型枚举"""
    CONSOLE = "console"
    FILE = "file"
    SYSLOG = "syslog"
    JSON_FILE = "json_file"


class LogLevel(Enum):
    """日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class RequestIDFilter(logging.Filter):
    """请求ID过滤器 - 自动添加请求ID和用户ID到日志记录"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        record.user_id = user_id_var.get() or "-"
        record.session_id = session_id_var.get() or "-"
        return True


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器 - 支持文本和JSON格式"""

    DEFAULT_FORMAT = (
        "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(request_id)s | %(user_id)s | "
        "%(session_id)s | %(name)s:%(lineno)d | %(message)s"
    )

    DEBUG_FORMAT = (
        "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(request_id)s | %(user_id)s | "
        "%(session_id)s | %(name)s:%(lineno)d | %(funcName)s | %(message)s"
    )

    ERROR_FORMAT = (
        "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(request_id)s | %(user_id)s | "
        "%(session_id)s | %(name)s:%(lineno)d | %(funcName)s | %(message)s\n%(exc_text)s"
    )

    def __init__(self, fmt: str = None, datefmt: str = None, style: str = "%", 
                 json_format: bool = False):
        super().__init__(fmt, datefmt, style)
        self.json_format = json_format

    def format(self, record: logging.LogRecord) -> str:
        """线程安全的格式化方法"""
        # 设置异常信息
        if record.exc_info:
            record.exc_text = self.formatException(record.exc_info)
        else:
            record.exc_text = ""

        if self.json_format:
            return self._format_json(record)
        else:
            return self._format_text(record)

    def _format_text(self, record: logging.LogRecord) -> str:
        """格式化文本日志"""
        if record.levelno == logging.DEBUG:
            fmt = self.DEBUG_FORMAT
        elif record.levelno >= logging.ERROR:
            fmt = self.ERROR_FORMAT
        else:
            fmt = self.DEFAULT_FORMAT

        formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)

    def _format_json(self, record: logging.LogRecord) -> str:
        """格式化JSON日志"""
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3],
            "level": record.levelname,
            "request_id": getattr(record, 'request_id', "-"),
            "user_id": getattr(record, 'user_id', "-"),
            "session_id": getattr(record, 'session_id', "-"),
            "module": record.name,
            "line_number": record.lineno,
            "function": record.funcName,
            "message": record.getMessage(),
            "process": record.process,
            "thread": record.threadName
        }

        if record.exc_text:
            log_entry["exception"] = record.exc_text

        return json.dumps(log_entry, ensure_ascii=False)


class LoggingConfig:
    """日志配置类"""

    def __init__(
        self,
        log_level: str = "INFO",
        log_dir: str = "./logs",
        max_file_size: int = 10 * 1024 * 1024,
        backup_count: int = 5,
        outputs: List[str] = None,
        modules: Optional[Dict[str, str]] = None
    ):
        self.log_level = log_level
        self.log_dir = log_dir
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self.outputs = outputs or ["console", "file"]
        self.modules = modules or {
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


def setup_logging(
    log_level: str = "INFO",
    log_dir: str = "./logs",
    max_file_size: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    outputs: Optional[List[str]] = None,
    modules: Optional[Dict[str, str]] = None
) -> logging.Logger:
    """
    配置日志系统

    Args:
        log_level: 全局日志级别
        log_dir: 日志目录
        max_file_size: 单个日志文件最大大小（字节）
        backup_count: 备份文件数量
        outputs: 输出目标列表 ["console", "file", "syslog", "json_file"]
        modules: 模块日志级别配置

    Returns:
        根日志记录器
    """
    os.makedirs(log_dir, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # 清除现有处理器
    root_logger.handlers.clear()

    request_id_filter = RequestIDFilter()
    output_types = outputs or ["console", "file"]

    # 控制台输出
    if "console" in output_types:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(StructuredFormatter())
        console_handler.addFilter(request_id_filter)
        root_logger.addHandler(console_handler)
        logging.debug("控制台日志输出已启用")

    # 普通文件输出
    if "file" in output_types:
        global_file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, "hermes.log"),
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding="utf-8"
        )
        global_file_handler.setLevel(logging.INFO)
        global_file_handler.setFormatter(StructuredFormatter())
        global_file_handler.addFilter(request_id_filter)
        root_logger.addHandler(global_file_handler)
        logging.debug("文件日志输出已启用")

    # JSON文件输出
    if "json_file" in output_types:
        json_file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, "hermes.json"),
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding="utf-8"
        )
        json_file_handler.setLevel(logging.INFO)
        json_file_handler.setFormatter(StructuredFormatter(json_format=True))
        json_file_handler.addFilter(request_id_filter)
        root_logger.addHandler(json_file_handler)
        logging.debug("JSON文件日志输出已启用")

    # 错误文件输出（始终启用）
    error_file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "error.log"),
        maxBytes=max_file_size,
        backupCount=backup_count,
        encoding="utf-8"
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(StructuredFormatter())
    error_file_handler.addFilter(request_id_filter)
    root_logger.addHandler(error_file_handler)

    # Syslog输出
    if "syslog" in output_types:
        try:
            syslog_handler = logging.handlers.SysLogHandler(address="/dev/log")
            syslog_handler.setLevel(logging.WARNING)
            syslog_handler.setFormatter(StructuredFormatter())
            syslog_handler.addFilter(request_id_filter)
            root_logger.addHandler(syslog_handler)
            logging.debug("Syslog日志输出已启用")
        except Exception as e:
            logging.warning(f"无法启用Syslog输出: {str(e)}")

    # 配置模块级日志
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

        # 为每个模块创建独立的日志文件
        module_file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, f"{module_name}.log"),
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding="utf-8"
        )
        module_file_handler.setLevel(logging.DEBUG)
        module_file_handler.setFormatter(StructuredFormatter())
        module_file_handler.addFilter(request_id_filter)
        module_logger.addHandler(module_file_handler)

        # 添加控制台输出
        module_console_handler = logging.StreamHandler()
        module_console_handler.setLevel(logging.WARNING)
        module_console_handler.setFormatter(StructuredFormatter())
        module_console_handler.addFilter(request_id_filter)
        module_logger.addHandler(module_console_handler)

    logging.info(f"日志系统初始化完成 - 级别: {log_level}, 输出目标: {output_types}")
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


def set_request_context(
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None
) -> None:
    """
    设置请求上下文
    Args:
        request_id: 请求ID
        user_id: 用户ID
        session_id: 会话ID
    """
    if request_id:
        request_id_var.set(request_id)
    if user_id:
        user_id_var.set(user_id)
    if session_id:
        session_id_var.set(session_id)


def clear_request_context() -> None:
    """清除请求上下文"""
    request_id_var.set(None)
    user_id_var.set(None)
    session_id_var.set(None)


def get_request_id() -> Optional[str]:
    """获取当前请求ID"""
    return request_id_var.get()


def get_user_id() -> Optional[str]:
    """获取当前用户ID"""
    return user_id_var.get()


def get_session_id() -> Optional[str]:
    """获取当前会话ID"""
    return session_id_var.get()


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
            start_time = datetime.now()
            try:
                result = func(*args, **kwargs)
                elapsed = (datetime.now() - start_time).total_seconds() * 1000
                logger.log(level, f"Exiting {func_name} in {elapsed:.2f}ms with result={result}")
                return result
            except Exception as e:
                elapsed = (datetime.now() - start_time).total_seconds() * 1000
                logger.error(f"Error in {func_name} after {elapsed:.2f}ms: {str(e)}", exc_info=True)
                raise
        return wrapper
    return decorator


def log_async_method_call(logger: logging.Logger, level: int = logging.DEBUG):
    """
    装饰器：记录异步方法调用

    Args:
        logger: 日志记录器
        level: 日志级别
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            func_name = func.__name__
            logger.log(level, f"Entering async {func_name} with args={args}, kwargs={kwargs}")
            start_time = datetime.now()
            try:
                result = await func(*args, **kwargs)
                elapsed = (datetime.now() - start_time).total_seconds() * 1000
                logger.log(level, f"Exiting async {func_name} in {elapsed:.2f}ms with result={result}")
                return result
            except Exception as e:
                elapsed = (datetime.now() - start_time).total_seconds() * 1000
                logger.error(f"Error in async {func_name} after {elapsed:.2f}ms: {str(e)}", exc_info=True)
                raise
        return wrapper
    return decorator


def log_performance(logger: logging.Logger, operation_name: str):
    """
    性能日志装饰器（支持同步和异步函数）

    Args:
        logger: 日志记录器
        operation_name: 操作名称
    """
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                start_time = datetime.now()
                try:
                    result = await func(*args, **kwargs)
                    elapsed = (datetime.now() - start_time).total_seconds() * 1000
                    logger.info(f"[PERF] {operation_name} completed in {elapsed:.2f}ms")
                    return result
                except Exception as e:
                    elapsed = (datetime.now() - start_time).total_seconds() * 1000
                    logger.error(f"[PERF] {operation_name} failed after {elapsed:.2f}ms: {str(e)}")
                    raise
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                start_time = datetime.now()
                try:
                    result = func(*args, **kwargs)
                    elapsed = (datetime.now() - start_time).total_seconds() * 1000
                    logger.info(f"[PERF] {operation_name} completed in {elapsed:.2f}ms")
                    return result
                except Exception as e:
                    elapsed = (datetime.now() - start_time).total_seconds() * 1000
                    logger.error(f"[PERF] {operation_name} failed after {elapsed:.2f}ms: {str(e)}")
                    raise
            return sync_wrapper
    return decorator


def log_event(logger: logging.Logger, event_type: str, **kwargs):
    """
    记录业务事件

    Args:
        logger: 日志记录器
        event_type: 事件类型
        **kwargs: 事件参数
    """
    params = ", ".join(f"{k}={v}" for k, v in kwargs.items())
    logger.info(f"[EVENT] {event_type} | {params}")


def log_metric(logger: logging.Logger, metric_name: str, value: float, **tags):
    """
    记录指标数据

    Args:
        logger: 日志记录器
        metric_name: 指标名称
        value: 指标值
        **tags: 标签
    """
    tag_str = ", ".join(f"{k}={v}" for k, v in tags.items())
    logger.info(f"[METRIC] {metric_name}={value:.4f} | {tag_str}")