"""API Key 认证中间件

通过在请求头 X-API-Key 中传递 API Key 进行认证。
默认关闭；在 .env 中设置 API_KEY_ENABLED=true 启用。

未认证路径（始终跳过）：/health, /, /docs, /openapi.json, /favicon.ico
"""

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response
from src.config import settings
from src.exceptions import AuthenticationException
from src.logging_config import get_logger

logger = get_logger("api")

# 无需认证的公共路径
PUBLIC_PATHS = {"/health", "/", "/docs", "/openapi.json", "/favicon.ico", "/redoc"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """API Key 认证中间件"""

    async def dispatch(self, request: Request, call_next) -> Response:
        # 跳过公共路径
        if request.url.path in PUBLIC_PATHS or request.url.path.startswith("/docs") or request.url.path.startswith("/redoc"):
            return await call_next(request)

        # 如果未启用认证，跳过
        if not settings.API_KEY_ENABLED:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        valid_keys = [k.strip() for k in settings.API_KEYS.split(",") if k.strip()]

        # 如果配置了有效 Key 列表，验证请求 Key
        if valid_keys:
            if not api_key or api_key not in valid_keys:
                logger.warning(f"认证失败: path={request.url.path}, client={request.client.host}")
                raise AuthenticationException(
                    message="无效或缺失的 API Key",
                    detail="请在 X-API-Key 请求头中提供有效的 API Key"
                )
        elif not api_key:
            # 未配置 Key 但启用了认证 → 要求任意 Key
            logger.warning(f"认证失败（缺失 Key）: path={request.url.path}, client={request.client.host}")
            raise AuthenticationException(
                message="缺失 API Key",
                detail="请在 X-API-Key 请求头中提供 API Key"
            )

        return await call_next(request)
