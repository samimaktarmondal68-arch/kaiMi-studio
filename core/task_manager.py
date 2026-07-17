from __future__ import annotations

import threading
from typing import Callable, Optional

from core.logger import get_logger


class TaskCancelledError(RuntimeError):
    """Raised when a background task is cancelled."""


class TaskManager:
    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._cancel_event = threading.Event()
        self.logger = get_logger()
        self._is_running = False
        self._current_task_name: Optional[str] = None
        self._progress = 0.0
        self._status_message: Optional[str] = None

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def current_task_name(self) -> Optional[str]:
        return self._current_task_name

    @property
    def progress(self) -> float:
        return self._progress

    @property
    def status_message(self) -> Optional[str]:
        return self._status_message

    def run_task(
        self,
        task_name: str,
        task_func: Callable[["TaskManager"], object],
        on_progress: Optional[Callable[[float, str], None]] = None,
        on_complete: Optional[Callable[[object], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> bool:
        if self._is_running:
            return False

        self._cancel_event = threading.Event()
        self._is_running = True
        self._current_task_name = task_name
        self._progress = 0.0
        self._status_message = "Starting..."

        self.logger.info("TaskManager", f"Task Started: {task_name}")
        self._thread = threading.Thread(
            target=self._execute,
            args=(task_func, on_progress, on_complete, on_error, task_name),
            daemon=True,
        )
        self._thread.start()
        return True

    def _execute(
        self,
        task_func: Callable[["TaskManager"], object],
        on_progress: Optional[Callable[[float, str], None]],
        on_complete: Optional[Callable[[object], None]],
        on_error: Optional[Callable[[Exception], None]],
        task_name: str,
    ) -> None:
        try:
            result = task_func(self)
            if self.check_cancelled():
                raise TaskCancelledError("Task was cancelled.")
            self._progress = 1.0
            self._status_message = "Completed."
            self.logger.info("TaskManager", f"Task Completed: {task_name}")
            if on_complete is not None:
                on_complete(result)
        except TaskCancelledError as exc:
            self._status_message = str(exc) or "Task was cancelled."
            self.logger.warning("TaskManager", f"Task Cancelled: {task_name}")
            if on_error is not None:
                on_error(exc)
        except Exception as exc:
            self._status_message = str(exc) or "Task failed."
            self.logger.error("TaskManager", f"Task Failed: {task_name}", exc)
            if on_error is not None:
                on_error(exc)
        finally:
            self._is_running = False
            self._current_task_name = None

    def update_progress(self, progress: float, message: Optional[str] = None) -> None:
        self._progress = max(0.0, min(1.0, float(progress)))
        if message is not None:
            self._status_message = message

    def check_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def cancel(self) -> None:
        self._cancel_event.set()
        self._status_message = "Cancelling..."
