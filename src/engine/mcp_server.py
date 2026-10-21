"""MCP Server - 基于官方 Python MCP SDK 的工具服务器"""

import logging
from typing import Any, Dict, List, Optional

try:
    from mcp.server.fastmcp import FastMCP
    HAS_MCP_SDK = True
except ImportError:
    HAS_MCP_SDK = False

logger = logging.getLogger("mcp_server")

async def _execute_guarded(tool_id, parameters):
    import asyncio
    from src.tools.runtime import current_user
    user_id = current_user.get()
    if not user_id:
        return {"success": False, "error": "MCP tool requires a server-authenticated user identity"}
    from src.plugins import get_tool_executor
    executor = get_tool_executor()
    if executor is None:
        return {"success": False, "error": "Tool executor is unavailable"}
    return await asyncio.to_thread(executor.execute, tool_id, {**parameters, "user_id": user_id})


if HAS_MCP_SDK:
    mcp = FastMCP("HermesAgent", stateless_http=True, json_response=True)


    @mcp.tool()
    async def document_search(
        query: str,
        limit: int = 5,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """文档语义搜索工具"""

        return await _execute_guarded("document_search", {"query": query, "limit": limit})


    @mcp.tool()
    async def memory_search(
        user_id: str,
        query: str,
        limit: int = 5
    ) -> Dict[str, Any]:
        """记忆搜索工具"""

        return await _execute_guarded("memory_search", {"query": query, "limit": limit})


    @mcp.tool()
    async def web_search(query: str) -> Dict[str, Any]:
        """网页搜索工具"""

        return await _execute_guarded("web_search", {"query": query})


    @mcp.tool()
    async def code_execution(
        code: str,
        language: str = "python"
    ) -> Dict[str, Any]:
        """代码执行工具"""

        return await _execute_guarded("code_execution", {"code": code, "language": language})


    @mcp.tool()
    async def file_operations(
        operation: str,
        file_path: str,
        content: Optional[str] = None
    ) -> Dict[str, Any]:
        """文件操作工具"""

        return await _execute_guarded("file_operations", {
            "operation": operation, "path": file_path, "content": content or ""})


    @mcp.tool()
    async def feishu_file_read(
        file_key: str,
        message_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """飞书文件读取工具"""

        return await _execute_guarded("feishu_file_read", {
            "file_key": file_key, "message_id": message_id})


    @mcp.tool()
    async def generate_ppt(
        title: str,
        slides: List[Dict[str, Any]],
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """PPT生成工具"""

        return await _execute_guarded("generate_ppt", {"title": title, "slides": slides})


    @mcp.tool()
    async def ppt_template_match(
        content: str,
        template_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """PPT模板匹配工具"""

        return await _execute_guarded("ppt_template_match", {
            "content": content, "style_hint": template_type})


    @mcp.tool()
    async def add_to_vector_store(
        content: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """添加到向量存储"""

        try:
            from src.data.vector_store import vector_store

            from src.tools.runtime import current_user
            user_id = current_user.get()
            if not user_id:
                return {"success": False, "error": "Authenticated identity required"}
            vector_store.add_large_document(content, {**metadata, "user_id": user_id})

            return {
                "success": True,
                "message": "文档已添加到向量存储"
            }
        except Exception as e:
            logger.error(f"添加到向量存储失败: {str(e)}")
            return {"success": False, "error": str(e)}


    @mcp.tool()
    async def get_user_preferences(user_id: str) -> Dict[str, Any]:
        """获取用户偏好设置"""

        try:
            from src.tools.runtime import current_user
            user_id = current_user.get()
            if not user_id:
                return {"success": False, "error": "Authenticated identity required"}
            from src.engine.memory_manager import memory_manager
            profile = memory_manager.get_user_profile(user_id)
            return {"success": True, "preferences": profile.preferences if profile else {}}
        except Exception as e:
            logger.error(f"获取用户偏好失败: {str(e)}")
            return {"success": False, "error": str(e)}


    @mcp.resource("documents://{doc_id}")
    async def get_document(doc_id: str) -> str:
        """获取文档资源"""

        try:
            from src.data.vector_store import vector_store

            from src.tools.runtime import current_user
            user_id = current_user.get()
            if not user_id:
                return ""
            results = vector_store.search(query=doc_id, k=1, filter={"user_id": user_id})

            if results:
                return results[0].get("content", "")
            return ""
        except Exception as e:
            logger.error(f"获取文档失败: {str(e)}")
            return ""


    @mcp.prompt()
    def review_code_prompt(code: str, language: str) -> str:
        """代码审查提示模板"""

        return f"""请审查以下{language}代码，关注：
    1. 代码质量和可读性
    2. 潜在的bug或安全问题
    3. 性能优化建议
    4. 最佳实践建议

    代码：
    ```{language}
    {code}
    ```"""


    def create_http_app():
        """Build the SDK transport, preserving its lifespan and binding a trusted identity."""
        from starlette.responses import JSONResponse
        from src.config import settings
        from src.tools.runtime import current_user
        import json

        app = mcp.streamable_http_app()

        async def authenticated_app(scope, receive, send):
            if scope["type"] != "http":
                return await app(scope, receive, send)
            headers = {k.lower(): v for k, v in scope.get("headers", [])}
            key = headers.get(b"x-api-key", b"").decode("utf-8", errors="replace")
            try:
                users = json.loads(settings.API_KEY_USERS)
                user = users.get(key) if isinstance(users, dict) and key else None
            except (ValueError, TypeError):
                user = None
            if not isinstance(user, str) or not user.strip():
                return await JSONResponse({"error": "A mapped API key is required"}, status_code=401)(scope, receive, send)
            token = current_user.set(user)
            try:
                await app(scope, receive, send)
            finally:
                current_user.reset(token)

        return authenticated_app


    def run_server(transport: str = "stdio"):
        if transport == "http":
            import uvicorn
            from src.config import settings
            uvicorn.run(create_http_app(), host=settings.MCP_SERVER_HOST, port=settings.MCP_SERVER_PORT)
        elif transport == "stdio":
            mcp.run(transport="stdio")
        else:
            raise ValueError("Supported transports: stdio, http")


    async def start_http_server(port: int = 8000) -> bool:
        import asyncio
        global _mcp_server_instance, _mcp_server_task
        if _mcp_server_instance is not None:
            return False
        try:
            import uvicorn
            from src.config import settings
            server = uvicorn.Server(uvicorn.Config(create_http_app(),
                host=settings.MCP_SERVER_HOST, port=port, log_level="info", access_log=False))
            _mcp_server_instance = server
            _mcp_server_task = asyncio.current_task()
            await server.serve()
            return bool(server.started)
        except Exception:
            logger.exception("MCP HTTP server failed")
            return False
        finally:
            _mcp_server_instance = None
            _mcp_server_task = None


    async def stop_http_server():
        import asyncio
        if _mcp_server_instance is not None:
            _mcp_server_instance.should_exit = True
            task = _mcp_server_task
            if task is not None and task is not asyncio.current_task():
                await asyncio.shield(task)


    _mcp_server_instance = None
    _mcp_server_task = None


else:
    mcp = None

    def run_server(transport: str = "stdio"):
        logger.error("MCP SDK 未安装，无法启动服务器")
        raise ImportError("MCP SDK 未安装，请运行 pip install mcp")

    async def start_http_server(port: int = 8000) -> bool:
        logger.warning("MCP SDK 未安装，无法启动 MCP HTTP 服务器")
        return False

    async def stop_http_server():
        pass


if __name__ == "__main__":
    import sys
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    run_server(transport=transport)