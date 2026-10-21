"""Messages HTTP endpoints; included under /api/v1."""
from fastapi import APIRouter
from src.api.v1.dependencies import (
    Any, Depends, Dict, IMAdapterConfig, IMException, Message, NotFoundException, ValidationException, authenticated_user, generate_id, get_timestamp, im_adapter_manager, logger, memory_manager, message_router, require_admin
)

router = APIRouter()


@router.post("/message")
async def send_message(message: Dict[str, Any], actor: str = Depends(authenticated_user)):
    request_id = message.get("message_id", generate_id())
    user_id = actor
    content = message.get("content", "")

    logger.info(f"[API_MESSAGE] ========== API消息入口 ==========")
    logger.info(f"[API_MESSAGE] request_id={request_id}, user_id={user_id}, content={content[:50]}...")

    if not content:
        logger.warning(f"[API_MESSAGE] 内容为空: request_id={request_id}")
        raise ValidationException(
            message="内容不能为空",
            detail="message.content 字段是必需的",
            context={"user_id": user_id}
        )

    msg = Message(
        id=generate_id(),
        user_id=user_id,
        content=content,
        role="user",
        timestamp=get_timestamp(),
        metadata={**(message.get("metadata") or {}), "request_id": request_id,
                  "message_id": request_id, "source": "api"}
    )

    logger.info(f"[API_MESSAGE] 消息对象已创建，开始路由: request_id={request_id}")
    response = await message_router.route(msg)
    logger.info(f"[API_MESSAGE] 路由完成: request_id={request_id}, response_length={len(response)}")

    return {"response": response}


@router.post("/im/webhook/{adapter_type}")
async def im_webhook(adapter_type: str, payload: Dict[str, Any]):
    request_id = generate_id()
    logger.info(f"[API_WEBHOOK] ========== Webhook入口 ==========")
    logger.info(f"[API_WEBHOOK] request_id={request_id}, adapter_type={adapter_type}, payload={str(payload)[:200]}...")

    adapter = im_adapter_manager.get_adapter(adapter_type)
    if not adapter:
        logger.warning(f"[API_WEBHOOK] 适配器不存在: request_id={request_id}, adapter_type={adapter_type}")
        raise NotFoundException(
            message=f"适配器 {adapter_type} 不存在",
            detail=f"未找到类型为 {adapter_type} 的IM适配器",
            context={"adapter_type": adapter_type}
        )

    message = adapter.receive_message(payload)
    if not message:
        logger.info(f"[API_WEBHOOK] 消息被忽略: request_id={request_id}")
        return {"status": "ignored"}

    logger.info(f"[API_WEBHOOK] 消息解析成功: request_id={request_id}, user_id={message.user_id}, content={message.content[:50]}")

    response = await message_router.route(message)
    logger.info(f"[API_WEBHOOK] 响应生成完成: request_id={request_id}, response_length={len(response)}")

    try:
        await adapter.send_message(Message(
            id=generate_id(),
            user_id=message.user_id,
            content=response,
            role="assistant",
            timestamp=get_timestamp()
        ))
        logger.info(f"[API_WEBHOOK] 消息发送成功: request_id={request_id}, user_id={message.user_id}")
    except Exception as e:
        logger.error(f"[API_WEBHOOK] 发送消息失败: request_id={request_id}, error={str(e)}")
        raise IMException(
            message="发送消息失败",
            detail=str(e),
            context={"user_id": message.user_id, "adapter_type": adapter_type}
        )

    return {"status": "success", "response": response}


@router.get("/user/{user_id}")
async def get_user_profile(user_id: str, actor: str = Depends(authenticated_user)):
    if actor != user_id:
        require_admin(actor)
    profile = memory_manager.get_user_profile(user_id)
    if not profile:
        raise NotFoundException(
            message="用户不存在",
            detail=f"未找到ID为 {user_id} 的用户",
            context={"user_id": user_id}
        )
    return {"profile": profile.model_dump()}


@router.put("/user/{user_id}")
async def update_user_profile(user_id: str, updates: Dict[str, Any], actor: str = Depends(authenticated_user)):
    if actor != user_id:
        require_admin(actor)
    if not updates:
        raise ValidationException(
            message="更新内容不能为空",
            detail="updates 字段不能为空",
            context={"user_id": user_id}
        )

    try:
        memory_manager.update_user_profile(user_id, updates)
    except ValueError as exc:
        raise ValidationException(message="用户资料参数无效", detail=str(exc))
    return {"status": "success"}


@router.post("/adapters/register")
async def register_adapter(config: IMAdapterConfig, actor: str = Depends(authenticated_user)):
    require_admin(actor)
    if not config.type:
        raise ValidationException(
            message="适配器类型不能为空",
            detail="type 字段是必需的",
            context={"config": config.model_dump()}
        )

    im_adapter_manager.register_adapter(config)
    return {"status": "success"}


@router.get("/memory/search")
async def search_memory(user_id: str, query: str, actor: str = Depends(authenticated_user)):
    if actor != user_id:
        require_admin(actor)
    if not query:
        raise ValidationException(
            message="搜索关键词不能为空",
            detail="query 字段是必需的",
            context={"user_id": user_id}
        )

    results = memory_manager.search_long_term_memory(user_id, query)
    return {"results": [r.model_dump() for r in results]}
