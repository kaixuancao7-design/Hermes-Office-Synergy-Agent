"""滑动窗口速率限制中间件

使用基于 IP + 用户 ID 的滑动窗口算法限制请求频率。
速率限制参数可在 .env 中配置：
  RATE_LIMIT_ENABLED=true/false（默认: true）
  RATE_LIMIT_MAX_REQUESTS=60（默认: 60）
  RATE_LIMIT_WINDOW_SECONDS=60（默认: 60）
"""

import time
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from src.config import settings
from src.logging_config import get_logger

logger = get_logger("api")

# 无需限流的公共路径
PUBLIC_PATHS = {"/health", "/", "/docs", "/openapi.json", "/favicon.ico", "/redoc"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """滑动窗口速率限制中间件"""

    def __init__(self, app):
        super().__init__(app)
        self.window_size = settings.RATE_LIMIT_WINDOW_SECONDS
        self.max_requests = settings.RATE_LIMIT_MAX_REQUESTS
        self._requests: dict[str, list[float]] = defaultdict(list)
        logger.info(f"[RATE_LIMIT] 已初始化: max={self.max_requests}/{self.window_size}s")

    async def dispatch(self, request: Request, call_next) -> Response:
        # 跳过公共路径
        if request.url.path in PUBLIC_PATHS or request.url.path.startswith("/docs") or request.url.path.startswith("/redoc"):
            return await call_next(request)

        # 如果未启用，跳过
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        # 客户端标识：优先使用用户 ID，否则使用 IP
        client_key = request.headers.get("X-User-ID") or request.client.host
        now = time.time()

        # 滑动窗口：移除窗口外的旧记录
        cutoff = now - self.window_size
        self._requests[client_key] = [t for t in self._requests[client_key] if t > cutoff]

        if len(self._requests[client_key]) >= self.max_requests:
            logger.warning(f"[RATE_LIMIT] {client_key} 请求过多 ({len(self._requests[client_key])}/{self.max_requests})")
            return JSONResponse(
                status_code=429,
                content={
                    "error_code": "RATE_LIMITED",
                    "message": f"请求过于频繁。限制: {self.max_requests} 次/{self.window_size}秒",
                    "detail": "请稍后重试",
                    "retry_after_seconds": self.window_size,
                },
            )

        self._requests[client_key].append(now)

        # 定期清理内存（每个客户端最多保留窗口期内的记录）
        if len(self._requests) > 1000:
            stale = [k for k, v in self._requests.items() if all(t <= cutoff for t in v)]
            for k in stale:
                del self._requests[k]

        return await call_next(request)
