from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional, List
from src.types import Message, Skill, UserProfile
from src.gateway.message_router import message_router
from src.gateway.im_adapter import im_adapter_manager, IMAdapterConfig
from src.skills.skill_manager import skill_manager
from src.engine.memory_manager import memory_manager
from src.utils import generate_id, get_timestamp

router = APIRouter(prefix="/api/v1")


@router.post("/message")
async def send_message(message: Dict[str, Any]):
    try:
        msg = Message(
            id=generate_id(),
            user_id=message.get("user_id", "default_user"),
            content=message.get("content", ""),
            role="user",
            timestamp=get_timestamp(),
            metadata=message.get("metadata")
        )
        
        response = message_router.route(msg)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/im/webhook/{adapter_type}")
async def im_webhook(adapter_type: str, payload: Dict[str, Any]):
    from src.utils import setup_logging
    from src.config import settings
    logger = setup_logging(settings.LOG_LEVEL)
    
    try:
        logger.info(f"Received webhook from {adapter_type}: {str(payload)[:500]}")
        
        adapter = im_adapter_manager.get_adapter(adapter_type)
        if not adapter:
            logger.error(f"Adapter {adapter_type} not found")
            raise HTTPException(status_code=404, detail=f"Adapter {adapter_type} not found")
        
        message = adapter.receive_message(payload)
        if not message:
            logger.info("Message ignored (adapter disabled or parsing failed)")
            return {"status": "ignored"}
        
        logger.info(f"Parsed message: user_id={message.user_id}, content={message.content[:100]}")
        
        response = message_router.route(message)
        logger.info(f"Generated response: {response[:100]}")
        
        adapter.send_message(Message(
            id=generate_id(),
            user_id=message.user_id,
            content=response,
            role="assistant",
            timestamp=get_timestamp()
        ))
        
        logger.info(f"Message sent successfully to user {message.user_id}")
        return {"status": "success", "response": response}
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills")
async def get_skills():
    try:
        skills = skill_manager.get_all_skills()
        return {"skills": [skill.model_dump() for skill in skills]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills")
async def create_skill(skill_data: Dict[str, Any]):
    try:
        user_id = skill_data.get("user_id", "default_user")
        name = skill_data.get("name", "")
        description = skill_data.get("description", "")
        steps = skill_data.get("steps", [])
        
        if not name or not steps:
            raise HTTPException(status_code=400, detail="Name and steps are required")
        
        skill = skill_manager.create_custom_skill(user_id, name, description, steps)
        return {"skill": skill.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills/{skill_id}")
async def get_skill(skill_id: str):
    try:
        skill = skill_manager.get_skill(skill_id)
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")
        return {"skill": skill.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/{skill_id}/execute")
async def execute_skill(skill_id: str, user_id: str = "default_user"):
    try:
        skill = skill_manager.get_skill(skill_id)
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")
        
        skill = skill_manager.apply_user_preferences(skill, user_id)
        
        results = []
        for step in skill.steps:
            results.append(f"{step.action}: {step.parameters}")
        
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}")
async def get_user_profile(user_id: str):
    try:
        profile = memory_manager.get_user_profile(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="User not found")
        return {"profile": profile.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/user/{user_id}")
async def update_user_profile(user_id: str, updates: Dict[str, Any]):
    try:
        memory_manager.update_user_profile(user_id, updates)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/adapters/register")
async def register_adapter(config: IMAdapterConfig):
    try:
        im_adapter_manager.register_adapter(config)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/search")
async def search_memory(user_id: str, query: str):
    try:
        results = memory_manager.search_long_term_memory(user_id, query)
        return {"results": [r.model_dump() for r in results]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback")
async def submit_feedback(feedback: Dict[str, Any]):
    try:
        user_id = feedback.get("user_id", "default_user")
        original = feedback.get("original", "")
        corrected = feedback.get("corrected", "")
        context = feedback.get("context", "")
        
        message_router.capture_correction(user_id, original, corrected, context)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
