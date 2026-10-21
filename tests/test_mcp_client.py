"""Outbound MCP regression tests, including real local Stdio and HTTP servers."""
import asyncio
import json
import sys
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool


@pytest.fixture
def client_setup(tmp_path, monkeypatch):
    from src.config import settings
    from src.data.database import Database, db
    from src.engine import mcp_client as module
    database = Database(str(tmp_path / "agent.db"))
    monkeypatch.setattr(db, "db_path", database.db_path)
    database.set_user_role("admin", "admin", "engineering")
    database.set_user_role("alice", "user", "engineering")
    database.set_user_role("bob", "user", "sales")
    manager = module.MCPClientManager()
    monkeypatch.setattr(module, "mcp_client_manager", manager)
    monkeypatch.setattr(settings, "MCP_CLIENT_ENABLED", True)
    path = tmp_path / "servers.json"
    monkeypatch.setattr(settings, "MCP_SERVERS_CONFIG", str(path))

    def configure(servers):
        path.write_text(json.dumps({"mcpServers": servers}), encoding="utf-8")

    return manager, database, configure


def fake_server(monkeypatch, *, delay=0, error=False):
    from src.engine import mcp_client as module
    schema = {"type": "object", "properties": {"payload": {"$ref": "#/$defs/Payload"}},
              "required": ["payload"], "additionalProperties": False,
              "$defs": {"Payload": {"type": "object", "properties": {"values": {"type": "array", "items": {"type": "integer"}}},
                                    "required": ["values"], "additionalProperties": False}}}
    calls, lifecycle = [], []

    @asynccontextmanager
    async def connect(config):
        lifecycle.append("open")
        async def list_tools(cursor=None):
            if cursor is None:
                return ListToolsResult(tools=[Tool(name="echo", description="Echo structured data", inputSchema=schema)], nextCursor="page2")
            return ListToolsResult(tools=[Tool(name="hidden", inputSchema={"type": "object"})])
        async def call_tool(name, arguments):
            calls.append((name, arguments))
            await asyncio.sleep(delay)
            return CallToolResult(content=[TextContent(type="text", text=json.dumps(arguments))],
                                  structuredContent=arguments, isError=error)
        try:
            yield SimpleNamespace(list_tools=list_tools, call_tool=call_tool)
        finally:
            lifecycle.append("close")

    monkeypatch.setattr(module, "open_session", connect)
    return calls, lifecycle


def test_discovery_schema_isolation_and_department_permission(client_setup, monkeypatch):
    manager, database, configure = client_setup
    calls, lifecycle = fake_server(monkeypatch)
    configure({"one": {"transport": "stdio", "command": "unused", "allowed_tools": ["echo"]},
               "two": {"transport": "stdio", "command": "unused", "allowed_tools": ["echo"], "allowed_users": ["alice"]}})
    async def run():
        assert await manager.refresh() == {"one": "ready:1", "two": "ready:1"}
        assert {t["name"] for t in manager.descriptors("admin")} == {"mcp__one__echo"}
        assert manager.descriptors("alice") == []
        assert not (await manager.call("mcp__one__echo", {}, "alice"))["success"]
        from src.services.permission_service import permission_service
        assert permission_service.grant_department_permission("admin", "tool", "mcp__one__echo", "engineering", ["execute"])
        descriptor = manager.descriptors("alice")[0]
        assert "$defs" in descriptor["inputSchema"]
        assert manager.descriptors("bob") == []
        assert not (await manager.call(descriptor["name"], {"payload": {"values": ["invalid"]}}, "alice"))["success"]
        assert not calls
        result = await manager.call(descriptor["name"], {"payload": {"values": [1, 2]}, "user_id": "bob"}, "alice")
        assert result["success"] and calls == [("echo", {"payload": {"values": [1, 2]}})]
        database.set_user_role("alice", "user", "sales")
        assert manager.descriptors("alice") == []
        assert not (await manager.call(descriptor["name"], {"payload": {"values": [1]}}, "alice"))["success"]
        await manager.close()
        assert manager.descriptors("admin") == []
    asyncio.run(run())
    assert lifecycle.count("open") == lifecycle.count("close")


def test_native_json_and_skill_tool_integration(client_setup, monkeypatch):
    manager, database, configure = client_setup
    calls, _ = fake_server(monkeypatch)
    configure({"demo": {"transport": "stdio", "command": "unused", "allowed_tools": ["echo"]}})
    asyncio.run(manager.refresh())
    import src.plugins as plugins
    from src.plugins.tool_executors import BasicToolExecutor, SandboxedToolExecutor
    from src.engine.langchain_tools import create_langchain_tools, load_react_system_prompt, get_tool_descriptors_mcp
    from src.tools.runtime import current_user
    for cls in (BasicToolExecutor, SandboxedToolExecutor):
        monkeypatch.setattr(cls, "_initialize_feishu_client", lambda self: None)
        monkeypatch.setattr(cls, "_initialize_memory_store", lambda self: None)
    executor = SandboxedToolExecutor()
    monkeypatch.setattr(plugins, "tool_executor", executor)
    name = "mcp__demo__echo"
    token = current_user.set("admin")
    try:
        assert name in executor.get_tools()
        assert name in BasicToolExecutor().get_tools()
        prompt = load_react_system_prompt(available_tools=[name])
        assert '"$defs"' in prompt and name in prompt
        assert "inputSchema" in get_tool_descriptors_mcp([name])[0]
        tool = create_langchain_tools([name])[0]

        async def run():
            payload = {"payload": {"values": [3]}}
            assert json.loads(await tool.ainvoke(payload))["success"]
            from src.engine.react_engine import react_engine
            result = await react_engine._execute_tool(executor, name, "query", "admin", {"file_key": "unrelated"}, payload)
            assert result["success"]
            from src.engine.skill_executor import SkillStepExecutor
            from src.types import SkillStep
            steps = SkillStepExecutor()
            steps._tool_executor = executor
            step = SkillStep(id="remote", action=name, type="tool", parameters=payload)
            outputs = {}
            await steps._execute_tool_step(step, "context", "admin", {"file_key": "unrelated"}, outputs)
            assert outputs["remote"]["success"]
        asyncio.run(run())
        assert len(calls) == 3
        current_user.set("alice")
        assert name not in executor.get_tools()
        assert not executor.execute(name, {"user_id": "admin", "payload": {"values": [4]}})["success"]
    finally:
        current_user.reset(token)


@pytest.mark.parametrize("delay,error", [(0, True), (0.15, False)])
def test_remote_errors_timeout_and_cleanup(client_setup, monkeypatch, delay, error):
    manager, _, configure = client_setup
    calls, lifecycle = fake_server(monkeypatch, delay=delay, error=error)
    configure({"demo": {"transport": "stdio", "command": "unused", "timeout": 0.03}})
    async def run():
        await manager.refresh()
        result = await manager.call("mcp__demo__echo", {"payload": {"values": [1]}}, "admin")
        assert result["success"] is False
    asyncio.run(run())
    assert len(calls) == 1  # Failures never cause an automatic write retry.
    assert lifecycle.count("open") == lifecycle.count("close") == 2


def test_configuration_failure_and_refresh_remove_stale_tools(client_setup, monkeypatch):
    manager, _, configure = client_setup
    fake_server(monkeypatch)
    configure({"valid": {"transport": "stdio", "command": "unused"},
               "bad": {"transport": "streamable_http", "url": "file:///secret"},
               "disabled": {"transport": "stdio", "command": "unused", "enabled": False}})
    async def run():
        status = await manager.refresh()
        assert status == {"valid": "ready:2", "bad": "unavailable", "disabled": "disabled"}
        assert manager.descriptors("admin")
        configure({})
        await manager.refresh()
        assert not manager.descriptors("admin")
        from src.config import settings
        monkeypatch.setattr(settings, "MCP_CLIENT_ENABLED", False)
        assert await manager.refresh() == {}
    asyncio.run(run())


def test_credentials_from_dotenv_and_environment_precedence(tmp_path, monkeypatch):
    from src.config import Settings, settings
    from src.engine.mcp_client import _environment
    path = tmp_path / ".env"
    path.write_text("OUTBOUND_MCP_KEY=dotenv-secret\n", encoding="utf-8")
    config = Settings(_env_file=str(path))  # Arbitrary credential names must not prevent startup.
    assert config.MCP_CLIENT_ENABLED is False
    monkeypatch.setitem(settings.model_config, "env_file", str(path))
    monkeypatch.delenv("OUTBOUND_MCP_KEY", raising=False)
    assert _environment({"X-API-Key": "OUTBOUND_MCP_KEY"}) == {"X-API-Key": "dotenv-secret"}
    monkeypatch.setenv("OUTBOUND_MCP_KEY", "environment-secret")
    assert _environment({"X-API-Key": "OUTBOUND_MCP_KEY"}) == {"X-API-Key": "environment-secret"}
    with pytest.raises(ValueError):
        _environment({"X-API-Key": "NONEXISTENT_HERMES_TEST_MCP_KEY"})


def test_client_status_and_catalog_api_authorization(client_setup, monkeypatch):
    import ast
    from pathlib import Path
    from fastapi import APIRouter, Depends, FastAPI
    from starlette.testclient import TestClient
    from src.middleware.auth_middleware import APIKeyMiddleware, authenticated_user, require_admin
    from src.config import settings
    manager, _, configure = client_setup
    fake_server(monkeypatch)
    configure({"demo": {"transport": "stdio", "command": "unused", "headers_env": {"secret": "SECRET_ENV"}}})
    asyncio.run(manager.refresh())
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / "src/api/v1/mcp.py").read_text(encoding="utf-8"))
    functions = [n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name in {"get_mcp_client_status", "get_mcp_client_tools"}]
    router = APIRouter(prefix="/api/v1")
    namespace = {"router": router, "Depends": Depends, "authenticated_user": authenticated_user, "require_admin": require_admin}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "mcp_client_endpoints", "exec"), namespace)
    app = FastAPI()
    app.include_router(router)
    app.add_middleware(APIKeyMiddleware)
    monkeypatch.setattr(settings, "API_KEY_ENABLED", True)
    monkeypatch.setattr(settings, "API_KEY_USERS", json.dumps({"admin-key": "admin", "alice-key": "alice"}))
    with TestClient(app) as client:
        assert client.get("/api/v1/mcp/client/status").status_code == 401
        assert client.get("/api/v1/mcp/client/status", headers={"X-API-Key": "alice-key"}).status_code == 403
        status = client.get("/api/v1/mcp/client/status", headers={"X-API-Key": "admin-key"})
        assert status.status_code == 200 and status.json()["servers"] == {"demo": "ready:2"}
        assert "SECRET_ENV" not in status.text and "headers_env" not in status.text
        assert client.get("/api/v1/mcp/client/tools", headers={"X-API-Key": "alice-key"}).json() == {"tools": []}


def test_remote_schema_does_not_fetch_external_references():
    from src.engine.mcp_client import _check_local_refs, tool_alias
    with pytest.raises(ValueError):
        _check_local_refs({"type": "object", "properties": {"x": {"$ref": "https://invalid.example/schema"}}})
    assert len(tool_alias("demo", "long tool name" * 20)) <= 64
    assert tool_alias("demo", "tool/name") != tool_alias("demo", "tool_name")


def test_real_stdio_discovery_and_call(client_setup, tmp_path):
    manager, _, configure = client_setup
    script = tmp_path / "stdio_server.py"
    script.write_text('''from mcp.server.fastmcp import FastMCP
mcp = FastMCP("stdio-regression")
@mcp.tool()
def echo(message: str) -> str:
    return "remote:" + message
if __name__ == "__main__":
    mcp.run(transport="stdio")
''', encoding="utf-8")
    configure({"local": {"transport": "stdio", "command": sys.executable, "args": [str(script)], "timeout": 15}})
    async def run():
        assert await manager.refresh() == {"local": "ready:1"}
        result = await manager.call("mcp__local__echo", {"message": "hello"}, "admin")
        assert result["success"] and result["result"]["content"][0]["text"] == "remote:hello"
        await manager.close()
    asyncio.run(run())


def test_real_streamable_http_discovery_and_call(client_setup, monkeypatch):
    import uvicorn
    from mcp.server.fastmcp import FastMCP
    from starlette.responses import JSONResponse
    manager, _, configure = client_setup
    server_mcp = FastMCP("http-regression", stateless_http=True, json_response=True)
    @server_mcp.tool()
    def echo(message: str) -> str:
        return "http:" + message
    app = server_mcp.streamable_http_app()
    async def authenticated(scope, receive, send):
        if scope["type"] == "http" and dict(scope["headers"]).get(b"x-api-key") != b"regression-key":
            return await JSONResponse({}, 401)(scope, receive, send)
        await app(scope, receive, send)
    monkeypatch.setenv("TEST_MCP_KEY", "regression-key")
    server = uvicorn.Server(uvicorn.Config(authenticated, host="127.0.0.1", port=0, log_level="error"))
    async def run():
        task = asyncio.create_task(server.serve())
        try:
            async with asyncio.timeout(5):
                while not server.started:
                    if task.done():
                        await task
                        raise RuntimeError("Test HTTP server stopped before startup")
                    await asyncio.sleep(0.01)
            port = server.servers[0].sockets[0].getsockname()[1]
            configure({"http": {"transport": "streamable_http", "url": f"http://127.0.0.1:{port}/mcp", "headers_env": {"X-API-Key": "TEST_MCP_KEY"}}})
            assert await manager.refresh() == {"http": "ready:1"}
            result = await manager.call("mcp__http__echo", {"message": "hello"}, "admin")
            assert result["success"] and result["result"]["content"][0]["text"] == "http:hello"
            await manager.close()
        finally:
            server.should_exit = True
            await asyncio.wait_for(task, 5)
    asyncio.run(run())
