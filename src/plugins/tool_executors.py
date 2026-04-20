"""工具执行插件实现"""
import logging
from typing import Dict, Any, List, Optional

from src.plugins.base import ToolExecutorBase
from src.config import settings
from src.utils import generate_id, get_timestamp

logger = logging.getLogger("hermes_office_agent")


class BasicToolExecutor(ToolExecutorBase):
    """基础工具执行器"""
    
    def __init__(self):
        self.tools = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """注册默认工具"""
        self.register_tool("document_search", DocumentSearchTool)
        self.register_tool("memory_search", MemorySearchTool)
        self.register_tool("web_search", WebSearchTool)
        self.register_tool("code_execution", CodeExecutionTool)
        self.register_tool("file_operations", FileOperationsTool)
    
    def execute(self, tool_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具"""
        if tool_id not in self.tools:
            return {"success": False, "error": f"工具 {tool_id} 不存在"}
        
        try:
            tool_instance = self.tools[tool_id]()
            result = tool_instance.execute(parameters)
            return result
        except Exception as e:
            logger.error(f"执行工具 {tool_id} 失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def register_tool(self, tool_id: str, tool_class: Any) -> bool:
        """注册工具"""
        self.tools[tool_id] = tool_class
        logger.info(f"注册工具: {tool_id}")
        return True
    
    def get_tools(self) -> List[str]:
        """获取所有可用工具"""
        return list(self.tools.keys())
    
    def get_executor_type(self) -> str:
        return "basic"


class SandboxedToolExecutor(ToolExecutorBase):
    """沙箱工具执行器（带安全限制）"""
    
    def __init__(self):
        self.tools = {}
        self.allowed_paths = settings.SANDBOX_ALLOWED_PATHS or []
        self.max_execution_time = settings.SANDBOX_MAX_EXECUTION_TIME or 30
        self._register_default_tools()
    
    def _register_default_tools(self):
        """注册默认工具"""
        self.register_tool("document_search", DocumentSearchTool)
        self.register_tool("memory_search", MemorySearchTool)
        self.register_tool("web_search", WebSearchTool)
        self.register_tool("code_execution", SandboxedCodeExecutionTool)
        self.register_tool("file_operations", SandboxedFileOperationsTool)
    
    def execute(self, tool_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具（带安全检查）"""
        if tool_id not in self.tools:
            return {"success": False, "error": f"工具 {tool_id} 不存在"}
        
        # 安全检查
        if not self._check_security(tool_id, parameters):
            return {"success": False, "error": "安全检查失败"}
        
        try:
            tool_instance = self.tools[tool_id](self)
            result = tool_instance.execute(parameters)
            return result
        except Exception as e:
            logger.error(f"执行工具 {tool_id} 失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _check_security(self, tool_id: str, parameters: Dict[str, Any]) -> bool:
        """安全检查"""
        if tool_id == "file_operations":
            file_path = parameters.get("path", "")
            if not self._is_path_allowed(file_path):
                logger.warning(f"非法路径访问: {file_path}")
                return False
        
        return True
    
    def _is_path_allowed(self, file_path: str) -> bool:
        """检查路径是否在白名单中"""
        if not file_path:
            return False
        
        for allowed in self.allowed_paths:
            if file_path.startswith(allowed):
                return True
        
        return False
    
    def register_tool(self, tool_id: str, tool_class: Any) -> bool:
        """注册工具"""
        self.tools[tool_id] = tool_class
        logger.info(f"注册工具: {tool_id}")
        return True
    
    def get_tools(self) -> List[str]:
        """获取所有可用工具"""
        return list(self.tools.keys())
    
    def get_executor_type(self) -> str:
        return "sandboxed"


# 工具类定义
class DocumentSearchTool:
    """文档搜索工具"""
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        query = parameters.get("query", "")
        limit = parameters.get("limit", 5)
        
        try:
            from src.infrastructure.model_router import search_documents
            results = search_documents(query, limit)
            
            return {
                "success": True,
                "result": results
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class MemorySearchTool:
    """记忆搜索工具"""
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        user_id = parameters.get("user_id", "")
        query = parameters.get("query", "")
        limit = parameters.get("limit", 5)
        
        try:
            from src.engine.memory_manager import memory_manager
            results = memory_manager.search_long_term_memory(user_id, query, limit)
            
            return {
                "success": True,
                "result": [r.dict() for r in results]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class WebSearchTool:
    """网页搜索工具"""
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        query = parameters.get("query", "")
        
        try:
            # 模拟网页搜索结果
            results = [
                {"title": "搜索结果1", "url": "https://example.com", "summary": f"关于 '{query}' 的信息..."},
                {"title": "搜索结果2", "url": "https://example.org", "summary": f"更多关于 '{query}' 的内容..."}
            ]
            
            return {
                "success": True,
                "result": results
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class CodeExecutionTool:
    """代码执行工具"""
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        code = parameters.get("code", "")
        language = parameters.get("language", "python")
        
        try:
            if language == "python":
                import subprocess
                import tempfile
                import os
                
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
                    "success": True,
                    "result": {
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "return_code": result.returncode
                    }
                }
            else:
                return {"success": False, "error": f"不支持的语言: {language}"}
        
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "执行超时"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class SandboxedCodeExecutionTool:
    """沙箱代码执行工具"""
    
    def __init__(self, executor: "SandboxedToolExecutor"):
        self.executor = executor
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        code = parameters.get("code", "")
        language = parameters.get("language", "python")
        
        # 安全检查：禁止危险操作
        dangerous_patterns = ["import os", "import subprocess", "open(", "os.system", "__import__"]
        for pattern in dangerous_patterns:
            if pattern in code:
                return {"success": False, "error": "禁止执行危险操作"}
        
        try:
            if language == "python":
                # 限制执行时间
                import subprocess
                import tempfile
                import os
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    f.write(code)
                    temp_path = f.name
                
                result = subprocess.run(
                    ["python", temp_path],
                    capture_output=True,
                    text=True,
                    timeout=self.executor.max_execution_time
                )
                
                os.unlink(temp_path)
                
                return {
                    "success": True,
                    "result": {
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "return_code": result.returncode
                    }
                }
            else:
                return {"success": False, "error": f"不支持的语言: {language}"}
        
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "执行超时"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class FileOperationsTool:
    """文件操作工具"""
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        operation = parameters.get("operation", "")
        path = parameters.get("path", "")
        content = parameters.get("content", "")
        
        try:
            if operation == "read":
                with open(path, "r", encoding="utf-8") as f:
                    return {"success": True, "result": f.read()}
            
            elif operation == "write":
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                return {"success": True, "result": "文件写入成功"}
            
            elif operation == "append":
                with open(path, "a", encoding="utf-8") as f:
                    f.write(content)
                return {"success": True, "result": "内容追加成功"}
            
            elif operation == "list":
                import os
                files = os.listdir(path)
                return {"success": True, "result": files}
            
            else:
                return {"success": False, "error": f"未知操作: {operation}"}
        
        except FileNotFoundError:
            return {"success": False, "error": "文件不存在"}
        except PermissionError:
            return {"success": False, "error": "权限不足"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class SandboxedFileOperationsTool:
    """沙箱文件操作工具"""
    
    def __init__(self, executor: "SandboxedToolExecutor"):
        self.executor = executor
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        operation = parameters.get("operation", "")
        path = parameters.get("path", "")
        content = parameters.get("content", "")
        
        # 路径安全检查
        if not self.executor._is_path_allowed(path):
            return {"success": False, "error": f"路径不在白名单中: {path}"}
        
        try:
            if operation == "read":
                with open(path, "r", encoding="utf-8") as f:
                    return {"success": True, "result": f.read()[:10000]}  # 限制读取大小
            
            elif operation == "write":
                # 检查文件大小
                if len(content) > 100000:
                    return {"success": False, "error": "内容超过限制"}
                
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                return {"success": True, "result": "文件写入成功"}
            
            elif operation == "append":
                if len(content) > 10000:
                    return {"success": False, "error": "内容超过限制"}
                
                with open(path, "a", encoding="utf-8") as f:
                    f.write(content)
                return {"success": True, "result": "内容追加成功"}
            
            elif operation == "list":
                import os
                files = os.listdir(path)
                return {"success": False, "result": files}
            
            else:
                return {"success": False, "error": f"未知操作: {operation}"}
        
        except FileNotFoundError:
            return {"success": False, "error": "文件不存在"}
        except PermissionError:
            return {"success": False, "error": "权限不足"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# 工具执行器注册表
TOOL_EXECUTOR_REGISTRY = {
    "basic": BasicToolExecutor,
    "sandboxed": SandboxedToolExecutor
}
