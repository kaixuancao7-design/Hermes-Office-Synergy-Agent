import asyncio
import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from src.config import settings
from src.middleware.auth_middleware import APIKeyMiddleware, authenticated_user
from src.services.permission_service import PermissionService
from src.services.audit_log_service import AuditLogService
from src.plugins.tool_executors import FileOperationsTool, SandboxedToolExecutor


def test_paths_reject_siblings_traversal_and_links(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    tool = FileOperationsTool()
    assert tool._is_path_allowed("data/report.txt")
    assert not tool._is_path_allowed("data_private/secret.txt")
    assert not tool._is_path_allowed("data/../secret.txt")
    executor = object.__new__(SandboxedToolExecutor)
    executor.allowed_paths = [str(tmp_path / "data")]
    assert executor._is_path_allowed(str(tmp_path / "data/report.txt"))
    assert not executor._is_path_allowed(str(tmp_path / "data_private/secret.txt"))


def test_api_identity_is_bound_to_key(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY_ENABLED", True)
    monkeypatch.setattr(settings, "API_KEYS", "legacy")
    monkeypatch.setattr(settings, "API_KEY_USERS", json.dumps({"secret": "alice"}))
    app = FastAPI()
    app.add_middleware(APIKeyMiddleware)
    @app.get("/protected")
    def protected(actor=Depends(authenticated_user)):
        return {"actor": actor}
    with TestClient(app) as client:
        assert client.get("/protected").status_code == 401
        assert client.get("/protected", headers={"X-API-Key": "legacy"}).status_code == 401
        response = client.get("/protected?admin_id=admin", headers={"X-API-Key": "secret", "X-User-ID": "admin"})
        assert response.json() == {"actor": "alice"}
        monkeypatch.setattr(settings, "API_KEY_USERS", "{}")
        monkeypatch.setattr(settings, "API_KEYS", "")
        assert client.get("/protected", headers={"X-API-Key": "anything"}).status_code == 401


def test_tool_grant_requires_admin_even_when_not_hazardous(monkeypatch):
    service = PermissionService()
    monkeypatch.setattr(service, "get_user_role", lambda user: "guest")
    assert not service.grant_tool_permission("guest", "code_execution", "guest", "execute", False)


def test_audit_persistence_filters_integrity_and_export(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = str(tmp_path / "audit.db")
    service = AuditLogService(path)
    service.log_skill_delete("alice", "s1", "Example")
    service.log_permission_grant("admin", "skill", "s1", "bob", "execute")
    service = AuditLogService(path)
    assert service.verify_log_integrity()
    result = service.query_logs(operator_id="alice")
    assert result.total == 1
    assert result.logs[0].operation_type == "skill_delete"
    assert service.get_log_by_id(result.logs[0].id) is not None
    assert len(service.get_logs_by_type("permission_grant")) == 1
    assert service.export_logs("output/audit.json")
    assert not service.export_logs("output_private/audit.json")
    assert not service.export_logs("output/../outside.json")
    with sqlite3.connect(path) as conn:
        row = conn.execute("SELECT seq,payload FROM audit_entries ORDER BY seq LIMIT 1").fetchone()
        data = json.loads(row[1]); data["operator_id"] = "mallory"
        conn.execute("UPDATE audit_entries SET payload=? WHERE seq=?", (json.dumps(data), row[0]))
    assert not service.verify_log_integrity()


def test_api_role_and_execution_contracts(monkeypatch):
    # Load only endpoint definitions so tests never initialize model/IM clients.
    import ast
    import sys
    from pathlib import Path
    from fastapi import APIRouter, HTTPException
    from typing import Dict, Any
    from src.types import Skill
    from src.utils import get_timestamp
    source = Path(__file__).resolve().parents[1] / "src/api/v1/endpoints.py"
    tree = ast.Module(body=[node for name in ("skills.py", "permissions.py") for node in ast.parse((source.parent / name).read_text(encoding="utf-8")).body], type_ignores=[])
    selected = [node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                and node.name in {"get_user_role", "execute_skill", "set_user_role"}]
    calls = []
    permissions = SimpleNamespace(
        get_user_role=lambda user: "user",
        set_user_role=lambda actor, user, role, department: calls.append(actor) or actor == "admin")
    skill = Skill(id="s1", name="Example", description="Test", type="custom", steps=[],
                  trigger_patterns=[], metadata={}, created_at=get_timestamp(),
                  updated_at=get_timestamp(), created_by="alice")
    manager = SimpleNamespace(get_skill=lambda key: skill,
                              apply_user_preferences=lambda skill, user: skill,
                              can_execute_skill=lambda user, key: user == "alice")
    executor = SimpleNamespace(execute_skill=AsyncMock(return_value=SimpleNamespace(
        step_results=[{"success": True}], response="done", steps_executed=1, steps_failed=0)))
    monkeypatch.setitem(sys.modules, "src.engine.skill_executor", SimpleNamespace(skill_executor=executor))
    namespace = dict(router=APIRouter(), Depends=Depends, authenticated_user=authenticated_user,
                     HTTPException=HTTPException, Dict=Dict, Any=Any, Optional=__import__("typing").Optional,
                     permission_service=permissions, db=SimpleNamespace(get_user_department=lambda user: "sales"),
                     skill_manager=manager, ValidationException=HTTPException)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), "exec"), namespace)
    app = FastAPI()
    app.include_router(namespace["router"])
    app.dependency_overrides[authenticated_user] = lambda: "alice"
    with TestClient(app) as client:
        assert client.get("/users/alice/role").json()["role"] == "user"
        assert client.get("/users/alice/role").json()["department"] == "sales"
        response = client.post("/skills/s1/execute?user_id=admin&query=hello")
        assert response.status_code == 200
        assert response.json()["response"] == "done"
        assert executor.execute_skill.call_args.args[1:] == ("hello", "alice")
        manager.can_execute_skill = lambda *args: False
        assert client.post("/skills/s1/execute").status_code == 403
        assert executor.execute_skill.call_count == 1
    # Directly verify the role endpoint forwards the authenticated actor.
    permissions.set_user_role = lambda actor, *args: calls.append(actor) or True
    asyncio.run(namespace["set_user_role"]("bob", "user", "alice", None))
    assert calls == ["alice"]
