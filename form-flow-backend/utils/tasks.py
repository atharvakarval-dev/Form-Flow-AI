"""
Background Task Queue

Provides lightweight async task queue for non-blocking operations.
Runs heavy tasks (form scraping, submission) in the background.

Usage:
    from utils.tasks import task_queue, enqueue_task
    
    # Submit a background task
    task_id = await enqueue_task(scrape_form_task, url="https://...")
    
    # Check status
    status = await get_task_status(task_id)
"""

import asyncio
import uuid
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime
from enum import Enum

from utils.logging import get_logger
from utils.cache import get_cached, set_cached

logger = get_logger(__name__)


class TaskStatus(str, Enum):
    """Task status enum."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# In-memory task storage (use Redis in production for persistence)
_tasks: Dict[str, Dict[str, Any]] = {}
_task_queue: asyncio.Queue = None
_worker_running = False


async def _get_queue() -> asyncio.Queue:
    """Get or create the task queue."""
    global _task_queue
    if _task_queue is None:
        _task_queue = asyncio.Queue(maxsize=100)
    return _task_queue


async def enqueue_task(
    func: Callable[..., Awaitable[Any]],
    task_name: str = None,
    **kwargs
) -> str:
    """
    Enqueue a task for background execution.
    
    Args:
        func: Async function to execute
        task_name: Human-readable task name
        **kwargs: Arguments to pass to the function
        
    Returns:
        str: Task ID for status checking
    """
    task_id = str(uuid.uuid4())[:8]
    
    task_info = {
        "id": task_id,
        "name": task_name or func.__name__,
        "status": TaskStatus.PENDING,
        "created_at": datetime.utcnow().isoformat(),
        "started_at": None,
        "completed_at": None,
        "result": None,
        "error": None,
    }
    
    _tasks[task_id] = task_info
    
    # Cache task info
    await set_cached(f"task:{task_id}", task_info, ttl=3600)
    
    # Add to queue
    queue = await _get_queue()
    await queue.put((task_id, func, kwargs))
    
    logger.info(f"Task enqueued: {task_id} ({task_info['name']})")
    
    # Ensure worker is running
    await _ensure_worker()
    
    return task_id


async def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the status of a task.
    
    Args:
        task_id: Task ID
        
    Returns:
        Task info dict or None if not found
    """
    # Check memory first
    if task_id in _tasks:
        return _tasks[task_id]
    
    # Check cache
    cached = await get_cached(f"task:{task_id}")
    return cached


async def _ensure_worker():
    """Ensure the background worker is running."""
    global _worker_running
    
    if not _worker_running:
        _worker_running = True
        asyncio.create_task(_background_worker())
        logger.info("Background task worker started")


async def _background_worker():
    """
    Background worker that processes tasks from the queue.
    
    Runs continuously and picks tasks from the queue.
    """
    global _worker_running
    
    queue = await _get_queue()
    
    while True:
        try:
            # Wait for a task (with timeout to allow graceful shutdown)
            try:
                task_id, func, kwargs = await asyncio.wait_for(
                    queue.get(),
                    timeout=60
                )
            except asyncio.TimeoutError:
                continue
            
            # Update status to running
            if task_id in _tasks:
                _tasks[task_id]["status"] = TaskStatus.RUNNING
                _tasks[task_id]["started_at"] = datetime.utcnow().isoformat()
            
            logger.info(f"Task started: {task_id}")
            
            try:
                # Execute the task
                result = await func(**kwargs)
                
                # Update status to completed
                if task_id in _tasks:
                    _tasks[task_id]["status"] = TaskStatus.COMPLETED
                    _tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
                    _tasks[task_id]["result"] = result
                
                logger.info(f"Task completed: {task_id}")
                
            except Exception as e:
                # Update status to failed
                if task_id in _tasks:
                    _tasks[task_id]["status"] = TaskStatus.FAILED
                    _tasks[task_id]["error"] = str(e)
                
                logger.error(f"Task failed: {task_id} - {e}")
            
            # Update cache
            if task_id in _tasks:
                await set_cached(f"task:{task_id}", _tasks[task_id], ttl=3600)
            
            queue.task_done()
            
        except Exception as e:
            logger.error(f"Worker error: {e}")
            await asyncio.sleep(1)


def get_queue_stats() -> Dict[str, Any]:
    """Get queue statistics."""
    pending = sum(1 for t in _tasks.values() if t["status"] == TaskStatus.PENDING)
    running = sum(1 for t in _tasks.values() if t["status"] == TaskStatus.RUNNING)
    completed = sum(1 for t in _tasks.values() if t["status"] == TaskStatus.COMPLETED)
    failed = sum(1 for t in _tasks.values() if t["status"] == TaskStatus.FAILED)
    
    return {
        "pending": pending,
        "running": running,
        "completed": completed,
        "failed": failed,
        "total": len(_tasks),
        "worker_running": _worker_running,
    }
