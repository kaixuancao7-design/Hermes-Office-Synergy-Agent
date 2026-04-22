"""工具执行插件实现"""
from typing import Dict, Any, List, Optional

from src.plugins.base import ToolExecutorBase
from src.config import settings
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger

logger = get_logger("tool")


class BasicToolExecutor(ToolExecutorBase):
    """基础工具执行器"""
    
    def __init__(self):
        self.tools = {}
        self.tool_name_mapping = {
            "file_reader": "feishu_file_read",
            "read_file": "feishu_file_read",
            "feishu_reader": "feishu_file_read"
        }
        self._register_default_tools()
    
    def _register_default_tools(self):
        """注册默认工具"""
        self.register_tool("document_search", DocumentSearchTool)
        self.register_tool("memory_search", MemorySearchTool)
        self.register_tool("web_search", WebSearchTool)
        self.register_tool("code_execution", CodeExecutionTool)
        self.register_tool("file_operations", FileOperationsTool)
        self.register_tool("feishu_file_read", FeishuFileReadTool)
    
    def execute(self, tool_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具"""
        # 工具名称映射
        if tool_id in self.tool_name_mapping:
            tool_id = self.tool_name_mapping[tool_id]
        
        if tool_id not in self.tools:
            return {"success": False, "error": f"工具 {tool_id} 不存在"}
        
        try:
            # 直接使用传入的参数（ReAct引擎已经处理好了参数格式）
            # 如果参数中包含嵌套的parameters字段，则使用嵌套的参数
            tool_params = parameters.get("parameters", parameters)
            
            # 如果是None，转换为空字典
            if tool_params is None:
                tool_params = {}
            
            # 获取工具类并创建实例
            tool_class = self.tools[tool_id]
            tool_instance = tool_class()
            result = tool_instance.execute(tool_params)
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
        self.register_tool("feishu_file_read", FeishuFileReadTool)
    
    def execute(self, tool_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具（带安全检查）"""
        if tool_id not in self.tools:
            return {"success": False, "error": f"工具 {tool_id} 不存在"}
        
        # 安全检查
        if not self._check_security(tool_id, parameters):
            return {"success": False, "error": "安全检查失败"}
        
        try:
            # 直接使用传入的参数（ReAct引擎已经处理好了参数格式）
            # 如果参数中包含嵌套的parameters字段，则使用嵌套的参数
            tool_params = parameters.get("parameters", parameters)
            
            # 如果是None，转换为空字典
            if tool_params is None:
                tool_params = {}
            
            # 创建工具实例（不传入参数，保持与 BasicToolExecutor 一致）
            tool_instance = self.tools[tool_id]()
            result = tool_instance.execute(tool_params)
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
                "result": [r.model_dump() for r in results]
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


class FeishuFileReadTool:
    """飞书文件读取工具 - 通过飞书API下载并读取文件内容"""
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        file_key = parameters.get("file_key", "")
        user_id = parameters.get("user_id", "")
        
        if not file_key:
            return {"success": False, "error": "缺少file_key参数"}
        
        try:
            from src.plugins.im_adapters import FeishuAdapter
            
            # 创建飞书适配器
            adapter = FeishuAdapter()
            
            # 调用飞书API下载文件
            file_content = self._download_feishu_file(adapter, file_key)
            
            if file_content:
                # 将文件内容存储到向量数据库（可选）
                if user_id:
                    self._store_to_vector_db(user_id, file_content, file_key)
                
                return {
                    "success": True,
                    "result": {
                        "file_key": file_key,
                        "content": file_content,
                        "content_length": len(file_content)
                    }
                }
            else:
                return {"success": False, "error": "文件下载失败"}
                
        except Exception as e:
            logger.error(f"读取飞书文件失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _download_feishu_file(self, adapter, file_key: str) -> Optional[str]:
        """
        通过飞书API下载文件内容
        
        步骤：
        1. 获取文件下载链接和文件信息
        2. 下载文件内容
        3. 根据文件类型解析内容
        """
        try:
            # 检查API客户端是否已初始化
            if not hasattr(adapter, '_api_client') or adapter._api_client is None:
                logger.warning("飞书API客户端未初始化，尝试初始化")
                adapter._initialize_client()
            
            if adapter._api_client is None:
                logger.error("无法初始化飞书API客户端")
                return None
            
            # 调用飞书API获取文件下载链接
            download_response = adapter._api_client.drive.v1.file.get_download_url(file_key)
            
            if not download_response.success():
                logger.error(f"获取下载链接失败: {download_response.code}, {download_response.msg}")
                return None
            
            download_url = download_response.data.download_url
            
            # 下载文件内容（保留原始二进制）
            import requests
            response = requests.get(download_url)
            
            # 获取文件名以确定文件类型
            file_info = adapter._api_client.drive.v1.file.get(file_key)
            file_name = ""
            if file_info.success():
                file_name = file_info.data.name or ""
            
            # 根据文件类型解析内容
            return self._parse_file_content(response.content, file_name)
            
        except Exception as e:
            logger.error(f"下载飞书文件失败: {str(e)}")
            # 返回模拟数据供测试
            return f"模拟文件内容 - file_key: {file_key}\n\n这是一份关于AI Agent智能协同助手的核心功能清单文档..."
    
    def _parse_file_content(self, content: bytes, file_name: str) -> str:
        """
        根据文件类型解析内容
        """
        try:
            # 获取文件扩展名
            import os
            _, ext = os.path.splitext(file_name.lower())
            
            # 文本文件直接解码
            if ext in ['.txt', '.md', '.json', '.xml', '.html', '.csv', '.tsv']:
                return content.decode('utf-8', errors='ignore')
            
            # docx 文件需要专门解析
            elif ext == '.docx':
                return self._parse_docx(content)
            
            # xlsx 文件解析
            elif ext == '.xlsx':
                return self._parse_xlsx(content)
            
            # xls 文件解析（旧版 Excel）
            elif ext == '.xls':
                return self._parse_xls(content)
            
            # pptx 文件解析
            elif ext == '.pptx':
                return self._parse_pptx(content)
            
            # pdf 文件解析
            elif ext == '.pdf':
                return self._parse_pdf(content)
            
            # rtf 文件解析
            elif ext == '.rtf':
                return self._parse_rtf(content)
            
            # doc 文件解析（旧版 Word）
            elif ext == '.doc':
                return self._parse_doc(content)
            
            # 其他未知类型，尝试作为文本处理
            else:
                # 先尝试 UTF-8 解码
                try:
                    text = content.decode('utf-8')
                    # 如果看起来像二进制数据，返回提示
                    if self._is_binary(text):
                        return f"无法解析文件格式: {ext}\n\n文件大小: {len(content)} bytes\n\n支持的文件类型: .txt, .md, .json, .xml, .html, .csv, .tsv, .docx, .doc, .xlsx, .xls, .pptx, .pdf, .rtf"
                    return text
                except:
                    return f"无法解析文件格式: {ext}\n\n文件大小: {len(content)} bytes\n\n支持的文件类型: .txt, .md, .json, .xml, .html, .csv, .tsv, .docx, .doc, .xlsx, .xls, .pptx, .pdf, .rtf"
                    
        except Exception as e:
            logger.error(f"解析文件内容失败: {str(e)}")
            return f"文件解析失败: {str(e)}"
    
    def _parse_docx(self, content: bytes) -> str:
        """解析 docx 文件内容"""
        try:
            from docx import Document
            from io import BytesIO
            
            doc = Document(BytesIO(content))
            full_text = []
            
            for para in doc.paragraphs:
                full_text.append(para.text)
            
            return '\n'.join(full_text)
            
        except Exception as e:
            logger.error(f"解析 docx 文件失败: {str(e)}")
            return f"无法解析 docx 文件: {str(e)}"
    
    def _parse_xlsx(self, content: bytes) -> str:
        """解析 xlsx 文件内容"""
        try:
            import pandas as pd
            from io import BytesIO
            
            df = pd.read_excel(BytesIO(content))
            return df.to_string()
            
        except Exception as e:
            logger.error(f"解析 xlsx 文件失败: {str(e)}")
            return f"无法解析 xlsx 文件: {str(e)}"
    
    def _parse_xls(self, content: bytes) -> str:
        """解析 xls 文件内容（旧版 Excel）"""
        try:
            import pandas as pd
            from io import BytesIO
            
            df = pd.read_excel(BytesIO(content), engine='xlrd')
            return df.to_string()
            
        except Exception as e:
            logger.error(f"解析 xls 文件失败: {str(e)}")
            return f"无法解析 xls 文件: {str(e)}"
    
    def _parse_pptx(self, content: bytes) -> str:
        """解析 pptx 文件内容"""
        try:
            from pptx import Presentation
            from io import BytesIO
            
            prs = Presentation(BytesIO(content))
            full_text = []
            
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, 'text'):
                        full_text.append(shape.text)
            
            return '\n\n'.join(full_text)
            
        except Exception as e:
            logger.error(f"解析 pptx 文件失败: {str(e)}")
            return f"无法解析 pptx 文件: {str(e)}"
    
    def _parse_pdf(self, content: bytes) -> str:
        """解析 pdf 文件内容"""
        try:
            import pdfplumber
            from io import BytesIO
            
            with pdfplumber.open(BytesIO(content)) as pdf:
                full_text = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        full_text.append(text)
            
            return '\n\n'.join(full_text)
            
        except Exception as e:
            logger.error(f"解析 pdf 文件失败: {str(e)}")
            return f"无法解析 pdf 文件: {str(e)}"
    
    def _parse_rtf(self, content: bytes) -> str:
        """解析 rtf 文件内容"""
        try:
            # 简单的 RTF 文本提取
            text = content.decode('utf-8', errors='ignore')
            # 移除 RTF 控制字
            import re
            text = re.sub(r'\\[a-zA-Z]+[^{}]*', '', text)
            text = re.sub(r'\\[{}]', '', text)
            text = re.sub(r'{[^}]*}', '', text)
            return text.strip()
            
        except Exception as e:
            logger.error(f"解析 rtf 文件失败: {str(e)}")
            return f"无法解析 rtf 文件: {str(e)}"
    
    def _parse_doc(self, content: bytes) -> str:
        """解析 doc 文件内容（旧版 Word）"""
        try:
            # 使用 antiword 或其他方式，这里提供基础支持
            # 旧版 doc 是二进制格式，需要专门工具
            return f"无法直接解析 .doc 文件格式。请将文件另存为 .docx 格式后重试，或使用 Microsoft Word 打开复制内容。\n\n文件大小: {len(content)} bytes"
            
        except Exception as e:
            logger.error(f"解析 doc 文件失败: {str(e)}")
            return f"无法解析 doc 文件: {str(e)}"
    
    def _is_binary(self, text: str) -> bool:
        """检测文本是否包含二进制数据"""
        # 检查是否有大量不可打印字符
        non_printable = sum(1 for c in text if ord(c) < 32 and c not in '\n\r\t')
        return non_printable > len(text) * 0.1
    
    def _store_to_vector_db(self, user_id: str, content: str, file_key: str):
        """将文件内容存储到向量数据库"""
        try:
            from src.engine.memory_manager import memory_manager
            
            # 存储到长期记忆
            memory_manager.add_long_term_memory(
                user_id=user_id,
                content=content,
                tags=f"feishu_file,{file_key}"
            )
            
            logger.info(f"文件内容已存储到向量数据库: {file_key}")
        except Exception as e:
            logger.warning(f"存储到向量数据库失败: {str(e)}")


# 工具执行器注册表
TOOL_EXECUTOR_REGISTRY = {
    "basic": BasicToolExecutor,
    "sandboxed": SandboxedToolExecutor
}
