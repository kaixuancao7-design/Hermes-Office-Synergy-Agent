"""日志中间件"""
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from src.logging_config import (
    set_request_context,
    clear_request_context,
    get_logger
)

logger = get_logger("api")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件 - 自动生成请求ID并记录请求/响应"""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # 生成或获取请求ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # 获取用户ID（从请求头或其他来源）
        user_id = request.headers.get("X-User-ID", "-")
        
        # 设置请求上下文
        set_request_context(request_id=request_id, user_id=user_id)
        
        # 记录请求开始
        logger.info(
            f"Request started | {request.method} {request.url.path} | "
            f"client={request.client.host}:{request.client.port}"
        )
        
        try:
            # 处理请求
            response = await call_next(request)
            
            # 记录请求完成
            logger.info(
                f"Request completed | {request.method} {request.url.path} | "
                f"status={response.status_code} | duration=calculated"
            )
            
            return response
        
        except Exception as e:
            # 记录请求异常
            logger.error(
                f"Request error | {request.method} {request.url.path} | "
                f"error={str(e)}",
                exc_info=True
            )
            raise
        
        finally:
            # 清除请求上下文
            clear_request_context()


class ResponseLoggingMiddleware(BaseHTTPMiddleware):
    """响应日志中间件 - 记录响应详情"""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        
        # 记录响应信息
        logger.debug(
            f"Response | status={response.status_code} | "
            f"content_type={response.headers.get('content-type', '')}"
        )
        
        return response
