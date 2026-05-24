import uvicorn
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 先导入配置和日志模块
from src.config import settings
from src.logging_config import setup_logging, get_logger

# 初始化日志系统（必须在其他模块导入之前执行）
# 解析日志输出目标
log_outputs = [o.strip() for o in settings.LOG_OUTPUTS.split(",") if o.strip()]

setup_logging(
    log_level=settings.LOG_LEVEL,
    log_dir=settings.LOG_DIR,
    max_file_size=settings.LOG_MAX_FILE_SIZE,
    backup_count=settings.LOG_BACKUP_COUNT,
    outputs=log_outputs,
    modules={
        "api": "INFO",
        "model": "INFO",
        "im": "DEBUG",
        "memory": "DEBUG",
        "skill": "INFO",
        "tool": "DEBUG",
        "engine": "DEBUG",
        "gateway": "DEBUG",
        "services": "INFO"
    }
)

logger = get_logger("gateway")

# 日志系统初始化完成后，再导入其他模块
from src.api.v1.endpoints import router as v1_router
from src.utils import ensure_directory
from src.data.database import db
from src.skills import skill_manager
from src.gateway.im_adapter import im_adapter_manager, IMAdapterConfig
from src.gateway.feishu_websocket import feishu_websocket_service
from src.errors import EXCEPTION_HANDLERS
from src.middleware.logging_middleware import RequestLoggingMiddleware, ResponseLoggingMiddleware
from src.plugins import init_plugins

app = FastAPI(title="Hermes Office Synergy Agent", version="1.0.0")

# 注册异常处理器
for exception_type, handler in EXCEPTION_HANDLERS.items():
    app.add_exception_handler(exception_type, handler)

# 注册日志中间件（注意顺序：先添加的先执行）
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(ResponseLoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)


def register_im_adapters():
    # 飞书配置
    feishu_enabled = bool(settings.FEISHU_APP_ID and settings.FEISHU_APP_SECRET)
    im_adapter_manager.register_adapter(IMAdapterConfig(
        type="feishu",
        enabled=feishu_enabled,
        config={
            "app_id": settings.FEISHU_APP_ID,
            "app_secret": settings.FEISHU_APP_SECRET,
            "bot_name": settings.FEISHU_BOT_NAME,
            "use_websocket": True
        }
    ))

    # 钉钉配置
    dingtalk_enabled = bool(settings.DINGTALK_APP_KEY and settings.DINGTALK_APP_SECRET)
    im_adapter_manager.register_adapter(IMAdapterConfig(
        type="dingtalk",
        enabled=dingtalk_enabled,
        config={
            "app_key": settings.DINGTALK_APP_KEY,
            "app_secret": settings.DINGTALK_APP_SECRET,
            "token": settings.DINGTALK_TOKEN
        }
    ))

    # 企业微信配置
    wecom_enabled = bool(settings.WECOM_CORP_ID and settings.WECOM_APP_SECRET)
    im_adapter_manager.register_adapter(IMAdapterConfig(
        type="wecom",
        enabled=wecom_enabled,
        config={
            "corp_id": settings.WECOM_CORP_ID,
            "app_secret": settings.WECOM_APP_SECRET,
            "agent_id": settings.WECOM_AGENT_ID
        }
    ))

    # 微信配置
    wechat_enabled = bool(settings.WECHAT_APP_ID and settings.WECHAT_APP_SECRET)
    im_adapter_manager.register_adapter(IMAdapterConfig(
        type="wechat",
        enabled=wechat_enabled,
        config={
            "app_id": settings.WECHAT_APP_ID,
            "app_secret": settings.WECHAT_APP_SECRET
        }
    ))

    # Slack 配置
    slack_enabled = bool(settings.SLACK_BOT_TOKEN)
    im_adapter_manager.register_adapter(IMAdapterConfig(
        type="slack",
        enabled=slack_enabled,
        config={
            "bot_token": settings.SLACK_BOT_TOKEN,
            "signing_secret": settings.SLACK_SIGNING_SECRET
        }
    ))

    # Discord 配置
    discord_enabled = bool(settings.DISCORD_BOT_TOKEN)
    im_adapter_manager.register_adapter(IMAdapterConfig(
        type="discord",
        enabled=discord_enabled,
        config={
            "bot_token": settings.DISCORD_BOT_TOKEN
        }
    ))


async def start_feishu_websocket():
    """启动飞书 WebSocket 长连接服务"""
    # 延迟1秒启动，确保插件系统完全初始化
    await asyncio.sleep(1)
    
    if settings.FEISHU_APP_ID and settings.FEISHU_APP_SECRET:
        logger.info("尝试启动飞书 WebSocket 长连接服务...")
        try:
            await feishu_websocket_service.start()
        except Exception as e:
            logger.error(f"飞书 WebSocket 服务启动失败: {str(e)}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")


@app.on_event("startup")
async def startup_event():
    ensure_directory("./data")
    ensure_directory("./logs")
    ensure_directory("./workspace")
    ensure_directory("./output")
    
    # 初始化插件系统（必须在其他服务启动之前）
    if not init_plugins():
        logger.error("插件系统初始化失败")
        return
    
    register_im_adapters()
    
    # 启动飞书 WebSocket 长连接服务（后台运行）- 仅在插件初始化成功后启动
    asyncio.create_task(start_feishu_websocket())
    
    logger.info("Hermes Office Synergy Agent started successfully")
    logger.info("飞书使用 WebSocket 长连接方式接收消息")


@app.on_event("shutdown")
async def shutdown_event():
    feishu_websocket_service.stop()
    logger.info("Hermes Office Synergy Agent shutting down")


@app.get("/")
async def root():
    return {"message": "Welcome to Hermes Office Synergy Agent"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )