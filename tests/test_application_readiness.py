import asyncio
import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import src.plugins as plugins
from src.config import settings


@pytest.fixture
def application(monkeypatch):
    monkeypatch.setattr(settings, "LOG_OUTPUTS", "console")
    module = importlib.import_module("src.main")
    monkeypatch.setattr(module, "configure_logging", lambda: None)
    monkeypatch.setattr(module.app.state, "ready", False)
    monkeypatch.setattr(module.app.state, "background_tasks", {})
    monkeypatch.setattr(module.app.state, "integrations", {})
    monkeypatch.setattr(settings, "API_KEY_ENABLED", True)
    monkeypatch.setattr(settings, "API_KEYS", "")
    monkeypatch.setattr(settings, "API_KEY_USERS", "{}")
    monkeypatch.setattr(settings, "RATE_LIMIT_MAX_REQUESTS", 0)
    monkeypatch.setattr(plugins, "component_status", {})
    monkeypatch.setattr(module, "component_status", plugins.component_status)
    return module


def fake_plugins(monkeypatch):
    for registry in (plugins.MODEL_ROUTER_REGISTRY, plugins.MEMORY_STORE_REGISTRY,
                     plugins.SKILL_MANAGER_REGISTRY, plugins.TOOL_EXECUTOR_REGISTRY, plugins.IM_ADAPTER_REGISTRY):
        monkeypatch.setitem(registry, "test", lambda: SimpleNamespace(close=AsyncMock()))
    for name in ("model_router", "memory_store", "skill_manager", "tool_executor", "im_adapter"):
        monkeypatch.setattr(plugins, name, None)
    monkeypatch.setattr(plugins, "_check_vector_migration", lambda: None)
    monkeypatch.setattr(plugins, "_init_mcp_server", lambda: None)
    return {name: "test" for name in ("model_router", "memory_store", "skill_manager", "tool_executor", "im_adapter")}


@pytest.mark.parametrize("component,success", [("model_router", False), ("tool_executor", False), ("im_adapter", True)])
def test_unknown_plugin_type_and_partial_cleanup(monkeypatch, component, success):
    config = fake_plugins(monkeypatch)
    config[component] = "unknown"
    assert plugins.init_plugins(config) is success
    assert plugins.component_status[component] == "failed"
    instances = [getattr(plugins, name) for name in config if getattr(plugins, name) is not None]
    asyncio.run(plugins.close_plugins())
    assert all(getattr(plugins, name) is None for name in config)
    for instance in instances:
        instance.close.assert_awaited_once()


def test_required_constructor_failure(monkeypatch):
    config = fake_plugins(monkeypatch)
    def fail():
        raise RuntimeError("credential=secret")
    monkeypatch.setitem(plugins.MEMORY_STORE_REGISTRY, "test", fail)
    assert not plugins.init_plugins(config)
    assert plugins.component_status["memory_store"] == "failed"
    asyncio.run(plugins.close_plugins())


def test_probe_public_and_readiness_tracks_startup(application):
    # Do not enter TestClient context: run startup separately with mocked services.
    client = TestClient(application.app)
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 503
    application.component_status.update({name: "ready" for name in ("model_router", "memory_store", "skill_manager", "tool_executor")})
    application.app.state.ready = True
    assert client.get("/ready").json()["status"] == "ready"
    application.app.state.integrations["feishu"] = "failed"
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert "secret" not in response.text
    application.component_status["tool_executor"] = "failed"
    assert client.get("/ready").status_code == 503


def test_failed_startup_cleans_up_and_raises(application, monkeypatch):
    monkeypatch.setattr(application, "init_plugins", lambda: False)
    cleanup = AsyncMock()
    monkeypatch.setattr(application, "shutdown_event", cleanup)
    with pytest.raises(RuntimeError, match="Required plugin"):
        asyncio.run(application.startup_event())
    cleanup.assert_awaited_once()
    assert not application.app.state.ready


def test_background_failure_is_observable_and_shutdown_cancels(application, monkeypatch):
    async def run():
        async def failed():
            return False
        task = application.track_background("optional", failed())
        await task
        await asyncio.sleep(0)
        assert application.app.state.integrations["optional"] == "failed"
        waiting = application.track_background("waiting", asyncio.Event().wait())
        from src.engine.mcp_client import mcp_client_manager
        monkeypatch.setattr(mcp_client_manager, "close", AsyncMock())
        await application.shutdown_event()
        assert waiting.cancelled()
        assert not application.app.state.background_tasks
        assert not application.app.state.ready
    asyncio.run(run())


def test_successful_startup_marks_ready(application, monkeypatch):
    monkeypatch.setattr(application, "initialize_services", AsyncMock())
    asyncio.run(application.startup_event())
    assert application.app.state.ready
