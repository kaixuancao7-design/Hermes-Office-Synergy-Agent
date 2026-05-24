"""MCP Server - 基于官方 Python MCP SDK 的工具服务器"""

import os
import logging
from typing import Any, Dict, List, Optional

try:
    from mcp.server.fastmcp import FastMCP
    HAS_MCP_SDK = True
except ImportError:
    HAS_MCP_SDK = False

logger = logging.getLogger("mcp_server")

if HAS_MCP_SDK:
    mcp = FastMCP("HermesAgent")


    @mcp.tool()
    async def document_search(
        query: str,
        limit: int = 5,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """文档语义搜索工具"""

        try:
            from src.data.vector_store import vector_store

            filter_dict = None
            if user_id:
                filter_dict = {"user_id": user_id}

            results = vector_store.search(
                query=query,
                k=limit,
                filter=filter_dict,
                use_advanced=True
            )

            logger.info(f"文档搜索完成: query='{query}', 找到 {len(results)} 条结果")

            return {
                "success": True,
                "result": results,
                "message": f"搜索完成，找到 {len(results)} 条相关文档",
                "query": query,
                "limit": limit
            }
        except Exception as e:
            logger.error(f"文档搜索失败: {str(e)}")
            return {
                "success": False,
                "result": [],
                "message": f"搜索失败: {str(e)}"
            }


    @mcp.tool()
    async def memory_search(
        user_id: str,
        query: str,
        limit: int = 5
    ) -> Dict[str, Any]:
        """记忆搜索工具"""

        try:
            from src.engine.memory_manager import memory_manager

            results = memory_manager.search_long_term_memory(user_id, query, limit)

            return {
                "success": True,
                "result": [r.model_dump() for r in results]
            }
        except Exception as e:
            logger.error(f"记忆搜索失败: {str(e)}")
            return {"success": False, "error": str(e)}


    @mcp.tool()
    async def web_search(query: str) -> Dict[str, Any]:
        """网页搜索工具"""

        try:
            results = [
                {
                    "title": f"搜索结果1: {query}",
                    "url": "https://example.com/result1",
                    "summary": f"关于 '{query}' 的搜索结果摘要..."
                },
                {
                    "title": f"搜索结果2: {query}",
                    "url": "https://example.com/result2",
                    "summary": f"更多关于 '{query}' 的内容..."
                }
            ]

            return {
                "success": True,
                "result": results
            }
        except Exception as e:
            logger.error(f"网页搜索失败: {str(e)}")
            return {"success": False, "error": str(e)}


    @mcp.tool()
    async def code_execution(
        code: str,
        language: str = "python"
    ) -> Dict[str, Any]:
        """代码执行工具"""

        try:
            if language == "python":
                import subprocess
                import tempfile

                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    f.write(code)
                    temp_path = f.name

                result = subprocess.run(
                    ["python", temp_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                os.unlink(temp_path)

                return {
                    "success": result.returncode == 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode
                }
            else:
                return {
                    "success": False,
                    "error": f"不支持的语言: {language}"
                }
        except Exception as e:
            logger.error(f"代码执行失败: {str(e)}")
            return {"success": False, "error": str(e)}


    @mcp.tool()
    async def file_operations(
        operation: str,
        file_path: str,
        content: Optional[str] = None
    ) -> Dict[str, Any]:
        """文件操作工具"""

        try:
            if operation == "read":
                if not os.path.exists(file_path):
                    return {"success": False, "error": f"文件不存在: {file_path}"}

                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                return {"success": True, "content": content}

            elif operation == "write":
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content or "")

                return {"success": True, "file_path": file_path}

            elif operation == "delete":
                if os.path.exists(file_path):
                    os.unlink(file_path)
                return {"success": True}

            elif operation == "list":
                if os.path.isdir(file_path):
                    files = os.listdir(file_path)
                    return {"success": True, "files": files}
                return {"success": False, "error": "不是有效的目录"}

            else:
                return {"success": False, "error": f"不支持的操作: {operation}"}

        except Exception as e:
            logger.error(f"文件操作失败: {str(e)}")
            return {"success": False, "error": str(e)}


    @mcp.tool()
    async def feishu_file_read(
        file_key: str,
        message_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """飞书文件读取工具"""

        try:
            from src.plugins.im_adapters import get_im_adapter

            adapter = get_im_adapter()
            if not adapter:
                return {"success": False, "error": "飞书适配器未初始化"}

            result = adapter.download_file(file_key, message_id=message_id)

            if result.get("success"):
                return {
                    "success": True,
                    "content": result.get("content", ""),
                    "file_name": result.get("file_name", ""),
                    "file_path": result.get("file_path", "")
                }
            else:
                return {"success": False, "error": result.get("error", "下载失败")}

        except Exception as e:
            logger.error(f"飞书文件读取失败: {str(e)}")
            return {"success": False, "error": str(e)}


    @mcp.tool()
    async def generate_ppt(
        title: str,
        slides: List[Dict[str, Any]],
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """PPT生成工具"""

        try:
            from tools.ppt_generator import GeneratePPT

            generator = GeneratePPT()

            params = {
                "title": title,
                "slides": slides,
                "output_path": output_path
            }

            result = generator.execute(params)

            return result
        except Exception as e:
            logger.error(f"PPT生成失败: {str(e)}")
            return {"success": False, "error": str(e)}


    @mcp.tool()
    async def ppt_template_match(
        content: str,
        template_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """PPT模板匹配工具"""

        try:
            from src.services.template_matcher import template_matcher

            result = template_matcher.match_template(content, template_type)

            return result
        except Exception as e:
            logger.error(f"模板匹配失败: {str(e)}")
            return {"success": False, "error": str(e)}


    @mcp.tool()
    async def add_to_vector_store(
        content: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """添加到向量存储"""

        try:
            from src.data.vector_store import vector_store

            vector_store.add_large_document(content, metadata)

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
            from src.plugins.memory_stores import get_memory_store

            memory_store = get_memory_store()
            if not memory_store:
                return {"success": False, "error": "记忆存储未初始化"}

            results = memory_store.search_memory(user_id, "user_preferences", limit=1)

            if results:
                return {
                    "success": True,
                    "preferences": results[0].content
                }
            return {
                "success": True,
                "preferences": {}
            }
        except Exception as e:
            logger.error(f"获取用户偏好失败: {str(e)}")
            return {"success": False, "error": str(e)}


    @mcp.resource("documents://{doc_id}")
    async def get_document(doc_id: str) -> str:
        """获取文档资源"""

        try:
            from src.data.vector_store import vector_store

            results = vector_store.search(query=doc_id, k=1)

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


    def run_server(transport: str = "stdio"):
        """运行 MCP Server

        Args:
            transport: 传输方式 ("stdio" 或 "http")
        """
        logger.info(f"启动 MCP Server，传输方式: {transport}")

        if transport == "http":
            import uvicorn
            from mcp.server.sse import SSEServer

            sse_server = SSEServer(mcp.app)
            uvicorn.run(sse_server, host="0.0.0.0", port=8000)
        else:
            mcp.run(transport="stdio")

else:
    mcp = None

    def run_server(transport: str = "stdio"):
        logger.error("MCP SDK 未安装，无法启动服务器")
        raise ImportError("MCP SDK 未安装，请运行 pip install mcp")


if __name__ == "__main__":
    import sys
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    run_server(transport=transport)