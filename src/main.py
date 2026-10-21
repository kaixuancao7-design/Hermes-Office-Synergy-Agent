import uvicorn
import asyncio
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# 先导入配置和日志模块
from src.config import settings
from src.logging_config import setup_logging, get_logger

def configure_logging():
    # 显式启动时配置日志，导入应用模块不创建文件处理器。
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

# 导入应用依赖；实际资源在 startup_event 中初始化。
from src.api.v1.endpoints import router as v1_router
from src.utils import ensure_directory
from src.data.database import db
from src.skills import skill_manager
from src.gateway.im_adapter import im_adapter_manager, IMAdapterConfig
from src.gateway.feishu_websocket import feishu_websocket_service
from src.errors import EXCEPTION_HANDLERS
from src.middleware.logging_middleware import RequestLoggingMiddleware, ResponseLoggingMiddleware
from src.middleware.auth_middleware import APIKeyMiddleware
from src.middleware.rate_limit_middleware import RateLimitMiddleware
from src.plugins import init_plugins, close_plugins, component_status

app = FastAPI(title="Hermes Office Synergy Agent", version="1.0.0")
app.state.ready = False
app.state.background_tasks = {}
app.state.integrations = {}


def track_background(name, coroutine):
    app.state.integrations[name] = "starting"
    task = asyncio.create_task(coroutine, name=name)
    app.state.background_tasks[name] = task

    def completed(done):
        if done.cancelled():
            app.state.integrations[name] = "stopped"
        else:
            error = done.exception()
            app.state.integrations[name] = "failed" if error or done.result() is False else "stopped"
            if error:
                logger.error("Background service failed: %s", name, exc_info=(type(error), error, error.__traceback__))
    task.add_done_callback(completed)
    return task

# 注册异常处理器
for exception_type, handler in EXCEPTION_HANDLERS.items():
    app.add_exception_handler(exception_type, handler)

# 注册中间件（FastAPI 按添加顺序的逆序执行 request 阶段）
# 请求：CORS → RequestLogging → ResponseLogging → RateLimit(IP) → Auth → Handler
# 日志覆盖 401/429；限流覆盖未认证请求；CORS 在外层处理预检和拒绝响应。
app.add_middleware(APIKeyMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(ResponseLoggingMiddleware)
app.add_middleware(RequestLoggingMiddleware)

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
            return await feishu_websocket_service.start()
        except Exception as e:
            logger.error(f"飞书 WebSocket 服务启动失败: {str(e)}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return False


@app.on_event("startup")
async def startup_event():
    app.state.ready = False
    try:
        await initialize_services()
        app.state.ready = True
    except BaseException:
        await shutdown_event()
        raise


async def initialize_services():
    configure_logging()
    db.initialize()
    from src.services.audit_log_service import audit_log_service
    from src.gateway.message_router import message_router
    audit_log_service.initialize()
    message_router.initialize()
    ensure_directory("./data")
    ensure_directory("./logs")
    ensure_directory("./workspace")
    ensure_directory("./output")
    ensure_directory("./skills")
    ensure_directory("./skills/learned")

    # 初始化插件系统（必须在其他服务启动之前）
    if not init_plugins():
        logger.error("插件系统初始化失败")
        raise RuntimeError("Required plugin initialization failed")

    register_im_adapters()

    from src.engine.mcp_client import mcp_client_manager
    await mcp_client_manager.refresh()

    # 启动飞书 WebSocket 长连接服务（后台运行）- 仅在插件初始化成功后启动
    if settings.FEISHU_APP_ID and settings.FEISHU_APP_SECRET:
        track_background("feishu", start_feishu_websocket())

    # MCP Server HTTP (optional, background)
    if settings.MCP_SERVER_ENABLED:
        from src.engine.mcp_server import start_http_server
        logger.info(f"[MCP] MCP Server HTTP starting (port={settings.MCP_SERVER_PORT})")
        track_background("mcp_http", start_http_server(port=settings.MCP_SERVER_PORT))

    # SKILL.md 文件同步：导入文件系统中已有的技能文件
    try:
        from src.skills.skill_md import skill_md_manager
        disk_skills = skill_md_manager.sync_from_directory()
        if disk_skills:
            for skill in disk_skills:
                existing = db.get_skill(skill.id)
                if not existing:
                    db.save_skill(skill)
                    logger.info(f"[STARTUP] Imported SKILL.md: {skill.name}")
            logger.info(f"[STARTUP] Synced {len(disk_skills)} SKILL.md files")
    except Exception as e:
        logger.warning(f"[STARTUP] SKILL.md sync skipped: {e}")

    # 一次性迁移：给旧技能步骤补充 type 字段（改造 3.6）
    # 幂等：已有 type 的步骤跳过；异常只记录 warning，不阻断启动
    try:
        from src.skills.skill_md import skill_md_manager
        db_skills, db_steps = skill_manager.migrate_legacy_step_types()
        md_files, md_steps = skill_md_manager.migrate_md_files_add_type()
        logger.info(
            f"[STARTUP] Migrated step types: "
            f"DB({db_skills} skills, {db_steps} steps), "
            f"MD({md_files} files, {md_steps} steps)"
        )
    except Exception as e:
        logger.warning(f"[STARTUP] Step type migration skipped: {e}")

    # 启动后台调度器 + Curator 周期性维护
    try:
        from src.engine.scheduler import scheduler as bg_scheduler
        from src.engine.skill_curator import skill_curator

        await bg_scheduler.start()
        await bg_scheduler.add_periodic(
            "skill_curator",
            skill_curator.run_curation_cycle,
            interval_seconds=7 * 24 * 3600,  # 7 天
        )
        # 首次启动 60 秒后运行一次 Curator（避免阻塞启动）
        await bg_scheduler.add_one_shot(
            "skill_curator_initial",
            skill_curator.run_curation_cycle,
            delay_seconds=60,
        )
        logger.info("[STARTUP] Background scheduler started with curator task")
    except Exception as e:
        logger.warning(f"[STARTUP] Scheduler init failed: {e}")

    logger.info("Hermes Office Synergy Agent started successfully")
    logger.info("飞书使用 WebSocket 长连接方式接收消息")


@app.on_event("shutdown")
async def shutdown_event():
    app.state.ready = False
    from src.engine.mcp_client import mcp_client_manager
    from src.engine.mcp_server import stop_http_server
    from src.engine.scheduler import scheduler as bg_scheduler
    from src.engine.checkpointer import close_checkpointer

    async def cleanup(name, operation):
        try:
            await operation()
        except Exception:
            logger.exception("Service cleanup failed: %s", name)

    await cleanup("mcp_client", mcp_client_manager.close)
    await cleanup("mcp_http", stop_http_server)
    await cleanup("scheduler", bg_scheduler.stop)
    try:
        feishu_websocket_service.stop()
    except Exception:
        logger.exception("Feishu cleanup failed")
    tasks = list(app.state.background_tasks.values())
    for task in tasks:
        if not task.done():
            task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    app.state.background_tasks.clear()
    await cleanup("checkpointer", close_checkpointer)
    await cleanup("plugins", close_plugins)
    logger.info("Hermes Office Synergy Agent shutting down")


@app.get("/")
async def root():
    return {"message": "Welcome to Hermes Office Synergy Agent"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/ready")
async def readiness_check():
    components = dict(component_status)
    integrations = dict(app.state.integrations)
    # Long-lived background tasks are only marked running when their service
    # reports that it has started, rather than when create_task() returns.
    if "feishu" in integrations and integrations["feishu"] == "starting" and feishu_websocket_service.is_running:
        integrations["feishu"] = "running"
    if "mcp_http" in integrations and integrations["mcp_http"] == "starting":
        from src.engine import mcp_server
        server = getattr(mcp_server, "_mcp_server_instance", None)
        if server is not None and server.started:
            integrations["mcp_http"] = "running"
    ready = app.state.ready and all(components.get(name) == "ready" for name in
        ("model_router", "memory_store", "skill_manager", "tool_executor"))
    degraded = any(value not in ("ready", "running") for value in (*components.values(), *integrations.values()))
    return JSONResponse(status_code=200 if ready else 503, content={
        "status": ("degraded" if degraded else "ready") if ready else "not_ready",
        "components": components, "integrations": integrations,
    })


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )
