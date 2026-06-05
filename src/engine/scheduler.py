"""后台周期性任务调度器 — 纯 asyncio 实现，无外部依赖

用于：
  - 技能 Curator 7 天循环
  - 技能健康检查
  - 其他周期性维护任务
"""

import asyncio
from typing import Dict, Optional, Awaitable, Callable
from src.logging_config import get_logger

logger = get_logger("engine")


class BackgroundScheduler:
    """asyncio 驱动的后台周期性任务调度器"""

    def __init__(self):
        self._tasks: Dict[str, asyncio.Task] = {}
        self._running: bool = False

    async def add_periodic(self, name: str, coro_func: Callable[[], Awaitable],
                           interval_seconds: int, run_immediately: bool = False) -> str:
        """添加周期性任务

        Args:
            name: 任务名称（用于日志和取消）
            coro_func: 异步回调函数
            interval_seconds: 执行间隔（秒）
            run_immediately: True 则立即运行一次，然后按间隔循环

        Returns:
            任务名称
        """
        async def _runner():
            if not run_immediately:
                await asyncio.sleep(interval_seconds)

            while self._running:
                try:
                    logger.debug(f"[SCHEDULER] Running periodic task: {name}")
                    await coro_func()
                    logger.debug(f"[SCHEDULER] Completed periodic task: {name}")
                except Exception as e:
                    logger.error(f"[SCHEDULER] Task '{name}' failed: {e}", exc_info=True)
                await asyncio.sleep(interval_seconds)

        task = asyncio.create_task(_runner())
        self._tasks[name] = task
        logger.info(f"[SCHEDULER] Registered periodic task: {name} (interval={interval_seconds}s)")
        return name

    async def add_one_shot(self, name: str, coro_func: Callable[[], Awaitable],
                           delay_seconds: int) -> str:
        """添加一次性延迟任务

        Args:
            name: 任务名称
            coro_func: 异步回调函数
            delay_seconds: 延迟秒数

        Returns:
            任务名称
        """
        async def _runner():
            await asyncio.sleep(delay_seconds)
            try:
                logger.debug(f"[SCHEDULER] Running one-shot task: {name}")
                await coro_func()
            except Exception as e:
                logger.error(f"[SCHEDULER] One-shot task '{name}' failed: {e}", exc_info=True)

        task = asyncio.create_task(_runner())
        self._tasks[name] = task
        logger.info(f"[SCHEDULER] Scheduled one-shot task: {name} (delay={delay_seconds}s)")
        return name

    async def start(self):
        """启动调度器"""
        self._running = True
        logger.info("[SCHEDULER] Background scheduler started")

    async def stop(self):
        """停止所有任务"""
        self._running = False
        for name, task in self._tasks.items():
            if not task.done():
                task.cancel()
                logger.debug(f"[SCHEDULER] Cancelled task: {name}")
        self._tasks.clear()
        logger.info("[SCHEDULER] Background scheduler stopped")

    @property
    def running(self) -> bool:
        return self._running

    def list_tasks(self) -> Dict[str, str]:
        """列出所有已注册任务"""
        return {name: "running" if not t.done() else "done" for name, t in self._tasks.items()}


# 全局实例
scheduler = BackgroundScheduler()
