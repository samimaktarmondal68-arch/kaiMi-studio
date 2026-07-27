# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Enhanced TaskManager with queue, retry, and task history."""

from __future__ import annotations

import threading
import queue
from dataclasses import dataclass
from typing import Callable, Optional
from datetime import datetime

from core.logger import get_logger


class TaskCancelledError(RuntimeError):
    """Raised when a background task is cancelled."""


@dataclass
class TaskRecord:
    name: str
    status: str = "pending"
    progress: float = 0.0
    message: str = ""
    created: str = ""
    completed: str = ""
    error: str = ""
    result: object = None


class TaskManager:

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._cancel_event = threading.Event()
        self.logger = get_logger()
        self._is_running = False
        self._current_task_name: Optional[str] = None
        self._progress = 0.0
        self._status_message: Optional[str] = None
        self._task_queue: queue.Queue = queue.Queue()
        self._history: list[TaskRecord] = []
        self._max_history = 50

    @property
    def progress(self) -> float:
        return self._progress

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def current_task_name(self) -> Optional[str]:
        return self._current_task_name

    @property
    def history(self) -> list[TaskRecord]:
        return list(self._history)

    def run_task(
        self,
        task_name: str,
        task_func: Callable[["TaskManager"], object],
        on_complete: Optional[Callable[[object], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> bool:
        if self._is_running:
            self._task_queue.put((task_name, task_func, on_complete, on_error))
            self.logger.info("TaskManager", f"Task queued: {task_name}")
            return False

        self._cancel_event = threading.Event()
        self._is_running = True
        self._current_task_name = task_name
        self._progress = 0.0
        self._status_message = "Starting..."

        record = TaskRecord(
            name=task_name,
            status="running",
            created=datetime.now().strftime("%d-%m-%Y %H:%M"),
        )
        self._history.insert(0, record)
        if len(self._history) > self._max_history:
            self._history = self._history[:self._max_history]

        self.logger.info("TaskManager", f"Task Started: {task_name}")
        self._thread = threading.Thread(
            target=self._execute,
            args=(task_func, on_complete, on_error, task_name, record),
            daemon=True,
        )
        self._thread.start()
        return True

    def _execute(
        self,
        task_func: Callable[["TaskManager"], object],
        on_complete: Optional[Callable[[object], None]],
        on_error: Optional[Callable[[Exception], None]],
        task_name: str,
        record: TaskRecord,
    ) -> None:
        try:
            result = task_func(self)
            if self.check_cancelled():
                raise TaskCancelledError("Task was cancelled.")
            self._progress = 1.0
            self._status_message = "Completed."
            record.status = "completed"
            record.progress = 1.0
            record.completed = datetime.now().strftime("%d-%m-%Y %H:%M")
            record.result = result
            self.logger.info("TaskManager", f"Task Completed: {task_name}")
            if on_complete is not None:
                on_complete(result)
        except TaskCancelledError as exc:
            self._status_message = str(exc) or "Task was cancelled."
            record.status = "cancelled"
            record.error = str(exc)
            record.completed = datetime.now().strftime("%d-%m-%Y %H:%M")
            self.logger.warning("TaskManager", f"Task Cancelled: {task_name}")
            if on_error is not None:
                on_error(exc)
        except Exception as exc:
            self._status_message = str(exc) or "Task failed."
            record.status = "failed"
            record.error = str(exc)
            record.completed = datetime.now().strftime("%d-%m-%Y %H:%M")
            self.logger.error("TaskManager", f"Task Failed: {task_name}", exc)
            if on_error is not None:
                on_error(exc)
        finally:
            self._is_running = False
            self._current_task_name = None
            self._process_queue()

    def _process_queue(self):
        if not self._task_queue.empty():
            task_name, task_func, on_complete, on_error = self._task_queue.get()
            self.run_task(task_name, task_func, on_complete, on_error)

    def update_progress(self, progress: float, message: Optional[str] = None) -> None:
        self._progress = max(0.0, min(1.0, float(progress)))
        if message is not None:
            self._status_message = message
        if self._history and self._history[0].status == "running":
            self._history[0].progress = self._progress
            self._history[0].message = message or ""

    def check_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def cancel(self) -> None:
        self._cancel_event.set()
        self._status_message = "Cancelling..."
        if self._history and self._history[0].status == "running":
            self._history[0].status = "cancelling"

    def retry_last(self, task_func, on_complete=None, on_error=None):
        if not self._history:
            return False
        last = self._history[0]
        if last.status not in ("failed", "cancelled"):
            return False
        return self.run_task(last.name, task_func, on_complete, on_error)

    def clear_history(self):
        self._history.clear()

    def get_queue_size(self) -> int:
        return self._task_queue.qsize()
