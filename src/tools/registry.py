from typing import Dict, Type, Any, Optional
from src.tools.base import BaseTool
from src.logging_config import get_logger

logger = get_logger("tool.registry")

_tool_registry: Dict[str, Type[BaseTool]] = {}


def register_tool(name: str):
    """
    工具注册装饰器
    
    Args:
        name: 工具名称
        
    Returns:
        装饰器函数
    """
    def decorator(cls: Type[BaseTool]) -> Type[BaseTool]:
        if not issubclass(cls, BaseTool):
            raise TypeError(f"工具类必须继承自 BaseTool: {cls.__name__}")
        
        if name in _tool_registry:
            logger.warning(f"工具已存在，将被覆盖: {name}")
        
        _tool_registry[name] = cls
        cls.name = name
        logger.info(f"工具注册成功: {name}")
        
        return cls
    return decorator


def get_tool(name: str) -> Optional[BaseTool]:
    """
    获取工具实例
    
    Args:
        name: 工具名称
        
    Returns:
        工具实例，如果不存在返回None
    """
    if name not in _tool_registry:
        logger.warning(f"工具不存在: {name}")
        return None
    
    try:
        return _tool_registry[name]()
    except Exception as e:
        logger.error(f"创建工具实例失败 [{name}]: {str(e)}")
        return None


def list_tools() -> Dict[str, Dict[str, Any]]:
    """
    获取所有已注册工具的元数据
    
    Returns:
        工具元数据字典
    """
    return {
        name: tool_class().get_metadata()
        for name, tool_class in _tool_registry.items()
    }


def execute_tool(name: str, params: Dict[str, Any]) -> Any:
    """
    执行工具
    
    Args:
        name: 工具名称
        params: 工具参数
        
    Returns:
        执行结果
    """
    tool = get_tool(name)
    if not tool:
        return f"Unknown tool: {name}"
    
    try:
        # 参数校验
        if not tool.validate_params(params):
            return f"参数校验失败: {name}"
        
        # 执行工具
        return tool.execute(params)
    except Exception as e:
        logger.error(f"工具执行失败 [{name}]: {str(e)}")
        return f"Error executing {name}: {str(e)}"


def clear_registry():
    """
    清空工具注册表（主要用于测试）
    """
    _tool_registry.clear()
    logger.info("工具注册表已清空")
