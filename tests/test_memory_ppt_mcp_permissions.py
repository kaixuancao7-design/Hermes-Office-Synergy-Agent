"""Regression coverage using isolated SQLite files and the real MCP ASGI transport."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    from src.data.database import Database, db
    database = Database(str(tmp_path / "agent.db"))
    monkeypatch.setattr(db, "db_path", database.db_path)
    return database


def test_default_memory_persistence_isolation_and_profiles(isolated_db, monkeypatch):
    import src.plugins as plugins
    from src.plugins.memory_stores import MEMORY_STORE_REGISTRY, SimpleMemoryStore, InMemoryStore
    from src.engine.memory_manager import memory_manager
    from src.types import MemoryEntry

    store = MEMORY_STORE_REGISTRY["simple"](isolated_db)
    monkeypatch.setattr(plugins, "memory_store", store)
    assert callable(InMemoryStore().store)
    assert memory_manager.store_memory("alice", "项目进度短期", "short")
    assert memory_manager.store_memory("alice", "项目长期经验", "long")
    assert memory_manager.store_memory("bob", "项目机密", "long")
    assert [m.content for m in memory_manager.search_long_term_memory("alice", "项目")] == ["项目长期经验"]
    entry = MemoryEntry(id="group-memory", user_id="alice", type="long", content="会议纪要",
                        timestamp=1, tags=["会议"], group_id="group-1", group_name="研发")
    isolated_db.save_memory(entry)
    assert isolated_db.get_memory_by_type("alice", "long")[-1].group_id == "group-1"
    assert isolated_db.get_memories_by_tag("会议", "alice")[0].group_name == "研发"
    assert store.search_memory("alice", "会议")[0].group_id == "group-1"
    assert store.add_memory("alice", entry)
    assert store.store("ppt:alice", {"phase": "confirm"})
    reopened = SimpleMemoryStore(isolated_db)
    assert reopened.retrieve("ppt:alice") == {"phase": "confirm"}
    assert reopened.get_memory_count("alice") == 3
    assert not reopened.delete_memory("bob", entry.id)
    assert reopened.retrieve("memory:alice:group-memory").group_id == "group-1"
    assert reopened.delete_memory("alice", entry.id)
    assert reopened.retrieve("memory:alice:group-memory") is None
    with pytest.raises(PermissionError):
        reopened.add_memory("bob", entry)
    foreign = entry.model_copy(update={"user_id": "bob", "id": memory_manager.get_user_memories("alice")[0].id})
    with pytest.raises(PermissionError):
        reopened.add_memory("bob", foreign)
    assert reopened.retrieve(f"memory:bob:{foreign.id}") is None
    profile = memory_manager.update_user_profile("alice", {"writing_style": "简洁", "preferences": {"language": "zh"}})
    assert profile.writing_style == "简洁"
    assert memory_manager.get_user_profile("alice").preferences == {"language": "zh"}
    with pytest.raises(ValueError):
        memory_manager.update_user_profile("alice", {"role": "admin"})
    assert memory_manager.get_user_profile("alice").role == "guest"


def test_legacy_memory_migration_preserves_entries(tmp_path):
    import sqlite3
    from src.data.database import Database
    from src.plugins.memory_stores import SimpleMemoryStore
    path = str(tmp_path / "legacy.db")
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE memory(id TEXT PRIMARY KEY,user_id TEXT,type TEXT,content TEXT,embedding TEXT,timestamp INTEGER,tags TEXT)")
        conn.execute("INSERT INTO memory VALUES(?,?,?,?,?,?,?)", ("old", "alice", "long", "历史数据", "[0.1]", 1, "['旧标签']"))
    database = Database(path)
    entries = SimpleMemoryStore(database).search_memory("alice", "历史")
    assert len(entries) == 1 and entries[0].tags == ["旧标签"]
    assert entries[0].group_id == "default" and entries[0].embedding == [0.1]
    Database(path)  # Startup migrations remain idempotent.
    assert len(database.get_memory_by_type("alice", "long")) == 1


def test_department_scopes_follow_membership_and_validate_grants(isolated_db):
    from src.services.permission_service import permission_service as service
    isolated_db.set_user_role("admin", "admin")
    isolated_db.set_user_role("alice", "user", "engineering")
    isolated_db.set_user_role("bob", "user", "sales")
    isolated_db.set_user_role("developer", "developer", "engineering")
    assert not service.grant_department_permission("alice", "skill", "s1", "engineering", ["edit"])
    assert not service.grant_department_permission("admin", "skill", "invalid", "engineering", ["edit", "unknown"])
    assert not isolated_db.get_resource_permissions("skill", "invalid")
    assert not service.grant_department_permission("admin", "skill", "s1", "engineering", [])
    assert service.grant_department_permission("admin", "skill", "s1", "engineering", ["edit"])
    assert service.check_skill_permission("alice", "s1", "edit").allowed
    assert not service.check_skill_permission("bob", "s1", "edit").allowed
    assert not isolated_db.check_permission("engineering", "skill", "s1", "edit")
    assert not isolated_db.check_permission("alice", "skill", "other", "edit")
    assert service.get_user_permissions("alice")["explicit_permissions"][0]["scope_type"] == "department"
    isolated_db.set_user_role("alice", "user", "sales")
    assert not service.check_skill_permission("alice", "s1", "edit").allowed
    assert not service.get_user_permissions("alice")["explicit_permissions"]
    assert not service.grant_skill_permission("developer", "s2", "bob", "edit", "all")
    assert not service.grant_skill_permission("admin", "s2", "bob", "edit", "department")
    assert service.grant_skill_permission("admin", "s2", "bob", "edit", "all")
    assert isolated_db.check_permission("alice", "skill", "s2", "edit")
    isolated_db.revoke_permissions("bob")
    assert isolated_db.check_permission("alice", "skill", "s2", "edit")
    from src.tools.runtime import authorize_tool
    with pytest.raises(PermissionError):
        authorize_tool("code_execution", {"user_id": "bob"})
    assert service.grant_department_permission("admin", "tool", "code_execution", "sales", ["execute"])
    assert authorize_tool("code_execution", {"user_id": "bob"})["user_id"] == "bob"
    isolated_db.set_user_role("bob", "user", "engineering")
    with pytest.raises(PermissionError):
        authorize_tool("code_execution", {"user_id": "bob"})


def test_interactive_ppt_confirmation_restart_and_cancel(tmp_path, monkeypatch):
    from src.engine import checkpointer
    from src.engine.ppt_workflow import PPTWorkflow
    monkeypatch.setattr(checkpointer, "CHECKPOINT_DB_PATH", str(tmp_path / "checkpoints.db"))
    checkpointer.reset_checkpointer()

    async def run():
        workflow = PPTWorkflow()
        try:
            prompt, state = await workflow.start_workflow("alice", "ppt_generation", "季度报告\n\n进度\n已完成核心开发")
            assert "回复" in prompt and state["awaiting_confirmation"]
            assert await workflow.is_awaiting_confirmation("alice")
            assert not await workflow.is_awaiting_confirmation("bob")
            prompt, _ = await workflow.continue_workflow("alice", "无法识别")
            assert "无法识别" in prompt
            prompt, _ = await workflow.continue_workflow("alice", "详细")
            assert prompt and await workflow.is_awaiting_confirmation("alice")
            await checkpointer.close_checkpointer()
            workflow = PPTWorkflow()  # Restores state from SQLite without an in-memory context.
            assert await workflow.is_awaiting_confirmation("alice")
            response, state = await workflow.continue_workflow("alice", "是")
            assert "PPT" in response
            assert not state.get("error_message")
            assert Path(state["output_path"]).is_file()
            from pptx import Presentation
            assert len(Presentation(state["output_path"]).slides) >= 3
            assert not await workflow.is_awaiting_confirmation("alice")
            assert await workflow.get_state("alice") == "completed"
            await workflow.start_workflow("alice", "ppt_generation", "取消测试")
            response, state = await workflow.continue_workflow("alice", "取消")
            assert "取消" in response and not state["output_path"]
            assert await workflow.get_state("alice") == "cancelled"
        finally:
            await checkpointer.close_checkpointer()

    asyncio.run(run())


def test_pending_ppt_bypasses_intent_and_skill_matching(monkeypatch):
    from src.engine.ppt_workflow import ppt_workflow
    from src.gateway.message_graph import MessageGraph
    # Node methods do not need model or router initialization.
    router = object.__new__(MessageGraph)
    monkeypatch.setattr(ppt_workflow, "is_awaiting_confirmation", AsyncMock(return_value=True))
    monkeypatch.setattr(ppt_workflow, "continue_workflow", AsyncMock(return_value=("已取消", {})))

    async def run():
        state = {"user_id": "alice", "content": "取消", "metadata": {}}
        await router._skill_prematch_node(state)
        await router._recognize_node(state)
        assert router._route_intent(state) == "handle_ppt"
        assert (await router._handle_ppt_node(state))["response"] == "已取消"

    asyncio.run(run())


def test_mcp_http_real_protocol_auth_and_identity(monkeypatch):
    from starlette.testclient import TestClient
    from src.engine import mcp_server as module
    from src.config import settings
    from src.tools.runtime import current_user
    import src.plugins as plugins
    from src.engine.memory_manager import memory_manager
    monkeypatch.setattr(settings, "API_KEY_USERS", json.dumps({"alice-key": "alice", "bob-key": "bob"}))
    seen = []
    memory_users = []

    def search_memory(user, query, limit):
        memory_users.append(user)
        return []

    monkeypatch.setattr(memory_manager, "search_long_term_memory", search_memory)
    monkeypatch.setattr(memory_manager, "get_user_profile", lambda user: SimpleNamespace(preferences={"owner": user}))

    def execute(tool, parameters):
        seen.append((current_user.get(), parameters["user_id"]))
        return {"success": True, "user_id": parameters["user_id"]}

    monkeypatch.setattr(plugins, "tool_executor", SimpleNamespace(execute=execute))
    app = module.create_http_app()
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        headers = {"accept": "application/json, text/event-stream", "X-API-Key": "alice-key"}
        def rpc(method, params, key="alice-key"):
            return client.post("/mcp", headers={**headers, "X-API-Key": key},
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        assert rpc("tools/list", {}, "invalid").status_code == 401
        assert client.get("/mcp").status_code == 401
        initialized = rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "regression", "version": "1"}})
        assert initialized.status_code == 200 and "serverInfo" in initialized.json()["result"]
        listed = rpc("tools/list", {})
        assert "code_execution" in {tool["name"] for tool in listed.json()["result"]["tools"]}
        for key in ("alice-key", "bob-key"):
            result = rpc("tools/call", {"name": "code_execution", "arguments": {"code": "print(1)"}}, key)
            assert result.status_code == 200 and not result.json()["result"].get("isError")
        assert seen == [("alice", "alice"), ("bob", "bob")]
        result = rpc("tools/call", {"name": "memory_search", "arguments": {"user_id": "bob", "query": "secret"}})
        assert result.status_code == 200 and memory_users == ["alice"]
        result = rpc("tools/call", {"name": "get_user_preferences", "arguments": {"user_id": "bob"}})
        content = json.loads(result.json()["result"]["content"][0]["text"])
        assert content["preferences"] == {"owner": "alice"}
        monkeypatch.setattr(settings, "API_KEY_USERS", '["alice-key"]')
        assert rpc("tools/list", {}).status_code == 401
        assert current_user.get() is None


def test_mcp_background_server_stops_and_cleans_up(monkeypatch):
    import uvicorn
    from src.engine import mcp_server as module
    server = SimpleNamespace(should_exit=False, started=False)

    async def serve():
        server.started = True
        while not server.should_exit:
            await asyncio.sleep(0.001)

    server.serve = serve
    monkeypatch.setattr(uvicorn, "Server", lambda config: server)

    async def run():
        task = asyncio.create_task(module.start_http_server(port=0))
        while not server.started:
            await asyncio.sleep(0.001)
        assert not await module.start_http_server(port=0)
        await module.stop_http_server()
        assert await task
        assert module._mcp_server_instance is None and module._mcp_server_task is None

    asyncio.run(run())
