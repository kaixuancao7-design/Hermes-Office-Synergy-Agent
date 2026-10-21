"""Outbound MCP tools. Each operation owns its transport and closes it in the same task."""
import copy
import hashlib
import json
import logging
import os
import re
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import anyio
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.config import settings

logger = logging.getLogger("engine.mcp_client")


class ServerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transport: Literal["stdio", "streamable_http"]
    enabled: bool = True
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    cwd: str | None = None
    env_from: dict[str, str] = Field(default_factory=dict)
    url: str | None = None
    headers_env: dict[str, str] = Field(default_factory=dict)
    allowed_users: list[str] | None = None
    allowed_tools: list[str] | None = None
    timeout: float = Field(default=30, gt=0, le=300)

    @model_validator(mode="after")
    def validate_transport(self):
        if self.transport == "stdio" and (not self.command or not self.command.strip()):
            raise ValueError("Stdio requires a command")
        if self.transport == "streamable_http":
            parsed = urlsplit(self.url or "")
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
                raise ValueError("HTTP requires an http(s) URL without embedded credentials or fragment")
        return self


def tool_alias(server, remote):
    prefix = f"mcp__{server}__"
    if re.fullmatch(r"[A-Za-z0-9_-]+", remote) and len(prefix + remote) <= 64:
        return prefix + remote
    readable = re.sub(r"[^A-Za-z0-9_-]", "_", remote)[:64 - len(prefix) - 13]
    return prefix + readable + "_" + hashlib.sha256(remote.encode()).hexdigest()[:12]


def _environment(mapping):
    from dotenv import dotenv_values
    dotenv = dotenv_values(settings.model_config.get("env_file") or ".env")
    values = {}
    for target, source in mapping.items():
        value = os.environ.get(source, dotenv.get(source))
        if not value:
            raise ValueError("A configured MCP credential environment variable is missing")
        values[target] = value
    return values


@asynccontextmanager
async def open_session(config):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    async with AsyncExitStack() as stack:
        if config.transport == "stdio":
            transport = stdio_client(StdioServerParameters(command=config.command,
                args=config.args, cwd=config.cwd, env=_environment(config.env_from)))
        else:
            headers = _environment(config.headers_env)
            try:
                from mcp.client.streamable_http import streamable_http_client
            except ImportError:  # SDK 1.x before the transport helper was renamed.
                from mcp.client.streamable_http import streamablehttp_client
                transport = streamablehttp_client(config.url, headers=headers,
                    timeout=config.timeout, sse_read_timeout=config.timeout)
            else:
                import httpx
                client = await stack.enter_async_context(httpx.AsyncClient(
                    headers=headers, timeout=config.timeout))
                transport = streamable_http_client(config.url, http_client=client)
        streams = await stack.enter_async_context(transport)
        session = await stack.enter_async_context(ClientSession(streams[0], streams[1],
            read_timeout_seconds=timedelta(seconds=config.timeout)))
        await session.initialize()
        yield session


def _check_local_refs(value):
    """Support nested local definitions without fetching untrusted schemas over the network."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"$ref", "$dynamicRef"} and (not isinstance(item, str) or not item.startswith("#")):
                raise ValueError("Only document-local JSON Schema references are supported")
            _check_local_refs(item)
    elif isinstance(value, list):
        for item in value:
            _check_local_refs(item)


class MCPClientManager:
    def __init__(self):
        self._tools = {}
        self.status = {}

    async def refresh(self):
        """Replace the catalog atomically. A failed server cannot leave stale tools behind."""
        catalog, status = {}, {}
        if not settings.MCP_CLIENT_ENABLED:
            self._tools, self.status = catalog, status
            return status
        try:
            payload = json.loads(Path(settings.MCP_SERVERS_CONFIG).read_text(encoding="utf-8"))
            servers = payload["mcpServers"]
            if not isinstance(servers, dict):
                raise ValueError("mcpServers must be an object")
        except Exception as exc:
            self._tools = {}
            self.status = {"config": "invalid"}
            logger.error("MCP client configuration could not be loaded (%s)", type(exc).__name__)
            return self.status

        for name, raw in servers.items():
            discovered = {}
            try:
                if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,15}", name):
                    raise ValueError("Invalid server name")
                config = ServerConfig.model_validate({"timeout": settings.MCP_CLIENT_TIMEOUT, **raw})
                if not config.enabled:
                    status[name] = "disabled"
                    continue
                with anyio.fail_after(config.timeout):
                    async with open_session(config) as session:
                        cursor, seen = None, set()
                        while True:
                            page = await session.list_tools(cursor=cursor)
                            for tool in page.tools:
                                if config.allowed_tools is not None and tool.name not in config.allowed_tools:
                                    continue
                                schema = copy.deepcopy(tool.inputSchema)
                                Draft202012Validator.check_schema(schema)
                                _check_local_refs(schema)
                                if schema.get("type") != "object":
                                    raise ValueError("Tool arguments must be an object")
                                alias = tool_alias(name, tool.name)
                                if alias in discovered:
                                    raise ValueError("Duplicate tool name")
                                discovered[alias] = {"name": alias, "remote_name": tool.name,
                                    "server": name, "description": tool.description or tool.name,
                                    "inputSchema": schema, "config": config}
                            cursor = page.nextCursor
                            if not cursor:
                                break
                            if cursor in seen or len(seen) >= 100:
                                raise ValueError("Invalid tool pagination")
                            seen.add(cursor)
                catalog.update(discovered)
                status[name] = f"ready:{len(discovered)}"
            except Exception as exc:
                status[name] = "unavailable"
                logger.warning("MCP discovery failed for configured server %s (%s)", name, type(exc).__name__)
        self._tools, self.status = catalog, status
        return dict(status)

    def _allowed(self, tool, user):
        if not settings.MCP_CLIENT_ENABLED or not user:
            return False
        allowed = tool["config"].allowed_users
        if allowed is not None and user not in allowed:
            return False
        from src.data.database import db
        # External tools may write arbitrary systems; role-wide tool grants are insufficient.
        return db.check_permission(user, "tool", tool["name"], "execute")

    def descriptors(self, user=None):
        if user is None:
            from src.tools.runtime import current_user
            user = current_user.get()
        return [{key: copy.deepcopy(tool[key]) for key in ("name", "description", "inputSchema")}
                for tool in self._tools.values() if self._allowed(tool, user)]

    def catalog(self):
        """Unfiltered metadata for trusted administration/structural validation, never credentials."""
        if not settings.MCP_CLIENT_ENABLED:
            return []
        return [{key: copy.deepcopy(tool[key]) for key in
                 ("name", "server", "remote_name", "description", "inputSchema")}
                for tool in self._tools.values()]

    def has_tool(self, name):
        return settings.MCP_CLIENT_ENABLED and name in self._tools

    async def call(self, name, parameters, user):
        tool = self._tools.get(name)
        if not tool or not self._allowed(tool, user):
            return {"success": False, "error": "External MCP tool unavailable or permission denied"}
        try:
            arguments = copy.deepcopy(parameters)
            # These are local execution metadata. A declared user_id always uses trusted identity.
            properties = tool["inputSchema"].get("properties", {})
            for key in ("user_id", "request_id"):
                if key not in properties:
                    arguments.pop(key, None)
            if "user_id" in properties:
                arguments["user_id"] = user
            Draft202012Validator(tool["inputSchema"]).validate(arguments)
            with anyio.fail_after(tool["config"].timeout):
                async with open_session(tool["config"]) as session:
                    result = await session.call_tool(tool["remote_name"], arguments=arguments)
            payload = result.model_dump(mode="json", by_alias=True, exclude_none=True)
            return {"success": not result.isError, "result": payload,
                    **({"error": "Remote MCP tool reported an error"} if result.isError else {})}
        except Exception as exc:
            logger.warning("MCP tool call failed for %s (%s)", name, type(exc).__name__)
            return {"success": False, "error": f"External MCP request failed ({type(exc).__name__})"}

    def execute(self, name, parameters):
        from src.tools.runtime import current_user, run_sync
        user = current_user.get() or parameters.get("user_id")
        return run_sync(self.call(name, parameters, user))

    async def close(self):
        # Transport/session contexts are owned per operation, including cancellation paths.
        self._tools = {}
        self.status = {}


mcp_client_manager = MCPClientManager()
