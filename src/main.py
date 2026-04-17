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


@app.on_event("startup")
async def startup_event():
    ensure_directory("./data")
    ensure_directory("./logs")
    ensure_directory("./workspace")
    ensure_directory("./output")
    
    im_adapter_manager.register_adapter(IMAdapterConfig(
        type="feishu",
        enabled=True,
        config={}
    ))
    
    im_adapter_manager.register_adapter(IMAdapterConfig(
        type="dingtalk",
        enabled=True,
        config={}
    ))
    
    im_adapter_manager.register_adapter(IMAdapterConfig(
        type="wecom",
        enabled=True,
        config={}
    ))
    
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
