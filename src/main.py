import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.v1.endpoints import router as v1_router
from src.config import settings
from src.utils import setup_logging, ensure_directory
from src.data.database import db
from src.skills.skill_manager import skill_manager
from src.gateway.im_adapter import im_adapter_manager, IMAdapterConfig

logger = setup_logging(settings.LOG_LEVEL)

app = FastAPI(title="Hermes Office Synergy Agent", version="1.0.0")

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
            "bot_name": settings.FEISHU_BOT_NAME
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


@app.on_event("startup")
async def startup_event():
    ensure_directory("./data")
    ensure_directory("./logs")
    ensure_directory("./workspace")
    ensure_directory("./output")
    
    register_im_adapters()
    
    logger.info("Hermes Office Synergy Agent started successfully")


@app.on_event("shutdown")
async def shutdown_event():
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
