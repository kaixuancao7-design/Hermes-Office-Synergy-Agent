"""Create SQLite checkpoints lazily on the service event loop."""
import os
from src.config import settings
from src.logging_config import get_logger

logger = get_logger("engine")
CHECKPOINT_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(settings.DATABASE_PATH) or ".", "checkpoints.db"))
_checkpointer = None


def get_checkpointer():
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer
    try:
        import asyncio
        import aiosqlite
        from langgraph.checkpoint.base import BaseCheckpointSaver
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        class LazySqliteSaver(BaseCheckpointSaver):
            def __init__(self):
                super().__init__()
                self.saver = None
                self.loop = None
                self.init_lock = asyncio.Lock()

            async def _get(self):
                async with self.init_lock:
                    loop = asyncio.get_running_loop()
                    if self.saver is not None:
                        if self.loop is not loop:
                            raise RuntimeError("Checkpointer must run on its owning service event loop")
                        return self.saver
                    os.makedirs(os.path.dirname(CHECKPOINT_DB_PATH), exist_ok=True)
                    conn = await aiosqlite.connect(CHECKPOINT_DB_PATH)
                    self.saver = AsyncSqliteSaver(conn)
                    self.loop = loop
                    return self.saver

            async def aget_tuple(self, config):
                return await (await self._get()).aget_tuple(config)

            async def alist(self, config, **kwargs):
                async for item in (await self._get()).alist(config, **kwargs):
                    yield item

            async def aput(self, config, checkpoint, metadata, new_versions):
                return await (await self._get()).aput(config, checkpoint, metadata, new_versions)

            async def aput_writes(self, config, writes, task_id, task_path=""):
                return await (await self._get()).aput_writes(config, writes, task_id, task_path)

            async def adelete_thread(self, thread_id):
                return await (await self._get()).adelete_thread(thread_id)

            def get_next_version(self, current, channel):
                if self.saver is None:
                    return super().get_next_version(current, channel)
                return self.saver.get_next_version(current, channel)

            async def close(self):
                if self.saver is not None:
                    await self.saver.conn.close()
                    self.saver = None
                    self.loop = None

        _checkpointer = LazySqliteSaver()
        return _checkpointer
    except ImportError as exc:
        logger.warning(f"[CHECKPOINTER] Dependency unavailable: {exc}")
        return None


async def close_checkpointer():
    global _checkpointer
    if _checkpointer is not None:
        await _checkpointer.close()
        _checkpointer = None


def reset_checkpointer():
    global _checkpointer
    if _checkpointer is not None and _checkpointer.saver is not None:
        raise RuntimeError("Await close_checkpointer() before resetting an active connection")
    _checkpointer = None
