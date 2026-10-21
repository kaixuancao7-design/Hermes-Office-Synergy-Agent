from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Type
from pydantic import BaseModel, ValidationError
from src.logging_config import get_logger

logger = get_logger("tool.base")


class ToolSchema(BaseModel):
    """工具参数Schema基类"""
    pass


class BaseTool(ABC):
    """工具基类，定义标准接口"""
    
    name: str = ""
    description: str = ""
    schema: Type[ToolSchema] = None
    
    def __init__(self, executor=None):
        self.executor = executor

    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> Any:
        """
        执行工具
        
        Args:
            params: 工具参数
            
        Returns:
            执行结果
        """
        pass
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        参数校验
        
        Args:
            params: 待校验参数
            
        Returns:
            True表示校验通过，False表示校验失败
        """
        if self.schema:
            try:
                self.schema(**params)
                return True
            except ValidationError as e:
                logger.error(f"参数校验失败 [{self.name}]: {e}")
                return False
        return True
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        获取工具元数据
        
        Returns:
            工具元数据字典
        """
        return {
            "name": self.name,
            "description": self.description,
            "schema": self.schema.model_json_schema() if self.schema else {}
        }


def invoke_tool(tool_class, params, executor=None):
    """Validate and normalize the common synchronous tool contract."""
    tool = tool_class(executor=executor)
    schema = tool_schema(tool_class)
    if schema is not None:
        params = {**params, **schema.model_validate(params).model_dump()}
    result = tool.execute(params)
    if isinstance(result, dict):
        if "success" not in result:
            return {"success": True, "result": result}
        if not result["success"] and "error" not in result:
            result["error"] = result.get("message", "Tool execution failed")
        return result
    if isinstance(result, str) and result.lower().startswith(("error", "failed", "unknown tool", "错误", "失败", "参数校验失败")):
        return {"success": False, "error": result}
    return {"success": True, "result": result}


def tool_schema(tool_class):
    schema = getattr(tool_class, "schema", None)
    if schema is not None:
        return schema
    from src.engine.langchain_tools import (DocumentSearchInput, MemorySearchInput, WebSearchInput,
        CodeExecutionInput, FileOperationsInput, FeishuFileReadInput)
    return {"DocumentSearchTool": DocumentSearchInput, "MemorySearchTool": MemorySearchInput,
            "WebSearchTool": WebSearchInput, "CodeExecutionTool": CodeExecutionInput,
            "SandboxedCodeExecutionTool": CodeExecutionInput, "FileOperationsTool": FileOperationsInput,
            "SandboxedFileOperationsTool": FileOperationsInput, "FeishuFileReadTool": FeishuFileReadInput}.get(tool_class.__name__)
