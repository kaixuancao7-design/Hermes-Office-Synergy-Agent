"""Aggregate domain routers while preserving the public API prefix."""
from fastapi import APIRouter
from src.api.v1 import mcp, messages, skills, learning, permissions, audit

router = APIRouter(prefix="/api/v1")
router.include_router(mcp.router)
router.include_router(messages.router)
router.include_router(skills.router)
router.include_router(learning.router)
router.include_router(permissions.router)
router.include_router(audit.router)
