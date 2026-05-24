"""自定义异常类"""

from typing import Dict, Any, Optional


class BaseException(Exception):
    """基础异常类"""
    
    def __init__(
        self,
        message: str,
        detail: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.detail = detail
        self.context = context or {}


class SkillException(BaseException):
    """技能相关异常"""
    pass


class MemoryException(BaseException):
    """记忆相关异常"""
    pass


class NotFoundException(BaseException):
    """资源未找到异常"""
    pass


class ValidationException(BaseException):
    """验证异常"""
    pass


class IMException(BaseException):
    """IM相关异常"""
    pass
