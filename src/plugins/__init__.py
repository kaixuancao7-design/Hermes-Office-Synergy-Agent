"""插件系统初始化模块"""
from typing import Dict, Any, Optional

from src.config import settings
from src.plugins.base import (
    IMAdapterBase,
    ModelRouterBase,
    MemoryBase,
    SkillManagerBase,
    ToolExecutorBase
)
from src.plugins.im_adapters import IM_ADAPTER_REGISTRY
from src.plugins.model_routers import MODEL_ROUTER_REGISTRY
from src.plugins.memory_stores import MEMORY_STORE_REGISTRY
from src.plugins.skill_managers import SKILL_MANAGER_REGISTRY
from src.plugins.tool_executors import TOOL_EXECUTOR_REGISTRY
from src.logging_config import get_logger

logger = get_logger("gateway")

# 全局插件实例
im_adapter: Optional[IMAdapterBase] = None
model_router: Optional[ModelRouterBase] = None
memory_store: Optional[MemoryBase] = None
skill_manager: Optional[SkillManagerBase] = None
tool_executor: Optional[ToolExecutorBase] = None


def init_plugins(config: Dict[str, Any] = None) -> bool:
    """初始化所有插件"""
    global im_adapter, model_router, memory_store, skill_manager, tool_executor
    
    try:
        # 初始化IM适配器
        im_adapter_type = config.get("im_adapter", settings.IM_ADAPTER_TYPE) if config else settings.IM_ADAPTER_TYPE
        if im_adapter_type in IM_ADAPTER_REGISTRY:
            im_adapter = IM_ADAPTER_REGISTRY[im_adapter_type]()
            logger.info(f"初始化IM适配器: {im_adapter_type}")
        else:
            logger.warning(f"未找到IM适配器类型: {im_adapter_type}")
        
        # 初始化模型路由
        model_router_type = config.get("model_router", settings.MODEL_ROUTER_TYPE) if config else settings.MODEL_ROUTER_TYPE
        if model_router_type in MODEL_ROUTER_REGISTRY:
            model_router = MODEL_ROUTER_REGISTRY[model_router_type]()
            logger.info(f"初始化模型路由: {model_router_type}")
        else:
            logger.warning(f"未找到模型路由类型: {model_router_type}")
        
        # 初始化记忆存储
        memory_store_type = config.get("memory_store", settings.MEMORY_STORE_TYPE) if config else settings.MEMORY_STORE_TYPE
        if memory_store_type in MEMORY_STORE_REGISTRY:
            memory_store = MEMORY_STORE_REGISTRY[memory_store_type]()
            logger.info(f"初始化记忆存储: {memory_store_type}")
        else:
            logger.warning(f"未找到记忆存储类型: {memory_store_type}")
        
        # 初始化技能管理器
        skill_manager_type = config.get("skill_manager", settings.SKILL_MANAGER_TYPE) if config else settings.SKILL_MANAGER_TYPE
        if skill_manager_type in SKILL_MANAGER_REGISTRY:
            skill_manager = SKILL_MANAGER_REGISTRY[skill_manager_type]()
            logger.info(f"初始化技能管理器: {skill_manager_type}")
        else:
            logger.warning(f"未找到技能管理器类型: {skill_manager_type}")
        
        # 初始化工具执行器
        tool_executor_type = config.get("tool_executor", settings.TOOL_EXECUTOR_TYPE) if config else settings.TOOL_EXECUTOR_TYPE
        if tool_executor_type in TOOL_EXECUTOR_REGISTRY:
            tool_executor = TOOL_EXECUTOR_REGISTRY[tool_executor_type]()
            logger.info(f"初始化工具执行器: {tool_executor_type}")
        else:
            logger.warning(f"未找到工具执行器类型: {tool_executor_type}")
        
        logger.info("所有插件初始化完成")
        return True
    
    except Exception as e:
        logger.error(f"插件初始化失败: {str(e)}")
        return False


def get_im_adapter(im_type: Optional[str] = None) -> Optional[IMAdapterBase]:
    """获取IM适配器实例
    
    Args:
        im_type: IM适配器类型，如果为None则返回全局初始化的适配器
    
    Returns:
        IM适配器实例
    """
    global im_adapter
    
    if im_type is None:
        return im_adapter
    
    # 根据指定类型获取适配器
    if im_type in IM_ADAPTER_REGISTRY:
        try:
            adapter = IM_ADAPTER_REGISTRY[im_type]()
            logger.info(f"动态获取IM适配器: {im_type}")
            return adapter
        except Exception as e:
            logger.error(f"创建IM适配器失败: {im_type}, 错误: {str(e)}")
            return None
    else:
        logger.warning(f"未找到IM适配器类型: {im_type}")
        return None


def get_model_router() -> Optional[ModelRouterBase]:
    """获取模型路由实例"""
    return model_router


def get_memory_store() -> Optional[MemoryBase]:
    """获取记忆存储实例"""
    return memory_store


def get_skill_manager() -> Optional[SkillManagerBase]:
    """获取技能管理器实例"""
    return skill_manager


def get_tool_executor() -> Optional[ToolExecutorBase]:
    """获取工具执行器实例"""
    return tool_executor


# 导出注册表供外部使用
__all__ = [
    "init_plugins",
    "get_im_adapter",
    "get_model_router",
    "get_memory_store",
    "get_skill_manager",
    "get_tool_executor",
    "IM_ADAPTER_REGISTRY",
    "MODEL_ROUTER_REGISTRY",
    "MEMORY_STORE_REGISTRY",
    "SKILL_MANAGER_REGISTRY",
    "TOOL_EXECUTOR_REGISTRY"
]
