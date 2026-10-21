"""Mcp HTTP endpoints; included under /api/v1."""
from fastapi import APIRouter
from src.api.v1.dependencies import (
    Depends, authenticated_user, require_admin
)

router = APIRouter()


@router.get("/mcp/client/status")
async def get_mcp_client_status(actor: str = Depends(authenticated_user)):
    """管理员查看连接状态与工具 ID，不返回连接配置或凭证。"""
    require_admin(actor)
    from src.engine.mcp_client import mcp_client_manager
    from src.config import settings
    return {"enabled": settings.MCP_CLIENT_ENABLED, "servers": dict(mcp_client_manager.status),
            "tools": mcp_client_manager.catalog()}


@router.get("/mcp/client/tools")
async def get_mcp_client_tools(actor: str = Depends(authenticated_user)):
    """只返回当前认证用户可执行的外部工具。"""
    from src.engine.mcp_client import mcp_client_manager
    return {"tools": mcp_client_manager.descriptors(actor)}
