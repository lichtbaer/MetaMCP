"""
Background Task Manager

This module provides a background task manager for asynchronous task execution
and performance optimization.
"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from ..config import get_settings
from ..utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class TaskStatus(Enum):
    """Task status enumeration."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Task priority enumeration."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class TaskInfo:
    """Task information."""

    id: str
    name: str
    status: TaskStatus
    priority: TaskPriority
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    retries: int = 0
    max_retries: int = 3
    execution_time: Optional[float] = None


class BackgroundTaskManager:
    """Background task manager for performance optimization."""

    def __init__(self, max_workers: int = None):
        """Initialize background task manager."""
        self.max_workers = max_workers or settings.worker_threads
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self._tasks: Dict[str, TaskInfo] = {}
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._workers: List[asyncio.Task] = []
        self._lock = asyncio.Lock()

    async def start(self):
        """Start the background task manager."""
        if self._running:
            return

        self._running = True
        logger.info(f"Starting background task manager with {self.max_workers} workers")

        # Start worker tasks
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self._workers.append(worker)

    async def stop(self):
        """Stop the background task manager."""
        if not self._running:
            return

        self._running = False
        logger.info("Stopping background task manager")

        # Cancel all workers
        for worker in self._workers:
            worker.cancel()

        # Wait for workers to finish
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

        # Shutdown executor
        self._executor.shutdown(wait=True)

    async def submit_task(
        self,
        func: Callable,
        *args,
        name: str = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int = 3,
        **kwargs,
    ) -> str:
        """Submit a task for background execution."""
        task_id = str(uuid4())
        task_name = name or func.__name__

        # Create task info
        task_info = TaskInfo(
            id=task_id,
            name=task_name,
            status=TaskStatus.PENDING,
            priority=priority,
            created_at=datetime.now(),
            max_retries=max_retries,
        )

        # Store task info
        async with self._lock:
            self._tasks[task_id] = task_info

        # Add to queue with priority
        await self._task_queue.put((priority.value, task_id, func, args, kwargs))

        logger.debug(f"Submitted task {task_id}: {task_name}")
        return task_id

    async def get_task_status(self, task_id: str) -> Optional[TaskInfo]:
        """Get task status."""
        async with self._lock:
            return self._tasks.get(task_id)

    async def get_task_result(self, task_id: str, timeout: float = None) -> Any:
        """Get task result, waiting if necessary."""
        start_time = time.time()

        while True:
            task_info = await self.get_task_status(task_id)

            if task_info is None:
                raise ValueError(f"Task {task_id} not found")

            if task_info.status == TaskStatus.COMPLETED:
                return task_info.result

            if task_info.status == TaskStatus.FAILED:
                raise Exception(f"Task failed: {task_info.error}")

            if task_info.status == TaskStatus.CANCELLED:
                raise Exception("Task was cancelled")

            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                raise asyncio.TimeoutError(f"Task {task_id} timed out")

            # Wait before checking again
            await asyncio.sleep(0.1)

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        async with self._lock:
            task_info = self._tasks.get(task_id)
            if task_info and task_info.status == TaskStatus.PENDING:
                task_info.status = TaskStatus.CANCELLED
                logger.info(f"Cancelled task {task_id}: {task_info.name}")
                return True
        return False

    async def get_all_tasks(self) -> List[TaskInfo]:
        """Get all tasks."""
        async with self._lock:
            return list(self._tasks.values())

    async def cleanup_completed_tasks(self, max_age_hours: int = 24):
        """Clean up completed tasks older than specified age."""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

        async with self._lock:
            tasks_to_remove = [
                task_id
                for task_id, task_info in self._tasks.items()
                if (
                    task_info.status
                    in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
                    and task_info.completed_at
                    and task_info.completed_at < cutoff_time
                )
            ]

            for task_id in tasks_to_remove:
                del self._tasks[task_id]

            if tasks_to_remove:
                logger.info(f"Cleaned up {len(tasks_to_remove)} completed tasks")

    async def _worker(self, worker_name: str):
        """Worker task that processes the task queue."""
        logger.debug(f"Started worker: {worker_name}")

        while self._running:
            try:
                # Get task from queue
                priority, task_id, func, args, kwargs = await asyncio.wait_for(
                    self._task_queue.get(), timeout=1.0
                )

                # Update task status
                async with self._lock:
                    task_info = self._tasks.get(task_id)
                    if task_info and task_info.status == TaskStatus.PENDING:
                        task_info.status = TaskStatus.RUNNING
                        task_info.started_at = datetime.now()

                if task_info is None:
                    continue

                # Execute task
                start_time = time.time()
                try:
                    # Check if function is async
                    if asyncio.iscoroutinefunction(func):
                        result = await func(*args, **kwargs)
                    else:
                        # Run sync function in thread pool
                        loop = asyncio.get_event_loop()
                        result = await loop.run_in_executor(
                            self._executor, func, *args, **kwargs
                        )

                    # Update task info
                    async with self._lock:
                        task_info.status = TaskStatus.COMPLETED
                        task_info.completed_at = datetime.now()
                        task_info.result = result
                        task_info.execution_time = time.time() - start_time

                    logger.debug(
                        f"Task {task_id} completed in {task_info.execution_time:.2f}s"
                    )

                except Exception as e:
                    # Handle task failure
                    async with self._lock:
                        task_info.error = str(e)
                        task_info.retries += 1

                        if task_info.retries < task_info.max_retries:
                            # Retry task
                            task_info.status = TaskStatus.PENDING
                            await self._task_queue.put(
                                (priority, task_id, func, args, kwargs)
                            )
                            logger.warning(
                                f"Retrying task {task_id} (attempt {task_info.retries})"
                            )
                        else:
                            # Mark as failed
                            task_info.status = TaskStatus.FAILED
                            task_info.completed_at = datetime.now()
                            task_info.execution_time = time.time() - start_time
                            logger.error(
                                f"Task {task_id} failed after {task_info.retries} retries: {e}"
                            )

                finally:
                    self._task_queue.task_done()
            except asyncio.TimeoutError:
                # Timeout waiting for task, continue to next iteration
                continue
            except Exception as e:
                # Handle any other exceptions in the worker loop
                logger.error(f"Worker {worker_name} encountered error: {e}")
                continue

        logger.debug(f"Stopped worker: {worker_name}")

    async def get_stats(self) -> Dict[str, Any]:
        """Get task manager statistics."""
        async with self._lock:
            total_tasks = len(self._tasks)
            pending_tasks = sum(
                1 for t in self._tasks.values() if t.status == TaskStatus.PENDING
            )
            running_tasks = sum(
                1 for t in self._tasks.values() if t.status == TaskStatus.RUNNING
            )
            completed_tasks = sum(
                1 for t in self._tasks.values() if t.status == TaskStatus.COMPLETED
            )
            failed_tasks = sum(
                1 for t in self._tasks.values() if t.status == TaskStatus.FAILED
            )
            cancelled_tasks = sum(
                1 for t in self._tasks.values() if t.status == TaskStatus.CANCELLED
            )

            return {
                "total_tasks": total_tasks,
                "pending_tasks": pending_tasks,
                "running_tasks": running_tasks,
                "completed_tasks": completed_tasks,
                "failed_tasks": failed_tasks,
                "cancelled_tasks": cancelled_tasks,
                "queue_size": self._task_queue.qsize(),
                "active_workers": len(self._workers),
                "max_workers": self.max_workers,
            }


# Global task manager instance
_task_manager: Optional[BackgroundTaskManager] = None


def get_task_manager() -> BackgroundTaskManager:
    """Get global task manager instance."""
    global _task_manager
    if _task_manager is None:
        _task_manager = BackgroundTaskManager()
    return _task_manager


async def submit_background_task(
    func: Callable,
    *args,
    name: str = None,
    priority: TaskPriority = TaskPriority.NORMAL,
    **kwargs,
) -> str:
    """Submit a background task."""
    task_manager = get_task_manager()
    return await task_manager.submit_task(
        func, *args, name=name, priority=priority, **kwargs
    )


async def start_background_tasks():
    """Start the global background task manager."""
    task_manager = get_task_manager()
    await task_manager.start()


async def stop_background_tasks():
    """Stop the global background task manager."""
    task_manager = get_task_manager()
    await task_manager.stop()
