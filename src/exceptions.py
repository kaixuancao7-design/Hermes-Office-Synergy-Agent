"""全局异常类定义"""
from typing import Optional, Dict, Any


class AgentException(Exception):
    """Agent基础异常类"""
    
    def __init__(
        self,
        error_code: str,
        message: str,
        detail: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        http_status_code: int = 500
    ):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.detail = detail
        self.context = context or {}
        self.http_status_code = http_status_code


class IMException(AgentException):
    """IM适配器异常"""
    
    def __init__(
        self,
        message: str,
        detail: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        http_status_code: int = 503
    ):
        super().__init__(
            error_code="IM_ERROR",
            message=message,
            detail=detail,
            context=context,
            http_status_code=http_status_code
        )


class ModelException(AgentException):
    """模型服务异常"""
    
    def __init__(
        self,
        message: str,
        detail: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        http_status_code: int = 503
    ):
        super().__init__(
            error_code="MODEL_ERROR",
            message=message,
            detail=detail,
            context=context,
            http_status_code=http_status_code
        )


class MemoryException(AgentException):
    """记忆存储异常"""
    
    def __init__(
        self,
        message: str,
        detail: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        http_status_code: int = 500
    ):
        super().__init__(
            error_code="MEMORY_ERROR",
            message=message,
            detail=detail,
            context=context,
            http_status_code=http_status_code
        )


class SkillException(AgentException):
    """技能管理异常"""
    
    def __init__(
        self,
        message: str,
        detail: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        http_status_code: int = 400
    ):
        super().__init__(
            error_code="SKILL_ERROR",
            message=message,
            detail=detail,
            context=context,
            http_status_code=http_status_code
        )


class ToolException(AgentException):
    """工具执行异常"""
    
    def __init__(
        self,
        message: str,
        detail: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        http_status_code: int = 500
    ):
        super().__init__(
            error_code="TOOL_ERROR",
            message=message,
            detail=detail,
            context=context,
            http_status_code=http_status_code
        )


class ValidationException(AgentException):
    """参数验证异常"""
    
    def __init__(
        self,
        message: str,
        detail: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        http_status_code: int = 400
    ):
        super().__init__(
            error_code="VALIDATION_ERROR",
            message=message,
            detail=detail,
            context=context,
            http_status_code=http_status_code
        )


class AuthenticationException(AgentException):
    """认证异常"""
    
    def __init__(
        self,
        message: str,
        detail: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        http_status_code: int = 401
    ):
        super().__init__(
            error_code="AUTH_ERROR",
            message=message,
            detail=detail,
            context=context,
            http_status_code=http_status_code
        )


class NotFoundException(AgentException):
    """资源未找到异常"""
    
    def __init__(
        self,
        message: str,
        detail: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        http_status_code: int = 404
    ):
        super().__init__(
            error_code="NOT_FOUND",
            message=message,
            detail=detail,
            context=context,
            http_status_code=http_status_code
        )
