"""工具注册表 - 管理所有原子工具的注册和路由"""

from typing import Dict, Any, Type, Optional, List
from src.logging_config import get_logger

logger = get_logger("tool.registry")

# 工具注册表
_tool_registry: Dict[str, Type] = {}


def register_tool(name: str):
    """工具注册装饰器"""
    def decorator(cls):
        _tool_registry[name] = cls
        logger.info(f"Registered tool: {name}")
        return cls
    return decorator


def get_tool(name: str) -> Optional[Type]:
    """获取工具类"""
    return _tool_registry.get(name)


def list_tools() -> Dict[str, Dict[str, Any]]:
    """获取所有已注册工具的元数据"""
    return {
        name: tool_class().get_metadata()
        for name, tool_class in _tool_registry.items()
    }


def execute_tool(name: str, params: Dict[str, Any]) -> Any:
    """执行工具"""
    tool = get_tool(name)
    if not tool:
        return f"Unknown tool: {name}"
    
    try:
        instance = tool()
        if not instance.validate_params(params):
            return f"参数校验失败: {name}"
        return instance.execute(params)
    except Exception as e:
        logger.error(f"工具执行失败 [{name}]: {str(e)}")
        return f"Error executing {name}: {str(e)}"


def clear_registry():
    """清空工具注册表"""
    _tool_registry.clear()
    logger.info("工具注册表已清空")