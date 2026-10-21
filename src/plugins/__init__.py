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

# MCP Server 实例
mcp_server = None


component_status: Dict[str, str] = {}


def init_plugins(config: Dict[str, Any] = None) -> bool:
    """Initialize required office components; IM remains an optional integration.

    Status values contain no configuration or exception text and may be published
    by readiness probes. Construction checks local initialization, not remote health.
    """
    component_status.clear()
    _check_vector_migration()
    _init_mcp_server()
    required_ok = True
    definitions = (
        ("model_router", MODEL_ROUTER_REGISTRY, settings.MODEL_ROUTER_TYPE, True),
        ("memory_store", MEMORY_STORE_REGISTRY, settings.MEMORY_STORE_TYPE, True),
        ("skill_manager", SKILL_MANAGER_REGISTRY, settings.SKILL_MANAGER_TYPE, True),
        ("tool_executor", TOOL_EXECUTOR_REGISTRY, settings.TOOL_EXECUTOR_TYPE, True),
        ("im_adapter", IM_ADAPTER_REGISTRY, settings.IM_ADAPTER_TYPE, False),
    )
    for name, _, _, _ in definitions:
        globals()[name] = None
    for name, registry, default, required in definitions:
        plugin_type = (config or {}).get(name, default)
        try:
            if plugin_type not in registry:
                raise ValueError(f"Unknown plugin type for {name}")
            globals()[name] = registry[plugin_type]()
            component_status[name] = "ready"
        except Exception:
            component_status[name] = "failed"
            logger.exception("Plugin initialization failed: %s", name)
            if required:
                required_ok = False
                break
    return required_ok


async def close_plugins():
    """Release initialized plugins, including a partially completed startup."""
    import inspect
    for name in ("im_adapter", "tool_executor", "skill_manager", "memory_store", "model_router"):
        instance = globals()[name]
        globals()[name] = None
        if instance is None:
            continue
        close = getattr(instance, "close", None) or getattr(instance, "stop", None)
        if close:
            try:
                result = close()
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception("Plugin cleanup failed: %s", name)
    component_status.clear()


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


def _check_vector_migration():
    """检查并执行向量数据迁移"""
    try:
        from src.tools.vector_migration import VectorMigrationTool

        migration_tool = VectorMigrationTool()
        migration_tool.run_auto_migration()
    except ImportError:
        logger.warning("向量迁移工具未找到，跳过迁移检测")
    except Exception as e:
        logger.error(f"向量迁移检测失败: {str(e)}")


def _init_mcp_server():
    """初始化 MCP Server（基于官方 Python MCP SDK）"""
    global mcp_server

    try:
        from src.engine.mcp_server import mcp as official_mcp

        mcp_server = official_mcp
        logger.info("MCP Server 初始化成功（基于官方 Python MCP SDK）")
    except ImportError as e:
        logger.warning(f"MCP Server 初始化失败: {str(e)}")
        mcp_server = None
    except Exception as e:
        logger.error(f"MCP Server 初始化异常: {str(e)}")
        mcp_server = None


def get_mcp_server():
    """获取 MCP Server 实例"""
    global mcp_server

    if mcp_server is None:
        _init_mcp_server()

    return mcp_server


# 导出注册表供外部使用
__all__ = [
    "init_plugins",
    "get_im_adapter",
    "get_model_router",
    "get_memory_store",
    "get_skill_manager",
    "get_tool_executor",
    "get_mcp_server",
    "IM_ADAPTER_REGISTRY",
    "MODEL_ROUTER_REGISTRY",
    "MEMORY_STORE_REGISTRY",
    "SKILL_MANAGER_REGISTRY",
    "TOOL_EXECUTOR_REGISTRY"
]
