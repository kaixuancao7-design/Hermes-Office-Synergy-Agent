import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.gateway.message_graph import MessageGraph, MessageGraphUnavailable
from src.gateway.message_router import MessageRouter
from src.types import Message


def message(user="alice"):
    return Message(id=f"msg-{user}", user_id=user, content="hello", role="user", timestamp=1792531200)


@pytest.mark.parametrize("failure", ["missing", "build-error", "available"])
def test_graph_selection_does_not_recurse_or_rebuild(monkeypatch, failure):
    import src.gateway.message_graph as module
    router = object.__new__(MessageRouter)
    router._graph = None
    router._graph_initialization_attempted = False
    router._route_manual = AsyncMock(return_value="manual")
    graph = SimpleNamespace(_graph=None if failure == "missing" else object(), route=AsyncMock(return_value="graph"))
    factory = Mock(side_effect=RuntimeError("build failed")) if failure == "build-error" else Mock(return_value=graph)
    monkeypatch.setattr(module, "MessageGraph", factory)

    async def run():
        expected = "graph" if failure == "available" else "manual"
        assert await router._route_once(message()) == expected
        assert await router._route_once(message()) == expected

    asyncio.run(run())
    assert factory.call_count == 1
    assert router._route_manual.await_count == (0 if failure == "available" else 2)


def test_unavailable_graph_never_calls_router():
    graph = object.__new__(MessageGraph)
    graph._graph = None
    graph.router = SimpleNamespace(route=AsyncMock())
    with pytest.raises(MessageGraphUnavailable):
        asyncio.run(graph.route(message()))
    graph.router.route.assert_not_called()


@pytest.mark.parametrize("stage", ["setup", "recognize", "handle_skill", "save_response"])
def test_failed_graph_never_replays_even_after_restart(monkeypatch, tmp_path, stage):
    import src.gateway.message_router as module
    from src.data.database import Database
    monkeypatch.setattr(module, "db", Database(str(tmp_path / "requests.db")))
    performed = []

    async def operation(state):
        if stage in ("handle_skill", "save_response"):
            performed.append("sent")
        raise RuntimeError("uncertain external result")

    async def invoke(msg):
        return await MessageGraph._guard_node(stage, operation)({})

    async def run():
        first = object.__new__(MessageRouter)
        first._graph = SimpleNamespace(route=invoke)
        first._route_manual = AsyncMock()
        result = await first.route(message())
        assert "停止自动重试" in result
        # A new router and a new DB connection must still respect the durable claim.
        second = object.__new__(MessageRouter)
        second._route_once = AsyncMock()
        assert await second.route(message()) == result
        first._route_manual.assert_not_called()
        second._route_once.assert_not_called()
        import sqlite3
        with sqlite3.connect(module.db.db_path) as conn:
            assert conn.execute("SELECT status, stage FROM routing_requests").fetchone() == ("failed", stage)

    asyncio.run(run())
    assert len(performed) == (1 if stage in ("handle_skill", "save_response") else 0)


def test_concurrent_delivery_cached_response_and_identity(monkeypatch, tmp_path):
    import src.gateway.message_router as module
    from src.data.database import Database
    monkeypatch.setattr(module, "db", Database(str(tmp_path / "requests.db")))

    async def run():
        router = object.__new__(MessageRouter)
        started, release = asyncio.Event(), asyncio.Event()
        async def execute(msg):
            started.set()
            await release.wait()
            return "sent once"
        router._route_once = AsyncMock(side_effect=execute)
        pending = asyncio.create_task(router.route(message()))
        await started.wait()
        assert "尚未确认" in await router.route(message())
        release.set()
        assert await pending == "sent once"
        assert await router.route(message()) == "sent once"
        modified = message().model_copy(update={"content": "different"})
        assert "其他内容" in await router.route(modified)
        assert await router.route(message("bob")) == "sent once"
        assert router._route_once.await_count == 2

    asyncio.run(run())


def test_cancelled_request_remains_claimed(monkeypatch, tmp_path):
    import src.gateway.message_router as module
    from src.data.database import Database
    monkeypatch.setattr(module, "db", Database(str(tmp_path / "requests.db")))
    async def run():
        router = object.__new__(MessageRouter)
        started = asyncio.Event()
        async def execute(msg):
            started.set()
            await asyncio.Event().wait()
        router._route_once = AsyncMock(side_effect=execute)
        task = asyncio.create_task(router.route(message()))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert "尚未确认" in await router.route(message())
        router._route_once.assert_awaited_once()
    asyncio.run(run())


@pytest.mark.parametrize("outcome", ["exception", "empty"])
def test_react_does_not_fallback_after_agent_execution(monkeypatch, outcome):
    from src.engine import react_engine as module
    from src.engine import langchain_tools as bridge
    import langchain.agents
    engine = module.ReActEngine()
    monkeypatch.setattr(engine, "_check_langgraph_available", lambda: True)
    monkeypatch.setattr(bridge, "create_langchain_tools", lambda names: [SimpleNamespace(name="send")])
    monkeypatch.setattr(bridge, "create_chat_model", lambda **kwargs: object())
    invoke = AsyncMock(side_effect=RuntimeError("lost after send")) if outcome == "exception" else AsyncMock(return_value={"messages": []})
    monkeypatch.setattr(langchain.agents, "create_agent", lambda **kwargs: SimpleNamespace(ainvoke=invoke))
    monkeypatch.setattr(module, "get_tool_executor", lambda: SimpleNamespace(get_tools=lambda: ["send"]))
    monkeypatch.setattr(engine, "_run_with_manual_loop", AsyncMock())
    with pytest.raises(RuntimeError):
        asyncio.run(engine.run("alice", "send file"))
    engine._run_with_manual_loop.assert_not_called()
    invoke.assert_awaited_once()


def pipeline(monkeypatch, mode):
    import src.gateway.message_router as module
    import src.gateway.message_graph as graph_module
    from src.engine import checkpointer
    monkeypatch.setattr(checkpointer, "get_checkpointer", lambda: None)
    database = SimpleNamespace(save_message=Mock())
    monkeypatch.setattr(module, "db", database)
    monkeypatch.setattr(graph_module, "db", database)
    monkeypatch.setattr(module, "get_memory_store", lambda: None)
    monkeypatch.setattr(graph_module, "get_memory_store", lambda: None)
    router = object.__new__(MessageRouter)
    router.sessions = {}
    router.use_react_mode = False
    for name in ("_persist_session", "_store_message_memory", "_detect_implicit_correction", "_save_response_to_db"):
        monkeypatch.setattr(router, name, Mock())
    router._handle_intent = AsyncMock(side_effect=lambda user, *args: f"reply:{user}")
    router._handle_with_react = AsyncMock(return_value="react")
    monkeypatch.setattr(module.ppt_workflow, "is_awaiting_confirmation", AsyncMock(return_value=False))
    monkeypatch.setattr(module.ppt_workflow, "continue_workflow", AsyncMock(return_value=("ppt confirmed", {})))
    monkeypatch.setattr(module.trigger_matcher, "find_relevant_skill_with_near_misses", Mock(return_value=(None, [])))
    monkeypatch.setattr(module.intent_recognizer, "recognize", AsyncMock(return_value=module.Intent(type="question_answering", confidence=1, entities={})))
    call = router._route_manual if mode == "manual" else MessageGraph(router).route
    return router, module, call


@pytest.mark.parametrize("mode", ["manual", "graph"])
@pytest.mark.parametrize("scenario", ["question", "group", "file", "ppt", "skill", "permission"])
def test_pipeline_contract(monkeypatch, mode, scenario):
    router, module, call = pipeline(monkeypatch, mode)
    msg = message()
    expected = "reply:alice"
    if scenario == "group":
        msg.metadata = {"group": True}
        expected = ""
    elif scenario == "file":
        msg.metadata = {"file_name": "report.pdf"}
        module.trigger_matcher.find_relevant_skill_with_near_misses.side_effect = AssertionError("file must bypass skill matching")
    elif scenario == "ppt":
        module.ppt_workflow.is_awaiting_confirmation.return_value = True
        expected = "ppt confirmed"
    elif scenario in ("skill", "permission"):
        summary = SimpleNamespace(id="skill", name="skill", type="custom", steps=[])
        module.trigger_matcher.find_relevant_skill_with_near_misses.return_value = (summary, [])
        monkeypatch.setattr(module.trigger_matcher, "_calculate_match_score", lambda *args: .9)
        monkeypatch.setattr(module.trigger_matcher, "load_full_skill", lambda *args: summary)
        monkeypatch.setattr(module.skill_executor, "build_footer", lambda *args: "footer")
        execute = AsyncMock(return_value=SimpleNamespace(disclosure="disclosure", step_progress=[], response="skill reply"))
        if scenario == "permission":
            execute.side_effect = PermissionError("denied")
        monkeypatch.setattr(module.skill_executor, "execute_skill", execute)
        expected = "skill reply"
    if scenario == "permission":
        with pytest.raises((PermissionError, RuntimeError)):
            asyncio.run(call(msg))
        router._handle_intent.assert_not_called()
        router._handle_with_react.assert_not_called()
    else:
        result = asyncio.run(call(msg))
        assert expected in result if expected else result == ""
    if scenario in ("group", "file", "ppt", "skill", "permission"):
        module.intent_recognizer.recognize.assert_not_called()
    if scenario == "file":
        assert router._handle_intent.call_args.args[1].type == "document_analysis"


@pytest.mark.parametrize("mode", ["manual", "graph"])
def test_near_miss_suggestions_are_request_local(monkeypatch, mode):
    router, module, call = pipeline(monkeypatch, mode)
    module.trigger_matcher.find_relevant_skill_with_near_misses.side_effect = lambda query, user: (None, [user])
    monkeypatch.setattr(module.skill_executor, "build_near_miss_suggestion", lambda near: f" suggestion:{near[0]}")

    async def run():
        reached = 0
        both = asyncio.Event()
        async def recognize(query):
            nonlocal reached
            reached += 1
            if reached == 2:
                both.set()
            await both.wait()
            return module.Intent(type="question_answering", confidence=1, entities={})
        module.intent_recognizer.recognize.side_effect = recognize
        results = await asyncio.gather(call(message("alice")), call(message("bob")))
        assert results == ["reply:alice suggestion:alice", "reply:bob suggestion:bob"]
    asyncio.run(run())


def test_graph_checkpoints_namespace_same_message_id_by_user_and_source():
    graph = object.__new__(MessageGraph)
    configs = []
    async def invoke(state, config):
        configs.append(config["configurable"]["thread_id"])
        return {"response": "ok"}
    graph._graph = SimpleNamespace(ainvoke=invoke)
    async def run():
        for user, source in (("alice", "api"), ("bob", "api"), ("alice", "feishu")):
            msg = message(user)
            msg.metadata = {"message_id": "same-id", "source": source}
            assert await graph.route(msg) == "ok"
    asyncio.run(run())
    assert len(set(configs)) == 3


def test_api_retry_id_is_stable_without_colliding_database_message_ids(monkeypatch):
    from src.api.v1 import messages
    route = AsyncMock(return_value="ok")
    monkeypatch.setattr(messages, "message_router", SimpleNamespace(route=route))
    async def run():
        for user in ("alice", "bob", "alice"):
            await messages.send_message({"message_id": "shared-id", "content": "hello"}, user)
    asyncio.run(run())
    recorded = [call.args[0] for call in route.call_args_list]
    assert len({msg.id for msg in recorded}) == 3
    assert all(msg.metadata["message_id"] == "shared-id" for msg in recorded)
    assert [msg.user_id for msg in recorded] == ["alice", "bob", "alice"]
