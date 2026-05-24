"""FastAPI 主应用入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.middleware.logging_middleware import (
    RequestLoggingMiddleware,
    ResponseLoggingMiddleware
)
from src.api.v1.endpoints import router as api_v1_router
from src.logging_config import setup_logging, get_logger

# 初始化日志
logger = setup_logging(settings.LOG_LEVEL)

# 创建 FastAPI 应用实例
app = FastAPI(
    title="Hermes Office Synergy Agent",
    description="智能办公协同代理服务 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册日志中间件
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(ResponseLoggingMiddleware)

# 注册 API 路由
app.include_router(api_v1_router)

# 健康检查端点
@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "Hermes Office Synergy Agent"}

logger.info("FastAPI 应用初始化完成")
