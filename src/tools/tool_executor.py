from typing import Dict, Any, Optional
from src.infrastructure.sandbox import sandbox
from src.utils import setup_logging
from src.config import settings

logger = setup_logging(settings.LOG_LEVEL)


class ToolExecutor:
    def __init__(self):
        self.tools = {
            "execute_script": self._execute_script,
            "read_file": self._read_file,
            "write_file": self._write_file,
            "list_files": self._list_files,
            "web_search": self._web_search,
            "summarize": self._summarize
        }
    
    def execute(self, tool_id: str, parameters: Dict[str, Any]) -> str:
        if tool_id not in self.tools:
            return f"Unknown tool: {tool_id}"
        
        try:
            return self.tools[tool_id](parameters)
        except Exception as e:
            logger.error(f"Tool execution failed: {str(e)}")
            return f"Error executing {tool_id}: {str(e)}"
    
    def _execute_script(self, params: Dict[str, Any]) -> str:
        script = params.get("script", "")
        script_type = params.get("type", "python")
        
        output, error, success = sandbox.execute_script(script, script_type)
        
        if success:
            return output
        return f"Script failed: {error}"
    
    def _read_file(self, params: Dict[str, Any]) -> str:
        file_path = params.get("path", "")
        content = sandbox.read_file(file_path)
        return content if content else "Failed to read file"
    
    def _write_file(self, params: Dict[str, Any]) -> str:
        file_path = params.get("path", "")
        content = params.get("content", "")
        
        success = sandbox.write_file(file_path, content)
        return "File written successfully" if success else "Failed to write file"
    
    def _list_files(self, params: Dict[str, Any]) -> str:
        directory = params.get("directory", "")
        files = sandbox.list_files(directory)
        return "\n".join(files) if files else "Failed to list files"
    
    def _web_search(self, params: Dict[str, Any]) -> str:
        query = params.get("query", "")
        return f"Search results for: {query}\n(Web search integration placeholder)"
    
    def _summarize(self, params: Dict[str, Any]) -> str:
        text = params.get("text", "")
        max_length = params.get("max_length", 100)
        
        if len(text) <= max_length:
            return text
        
        return text[:max_length] + "..."


tool_executor = ToolExecutor()
