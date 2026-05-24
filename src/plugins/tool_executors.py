"""工具执行器插件实现"""
from typing import Dict, Any, Optional, List
from src.plugins.base import ToolExecutorBase
from src.config import settings
from src.logging_config import get_logger

logger = get_logger("tool")


class DefaultToolExecutor(ToolExecutorBase):
    """默认工具执行器"""
    
    def __init__(self):
        self.tools = {}
        self._load_tools()
    
    def _load_tools(self):
        """加载可用工具"""
        try:
            from src.tools import register_tools
            self.tools = register_tools()
            logger.info(f"加载了 {len(self.tools)} 个工具")
        except Exception as e:
            logger.error(f"加载工具失败: {str(e)}")
    
    def register_tool(self, tool_id: str, tool_class: Any) -> bool:
        """注册工具"""
        self.tools[tool_id] = tool_class()
        return True
    
    def get_tools(self) -> List[str]:
        """获取所有工具"""
        return list(self.tools.keys())
    
    def execute(self, tool_id: str, params: dict) -> dict:
        """执行工具"""
        try:
            if tool_id not in self.tools:
                logger.error(f"未找到工具: {tool_id}")
                return {"success": False, "error": f"工具 {tool_id} 不存在"}
            
            tool = self.tools[tool_id]
            
            logger.info(f"执行工具: {tool_id}, 参数: {params}")
            
            try:
                result = tool(params)
                
                if result is None:
                    return {"success": True, "result": None}
                
                if isinstance(result, dict) and "success" in result:
                    return result
                
                return {"success": True, "result": result}
            
            except Exception as e:
                logger.error(f"工具执行失败: {tool_id}, 错误: {str(e)}")
                return {"success": False, "error": str(e)}
        
        except Exception as e:
            logger.error(f"工具执行器异常: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def list_tools(self) -> List[str]:
        """列出可用工具"""
        return list(self.tools.keys())
    
    def get_tool_info(self, tool_id: str) -> Optional[dict]:
        """获取工具信息"""
        if tool_id not in self.tools:
            return None
        
        tool = self.tools[tool_id]
        return {
            "tool_id": tool_id,
            "description": getattr(tool, "__doc__", ""),
            "parameters": {}
        }
    
    def get_executor_type(self) -> str:
        return "default"


class ReActToolExecutor(ToolExecutorBase):
    """ReAct模式工具执行器"""
    
    def __init__(self):
        self.tools = {}
        self._load_tools()
    
    def _load_tools(self):
        """加载可用工具"""
        try:
            from src.tools import register_tools
            self.tools = register_tools()
            logger.info(f"ReAct执行器加载了 {len(self.tools)} 个工具")
        except Exception as e:
            logger.error(f"加载工具失败: {str(e)}")
    
    def register_tool(self, tool_id: str, tool_class: Any) -> bool:
        """注册工具"""
        self.tools[tool_id] = tool_class()
        return True
    
    def get_tools(self) -> List[str]:
        """获取所有工具"""
        return list(self.tools.keys())
    
    def execute(self, tool_id: str, params: dict) -> dict:
        """执行工具（带ReAct模式支持）"""
        try:
            if tool_id not in self.tools:
                logger.error(f"未找到工具: {tool_id}")
                return {"success": False, "error": f"工具 {tool_id} 不存在"}
            
            tool = self.tools[tool_id]
            
            logger.info(f"[ReAct] 执行工具: {tool_id}")
            
            # ReAct模式：记录执行信息
            try:
                result = tool(params)
                
                if result is None:
                    return {"success": True, "result": None, "thought": "工具执行完成"}
                
                if isinstance(result, dict) and "success" in result:
                    return result
                
                return {
                    "success": True,
                    "result": result,
                    "thought": "工具执行成功"
                }
            
            except Exception as e:
                logger.error(f"工具执行失败: {tool_id}, 错误: {str(e)}")
                return {
                    "success": False,
                    "error": str(e),
                    "thought": f"工具执行失败: {str(e)}"
                }
        
        except Exception as e:
            logger.error(f"工具执行器异常: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "thought": f"执行器异常: {str(e)}"
            }
    
    def list_tools(self) -> List[str]:
        """列出可用工具"""
        return list(self.tools.keys())
    
    def get_tool_info(self, tool_id: str) -> Optional[dict]:
        """获取工具信息（带ReAct格式）"""
        if tool_id not in self.tools:
            return None
        
        tool = self.tools[tool_id]
        return {
            "tool_id": tool_id,
            "description": getattr(tool, "__doc__", ""),
            "parameters": {},
            "react_support": True
        }
    
    def get_executor_type(self) -> str:
        return "react"


# 工具执行器注册表
TOOL_EXECUTOR_REGISTRY = {
    "default": DefaultToolExecutor,
    "react": ReActToolExecutor
}
