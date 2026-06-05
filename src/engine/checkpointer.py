"""共享 LangGraph Checkpointer — AsyncSqliteSaver 单例

所有 LangGraph 图（message_graph, react_engine, ppt_workflow）共用此实例。
使用 aiosqlite 异步连接 + AsyncSqliteSaver，支持 ainvoke。
"""

import os
import asyncio
from src.config import settings
from src.logging_config import get_logger

logger = get_logger("engine")

CHECKPOINT_DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(settings.DATABASE_PATH) or ".", "checkpoints.db")
)

_checkpointer = None


def get_checkpointer():
    """获取共享的 AsyncSqliteSaver 单例。

    首次调用时通过 asyncio.run() 创建 aiosqlite 连接。
    （图在模块导入时同步构建，此时无事件循环，asyncio.run() 安全）

    Returns:
        AsyncSqliteSaver 实例，不可用时返回 None
    """
    global _checkpointer

    if _checkpointer is not None:
        return _checkpointer

    try:
        import aiosqlite
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        os.makedirs(os.path.dirname(CHECKPOINT_DB_PATH), exist_ok=True)

        async def _connect():
            conn = await aiosqlite.connect(CHECKPOINT_DB_PATH)
            return AsyncSqliteSaver(conn)

        _checkpointer = asyncio.run(_connect())
        logger.info(f"[CHECKPOINTER] AsyncSqliteSaver 初始化 | path={CHECKPOINT_DB_PATH}")
        return _checkpointer

    except ImportError as e:
        logger.warning(f"[CHECKPOINTER] 依赖缺失: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"[CHECKPOINTER] 初始化失败: {str(e)}")
        return None


def reset_checkpointer():
    """重置 checkpointer 单例（测试用）"""
    global _checkpointer
    _checkpointer = None
