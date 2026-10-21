"""API Key 认证中间件

通过在请求头 X-API-Key 中传递 API Key 进行认证。
默认关闭；在 .env 中设置 API_KEY_ENABLED=true 启用。

未认证路径（始终跳过）：/health, /, /docs, /openapi.json, /favicon.ico
"""

import json
from fastapi import HTTPException
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response
from src.config import settings
from src.logging_config import get_logger

logger = get_logger("api")

# 无需认证的公共路径
PUBLIC_PATHS = {"/health", "/ready", "/", "/docs", "/openapi.json", "/favicon.ico", "/redoc"}


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
        try:
            users = json.loads(settings.API_KEY_USERS)
        except (ValueError, TypeError):
            users = {}
        if not isinstance(users, dict):
            users = {}
        if not api_key or api_key not in set(valid_keys) | set(users):
            return JSONResponse({"detail": "无效或缺失的 API Key"}, status_code=401)
        request.state.user_id = users.get(api_key)
        return await call_next(request)


def authenticated_user(request: Request) -> str:
    """Identity must come from a server-configured credential mapping."""
    user_id = getattr(request.state, "user_id", None)
    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(status_code=401, detail="需要绑定用户的 API Key，并启用 API_KEY_ENABLED")
    return user_id


def require_admin(user_id: str):
    from src.services.permission_service import permission_service
    if permission_service.get_user_role(user_id) != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
