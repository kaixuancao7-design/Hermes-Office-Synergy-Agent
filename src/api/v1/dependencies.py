"""Shared application services for HTTP route modules."""
from fastapi import APIRouter, Query, Depends, HTTPException
from src.middleware.auth_middleware import authenticated_user, require_admin
from src.data.database import db
from typing import Dict, Any, Optional, List
from src.types import Message, Skill, UserProfile, SkillDraft, VerificationResult, AuditQueryResult
from src.gateway.message_router import message_router
from src.gateway.im_adapter import im_adapter_manager, IMAdapterConfig
from src.skills import skill_manager
from src.engine.memory_manager import memory_manager
from src.engine.learning_cycle import learning_cycle
from src.services.skill_verification import skill_verification_service
from src.services.permission_service import permission_service
from src.services.audit_log_service import audit_log_service
from src.utils import generate_id, get_timestamp
from src.exceptions import (
    SkillException,
    MemoryException,
    NotFoundException,
    ValidationException,
    IMException
)
from src.logging_config import get_logger

logger = get_logger("api")
