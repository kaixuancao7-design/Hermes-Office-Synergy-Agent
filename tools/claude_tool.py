"""Claude风格的工具调用封装"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from tools.base import BaseTool
from tools.registry import get_tool, execute_tool
from src.logging_config import get_logger

logger = get_logger("tool.claude")


class ToolCall(BaseModel):
    """标准工具调用格式"""
    name: str = Field(description="工具名称")
    parameters: Dict[str, Any] = Field(description="工具参数")
    id: Optional[str] = Field(description="调用ID", default=None)


class ToolResult(BaseModel):
    """标准工具返回格式"""
    tool_call_id: str = Field(description="调用ID")
    content: Dict[str, Any] = Field(description="返回内容")
    is_error: bool = Field(description="是否错误", default=False)
    error: Optional[str] = Field(description="错误信息")


class ClaudeToolExecutor:
    """Claude风格的工具执行器"""
    
    def call_tool(self, tool_call: ToolCall) -> ToolResult:
        """执行工具调用"""
        tool_call_id = tool_call.id or self._generate_id()
        
        try:
            result = execute_tool(tool_call.name, tool_call.parameters)
            
            if isinstance(result, dict) and result.get("success") is False:
                return ToolResult(
                    tool_call_id=tool_call_id,
                    content={},
                    is_error=True,
                    error=result.get("error", "Unknown error")
                )
            
            return ToolResult(
                tool_call_id=tool_call_id,
                content=result if isinstance(result, dict) else {"result": result},
                is_error=False
            )
        
        except Exception as e:
            return ToolResult(
                tool_call_id=tool_call_id,
                content={},
                is_error=True,
                error=str(e)
            )
    
    def get_tool_info(self, tool_name: str) -> Dict[str, Any]:
        """获取工具元信息"""
        tool = get_tool(tool_name)
        if not tool:
            return {}
        
        return {
            "name": tool.name,
            "description": tool.description,
            "schema": tool.schema.model_json_schema() if tool.schema else {}
        }
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """获取所有工具列表"""
        from tools.registry import list_tools
        tools = list_tools()
        return [{
            "name": name,
            "description": meta.get("description"),
            "schema": meta.get("schema", {})
        } for name, meta in tools.items()]
    
    def _generate_id(self) -> str:
        """生成唯一ID"""
        import uuid
        return str(uuid.uuid4())