"""Shared identity, path and synchronous bridge helpers for tools."""
import asyncio
import json
from contextvars import ContextVar
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

current_user = ContextVar("tool_current_user", default=None)


def run_sync(coroutine):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coroutine).result()


def parse_paths(value):
    if not value:
        return ["./data", "./output", "./workspace"]
    if isinstance(value, str):
        value = json.loads(value) if value.strip().startswith("[") else value.split(",")
    if not isinstance(value, (list, tuple)) or any(not isinstance(p, str) or not p.strip() for p in value):
        raise ValueError("Sandbox paths must be a nonempty list of directory paths")
    return [str(Path(p.strip()).resolve()) for p in value]


def within(path, roots):
    try:
        target = Path(path).resolve()
        return any(target.is_relative_to(Path(root).resolve()) for root in roots)
    except (ValueError, OSError, RuntimeError):
        return False


def authorize_tool(tool_id, params):
    from src.services.permission_service import permission_service
    user = current_user.get() or params.get("user_id")
    if not user:
        raise PermissionError("Tool execution requires a user identity")
    params = {**params, "user_id": user}
    if not permission_service.check_tool_permission(user, tool_id, "execute").allowed:
        raise PermissionError("No permission to execute tool")
    hazardous = tool_id == "code_execution" or (tool_id == "file_operations" and params.get("operation") in {"write", "append", "delete"})
    if hazardous and permission_service.get_user_role(user) != "admin":
        from src.data.database import db
        if not db.check_permission(user, "tool", tool_id, "execute"):
            raise PermissionError("This tool requires an explicit administrator grant")
    return params
