import ast
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict
from unittest.mock import AsyncMock

import pytest
from fastapi import Depends, HTTPException, APIRouter
from src.types import Message
from src.utils import get_timestamp

ROOT = Path(__file__).resolve().parents[1]


def test_revocation_deletes_only_requested_permission(tmp_path, monkeypatch):
    from src.data.database import Database
    from src.services import permission_service as module
    database = Database(str(tmp_path / "permissions.db"))
    monkeypatch.setattr(module, "db", database)
    service = module.PermissionService()
    database.set_user_role("admin", "admin")
    database.grant_permission("p1", "skill", "one", "alice", "edit", "admin")
    database.grant_permission("p2", "skill", "two", "alice", "edit", "admin")
    assert not service.revoke_skill_permission("guest", "one", "alice", "edit")
    assert database.check_permission("alice", "skill", "one", "edit")
    assert service.revoke_skill_permission("admin", "one", "alice", "edit")
    assert not database.check_permission("alice", "skill", "one", "edit")
    assert database.check_permission("alice", "skill", "two", "edit")
    assert service.revoke_all_permissions("admin", "alice")
    assert not database.get_user_permissions("alice")
    database.save_pending_message_response("message", "reply")
    assert Database(str(tmp_path / "permissions.db")).get_pending_message_response("message") == "reply"
    database.mark_message_processed("message", "alice", "feishu")
    assert database.get_pending_message_response("message") is None
    assert database.is_message_processed("message")


def test_profile_memory_and_adapter_access_boundaries():
    tree = ast.parse((ROOT / "src/api/v1/messages.py").read_text(encoding="utf-8"))
    selected = [x for x in tree.body if isinstance(x, ast.AsyncFunctionDef)
                and x.name in {"get_user_profile", "update_user_profile", "search_memory", "register_adapter"}]
    def admin(actor):
        if actor != "admin":
            raise HTTPException(403)
    namespace = dict(router=APIRouter(), Depends=Depends, authenticated_user=lambda: "alice",
        require_admin=admin, Dict=Dict, Any=Any, IMAdapterConfig=Any,
        memory_manager=SimpleNamespace(get_user_profile=lambda user: SimpleNamespace(model_dump=lambda: {"user": user})))
    exec(compile(ast.Module(body=selected, type_ignores=[]), "endpoints", "exec"), namespace)
    async def run():
        result = await namespace["get_user_profile"]("alice", "alice")
        assert result["profile"]["user"] == "alice"
        for name, args in [("get_user_profile", ("bob", "alice")),
                           ("update_user_profile", ("bob", {"name": "x"}, "alice")),
                           ("search_memory", ("bob", "secret", "alice")),
                           ("register_adapter", (None, "alice"))]:
            with pytest.raises(HTTPException) as exc:
                await namespace[name](*args)
            assert exc.value.status_code == 403
    asyncio.run(run())


def test_feishu_callback_dispatch_and_completion_marker():
    tree = ast.parse((ROOT / "src/gateway/feishu_websocket.py").read_text(encoding="utf-8"))
    handler_class = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == "FeishuEventHandler")
    completed = set()
    pending = {}
    route = AsyncMock(return_value="response")
    logger = SimpleNamespace(**{name: lambda *args, **kwargs: None for name in ["info", "debug", "warning", "error"]})
    send_times = []
    def send(*args):
        send_times.append(time.monotonic())
        return len(send_times) > 1
    service = SimpleNamespace(_send_message_static=send)
    namespace = dict(asyncio=asyncio, json=json, time=time, datetime=datetime, Dict=Dict, Any=Any,
        logger=logger, Message=Message, get_timestamp=get_timestamp, safe_log_string=str,
        settings=SimpleNamespace(FEISHU_BOT_NAME=""), message_router=SimpleNamespace(route=route),
        FeishuWebSocketService=service, log_event=lambda *args, **kwargs: None,
        set_request_context=lambda **kwargs: None, clear_request_context=lambda: None,
        db=SimpleNamespace(get_pending_message_response=pending.get,
                           save_pending_message_response=lambda key, response: pending.update({key: response}),
                           is_message_processed=lambda key: key in completed,
                           mark_message_processed=lambda key, *args, **kwargs: completed.add(key)))
    exec(compile(ast.Module(body=[handler_class], type_ignores=[]), "feishu_handler", "exec"), namespace)
    async def run():
        handler = namespace["FeishuEventHandler"]()
        handler.main_loop = asyncio.get_running_loop()
        handler.MESSAGE_INTERVAL = .005
        payload = json.dumps({"header": {"event_type": "im.message.receive_v1"}, "event": {
            "message": {"message_id": "test", "content": json.dumps({"text": "hello"})},
            "sender": {"sender_type": "user", "sender_id": {"user_id": "alice"}}}}).encode()
        async def deliver():
            await asyncio.to_thread(handler.do_without_validation, payload)
            for _ in range(100):
                await asyncio.sleep(.001)
                if route.call_count and not handler.processing_message_ids:
                    break
        await deliver()
        assert route.call_count == 1
        assert not completed  # A failed send must not permanently suppress redelivery.
        first_slot = handler.last_message_time["alice"]
        await deliver()
        assert route.call_count == 1
        assert completed == {"test"}
        assert handler.last_message_time["alice"] - first_slot >= handler.MESSAGE_INTERVAL - 1e-8
        await deliver()
        assert route.call_count == 1
    asyncio.run(run())


def test_checkpointer_uses_runtime_loop_and_closes(tmp_path, monkeypatch):
    from src.engine import checkpointer as module
    monkeypatch.setattr(module, "CHECKPOINT_DB_PATH", str(tmp_path / "checkpoints.db"))
    module.reset_checkpointer()
    saver = module.get_checkpointer()  # Called synchronously during graph construction.
    if saver is None:
        pytest.skip("SQLite checkpoint optional dependency unavailable")
    async def run():
        from langgraph.graph import StateGraph, START, END
        from typing import TypedDict
        class State(TypedDict):
            value: int
        graph = StateGraph(State)
        graph.add_node("increment", lambda state: {"value": state["value"] + 1})
        graph.add_edge(START, "increment")
        graph.add_edge("increment", END)
        app = graph.compile(checkpointer=saver)
        config = {"configurable": {"thread_id": "regression"}}
        try:
            assert (await app.ainvoke({"value": 1}, config))["value"] == 2
            assert (await app.aget_state(config)).values["value"] == 2
            assert saver.loop is asyncio.get_running_loop()
        finally:
            await module.close_checkpointer()
        assert module._checkpointer is None
    asyncio.run(run())
