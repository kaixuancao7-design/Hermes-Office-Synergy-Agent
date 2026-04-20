"""标准化错误响应模型和异常处理器"""
from typing import Optional, Dict, Any
from pydantic import BaseModel
from fastapi import Request, status
from fastapi.responses import JSONResponse
from src.exceptions import (
    AgentException,
    IMException,
    ModelException,
    MemoryException,
    SkillException,
    ToolException,
    ValidationException,
    AuthenticationException,
    NotFoundException
)


class ErrorResponse(BaseModel):
    """标准化错误响应模型"""
    error_code: str
    message: str
    detail: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    timestamp: Optional[int] = None
    request_id: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "error_code": "MODEL_ERROR",
                "message": "模型服务不可用",
                "detail": "无法连接到Ollama服务",
                "context": {
                    "model_type": "ollama",
                    "host": "http://localhost:11434"
                },
                "timestamp": 1714567890,
                "request_id": "abc123"
            }
        }


async def agent_exception_handler(request: Request, exc: AgentException) -> JSONResponse:
    """Agent异常处理器"""
    from src.utils import get_timestamp, generate_id
    
    response = ErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        detail=exc.detail,
        context=exc.context,
        timestamp=get_timestamp(),
        request_id=generate_id()
    )
    
    return JSONResponse(
        status_code=exc.http_status_code,
        content=response.dict()
    )


async def im_exception_handler(request: Request, exc: IMException) -> JSONResponse:
    """IM适配器异常处理器"""
    return await agent_exception_handler(request, exc)


async def model_exception_handler(request: Request, exc: ModelException) -> JSONResponse:
    """模型服务异常处理器"""
    return await agent_exception_handler(request, exc)


async def memory_exception_handler(request: Request, exc: MemoryException) -> JSONResponse:
    """记忆存储异常处理器"""
    return await agent_exception_handler(request, exc)


async def skill_exception_handler(request: Request, exc: SkillException) -> JSONResponse:
    """技能管理异常处理器"""
    return await agent_exception_handler(request, exc)


async def tool_exception_handler(request: Request, exc: ToolException) -> JSONResponse:
    """工具执行异常处理器"""
    return await agent_exception_handler(request, exc)


async def validation_exception_handler(request: Request, exc: ValidationException) -> JSONResponse:
    """参数验证异常处理器"""
    return await agent_exception_handler(request, exc)


async def auth_exception_handler(request: Request, exc: AuthenticationException) -> JSONResponse:
    """认证异常处理器"""
    return await agent_exception_handler(request, exc)


async def not_found_exception_handler(request: Request, exc: NotFoundException) -> JSONResponse:
    """资源未找到异常处理器"""
    return await agent_exception_handler(request, exc)


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """通用异常处理器（兜底处理）"""
    from src.utils import get_timestamp, generate_id
    
    response = ErrorResponse(
        error_code="INTERNAL_ERROR",
        message="服务器内部错误",
        detail=str(exc),
        timestamp=get_timestamp(),
        request_id=generate_id()
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response.dict()
    )


# 异常处理器映射
EXCEPTION_HANDLERS = {
    AgentException: agent_exception_handler,
    IMException: im_exception_handler,
    ModelException: model_exception_handler,
    MemoryException: memory_exception_handler,
    SkillException: skill_exception_handler,
    ToolException: tool_exception_handler,
    ValidationException: validation_exception_handler,
    AuthenticationException: auth_exception_handler,
    NotFoundException: not_found_exception_handler,
    Exception: general_exception_handler
}
