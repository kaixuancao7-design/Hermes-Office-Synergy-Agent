from fastapi import APIRouter
from typing import Dict, Any, Optional, List
from src.types import Message, Skill, UserProfile
from src.gateway.message_router import message_router
from src.gateway.im_adapter import im_adapter_manager, IMAdapterConfig
from src.skills.skill_manager import skill_manager
from src.engine.memory_manager import memory_manager
from src.utils import generate_id, get_timestamp
from src.exceptions import (
    SkillException,
    MemoryException,
    NotFoundException,
    ValidationException,
    IMException
)

router = APIRouter(prefix="/api/v1")


@router.post("/message")
async def send_message(message: Dict[str, Any]):
    user_id = message.get("user_id", "default_user")
    content = message.get("content", "")
    
    if not content:
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
        metadata=message.get("metadata")
    )
    
    response = message_router.route(msg)
    return {"response": response}


@router.post("/im/webhook/{adapter_type}")
async def im_webhook(adapter_type: str, payload: Dict[str, Any]):
    from src.utils import setup_logging
    from src.config import settings
    logger = setup_logging(settings.LOG_LEVEL)
    
    logger.info(f"Received webhook from {adapter_type}: {str(payload)[:500]}")
    
    adapter = im_adapter_manager.get_adapter(adapter_type)
    if not adapter:
        raise NotFoundException(
            message=f"适配器 {adapter_type} 不存在",
            detail=f"未找到类型为 {adapter_type} 的IM适配器",
            context={"adapter_type": adapter_type}
        )
    
    message = adapter.receive_message(payload)
    if not message:
        logger.info("Message ignored (adapter disabled or parsing failed)")
        return {"status": "ignored"}
    
    logger.info(f"Parsed message: user_id={message.user_id}, content={message.content[:100]}")
    
    response = message_router.route(message)
    logger.info(f"Generated response: {response[:100]}")
    
    try:
        adapter.send_message(Message(
            id=generate_id(),
            user_id=message.user_id,
            content=response,
            role="assistant",
            timestamp=get_timestamp()
        ))
    except Exception as e:
        raise IMException(
            message="发送消息失败",
            detail=str(e),
            context={"user_id": message.user_id, "adapter_type": adapter_type}
        )
    
    logger.info(f"Message sent successfully to user {message.user_id}")
    return {"status": "success", "response": response}


@router.get("/skills")
async def get_skills():
    skills = skill_manager.get_all_skills()
    return {"skills": [skill.model_dump() for skill in skills]}


@router.post("/skills")
async def create_skill(skill_data: Dict[str, Any]):
    user_id = skill_data.get("user_id", "default_user")
    name = skill_data.get("name", "")
    description = skill_data.get("description", "")
    steps = skill_data.get("steps", [])
    
    if not name:
        raise ValidationException(
            message="技能名称不能为空",
            detail="name 字段是必需的",
            context={"user_id": user_id}
        )
    
    if not steps:
        raise ValidationException(
            message="技能步骤不能为空",
            detail="steps 字段是必需的，至少需要一个步骤",
            context={"user_id": user_id, "skill_name": name}
        )
    
    skill = skill_manager.create_custom_skill(user_id, name, description, steps)
    return {"skill": skill.model_dump()}


@router.get("/skills/{skill_id}")
async def get_skill(skill_id: str):
    skill = skill_manager.get_skill(skill_id)
    if not skill:
        raise NotFoundException(
            message="技能不存在",
            detail=f"未找到ID为 {skill_id} 的技能",
            context={"skill_id": skill_id}
        )
    return {"skill": skill.model_dump()}


@router.post("/skills/{skill_id}/execute")
async def execute_skill(skill_id: str, user_id: str = "default_user"):
    skill = skill_manager.get_skill(skill_id)
    if not skill:
        raise NotFoundException(
            message="技能不存在",
            detail=f"未找到ID为 {skill_id} 的技能",
            context={"skill_id": skill_id, "user_id": user_id}
        )
    
    skill = skill_manager.apply_user_preferences(skill, user_id)
    
    results = []
    for step in skill.steps:
        results.append(f"{step.action}: {step.parameters}")
    
    return {"results": results}


@router.get("/user/{user_id}")
async def get_user_profile(user_id: str):
    profile = memory_manager.get_user_profile(user_id)
    if not profile:
        raise NotFoundException(
            message="用户不存在",
            detail=f"未找到ID为 {user_id} 的用户",
            context={"user_id": user_id}
        )
    return {"profile": profile.model_dump()}


@router.put("/user/{user_id}")
async def update_user_profile(user_id: str, updates: Dict[str, Any]):
    if not updates:
        raise ValidationException(
            message="更新内容不能为空",
            detail="updates 字段不能为空",
            context={"user_id": user_id}
        )
    
    memory_manager.update_user_profile(user_id, updates)
    return {"status": "success"}


@router.post("/adapters/register")
async def register_adapter(config: IMAdapterConfig):
    if not config.type:
        raise ValidationException(
            message="适配器类型不能为空",
            detail="type 字段是必需的",
            context={"config": config.dict()}
        )
    
    im_adapter_manager.register_adapter(config)
    return {"status": "success"}


@router.get("/memory/search")
async def search_memory(user_id: str, query: str):
    if not query:
        raise ValidationException(
            message="搜索关键词不能为空",
            detail="query 字段是必需的",
            context={"user_id": user_id}
        )
    
    results = memory_manager.search_long_term_memory(user_id, query)
    return {"results": [r.model_dump() for r in results]}


@router.post("/feedback")
async def submit_feedback(feedback: Dict[str, Any]):
    user_id = feedback.get("user_id", "default_user")
    original = feedback.get("original", "")
    corrected = feedback.get("corrected", "")
    context = feedback.get("context", "")
    
    if not original or not corrected:
        raise ValidationException(
            message="反馈内容不完整",
            detail="original 和 corrected 字段都是必需的",
            context={"user_id": user_id}
        )
    
    message_router.capture_correction(user_id, original, corrected, context)
    return {"status": "success"}
