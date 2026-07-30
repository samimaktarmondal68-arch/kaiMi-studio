from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Callable, Optional

from PySide6.QtCore import QObject, QThread, Signal

from core.logger import get_logger


class JobStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobRecord:
    __slots__ = ("id", "name", "status", "progress", "message",
                 "created", "completed", "error", "result")

    def __init__(self, name: str):
        self.id: str = ""
        self.name: str = name
        self.status: JobStatus = JobStatus.QUEUED
        self.progress: float = 0.0
        self.message: str = ""
        self.created: str = datetime.now().strftime("%H:%M:%S")
        self.completed: str = ""
        self.error: str = ""
        self.result: object = None


class JobTask:
    __slots__ = ("fn", "args", "kwargs")

    def __init__(self, fn, args, kwargs):
        self.fn = fn
        self.args = args
        self.kwargs = kwargs


class JobWorker(QObject):
    progress_changed = Signal(float, str)
    finished = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            def report(p: float, msg: str = ""):
                self.progress_changed.emit(p, msg)

            result = self._fn(report, *self._args, **self._kwargs)
            if self._cancelled:
                self.error_occurred.emit("Cancelled")
            else:
                self.finished.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))


class TaskCenter(QObject):
    job_queued = Signal(str, str)
    job_started = Signal(str, str)
    job_progress = Signal(str, str, float, str)
    job_completed = Signal(str, str)
    job_failed = Signal(str, str, str)
    job_cancelled = Signal(str, str)
    all_completed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._logger = get_logger()
        self._jobs: dict[str, JobRecord] = {}
        self._tasks: dict[str, JobTask] = {}
        self._queue: list[str] = []
        self._thread: Optional[QThread] = None
        self._worker: Optional[JobWorker] = None
        self._current_job_id: Optional[str] = None
        self._max_history = 50

    @property
    def current_job_id(self) -> Optional[str]:
        return self._current_job_id

    @property
    def is_running(self) -> bool:
        return self._current_job_id is not None

    def submit(self, name: str, fn: Callable, *args, **kwargs) -> str:
        import uuid
        job_id = uuid.uuid4().hex[:8]
        record = JobRecord(name)
        record.id = job_id
        self._jobs[job_id] = record
        self._tasks[job_id] = JobTask(fn, args, kwargs)
        self._queue.append(job_id)
        self.job_queued.emit(job_id, name)
        self._logger.info("TaskCenter", f"Job queued: {name} [{job_id}]")
        if not self.is_running:
            self._run_next()
        return job_id

    def _run_next(self):
        if not self._queue:
            self._current_job_id = None
            self.all_completed.emit()
            return

        job_id = self._queue.pop(0)
        record = self._jobs.get(job_id)
        task = self._tasks.get(job_id)
        if record is None or task is None:
            self._run_next()
            return

        self._current_job_id = job_id
        record.status = JobStatus.RUNNING
        self.job_started.emit(job_id, record.name)

        self._thread = QThread(self)
        self._worker = JobWorker(task.fn, *task.args, **task.kwargs)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.progress_changed.connect(self._on_progress)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error_occurred.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_worker)

        self._thread.start()

    def _on_finished(self, result: object):
        job_id = self._current_job_id
        record = self._jobs.get(job_id) if job_id else None
        if record:
            record.status = JobStatus.COMPLETED
            record.progress = 1.0
            record.completed = datetime.now().strftime("%H:%M:%S")
            record.result = result
            self.job_completed.emit(job_id, record.name)
            self._logger.info("TaskCenter", f"Job completed: {record.name} [{job_id}]")
        self._current_job_id = None
        self._run_next()

    def _on_error(self, error_msg: str):
        job_id = self._current_job_id
        record = self._jobs.get(job_id) if job_id else None
        if record:
            record.status = JobStatus.FAILED
            record.completed = datetime.now().strftime("%H:%M:%S")
            record.error = error_msg
            self.job_failed.emit(job_id, record.name, error_msg)
            self._logger.error("TaskCenter", f"Job failed: {record.name} [{job_id}]: {error_msg}")
        self._current_job_id = None
        self._run_next()

    def _on_progress(self, progress: float, message: str):
        job_id = self._current_job_id
        record = self._jobs.get(job_id) if job_id else None
        if record:
            record.progress = progress
            record.message = message
            self.job_progress.emit(job_id, record.name, progress, message)

    def _cleanup_worker(self):
        if self._worker:
            self._worker.deleteLater()
            self._worker = None
        if self._thread:
            self._thread.deleteLater()
            self._thread = None

    def cancel_job(self, job_id: str) -> bool:
        record = self._jobs.get(job_id)
        if record is None:
            return False
        if record.status == JobStatus.RUNNING and self._worker:
            self._worker.cancel()
            if self._thread:
                self._thread.quit()
                self._thread.wait()
            record.status = JobStatus.CANCELLED
            record.completed = datetime.now().strftime("%H:%M:%S")
            self.job_cancelled.emit(job_id, record.name)
            self._current_job_id = None
            self._run_next()
            return True
        if record.status == JobStatus.QUEUED:
            if job_id in self._queue:
                self._queue.remove(job_id)
            record.status = JobStatus.CANCELLED
            record.completed = datetime.now().strftime("%H:%M:%S")
            self.job_cancelled.emit(job_id, record.name)
            return True
        return False

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        return self._jobs.get(job_id)

    def get_completed_jobs(self) -> list[JobRecord]:
        return [j for j in self._jobs.values() if j.status == JobStatus.COMPLETED]

    def get_failed_jobs(self) -> list[JobRecord]:
        return [j for j in self._jobs.values() if j.status == JobStatus.FAILED]

    def get_active_jobs(self) -> list[JobRecord]:
        return [j for j in self._jobs.values() if j.status in (JobStatus.QUEUED, JobStatus.RUNNING)]

    def retry_job(self, job_id: str, fn: Callable, *args, **kwargs) -> Optional[str]:
        record = self._jobs.get(job_id)
        if record is None:
            return None
        if record.status not in (JobStatus.FAILED, JobStatus.CANCELLED):
            return None
        return self.submit(record.name, fn, *args, **kwargs)

    def clear_history(self):
        active = {j.id for j in self.get_active_jobs()}
        self._jobs = {jid: rec for jid, rec in self._jobs.items() if jid in active}

    def trim_history(self, max_count: int = 50):
        all_jobs = sorted(
            self._jobs.values(),
            key=lambda j: j.created,
            reverse=True,
        )
        to_keep = set()
        for j in all_jobs[:max_count]:
            to_keep.add(j.id)
        self._jobs = {jid: rec for jid, rec in self._jobs.items() if jid in to_keep}


_task_center_instance = None


def get_task_center() -> TaskCenter:
    global _task_center_instance
    if _task_center_instance is None:
        _task_center_instance = TaskCenter()
    return _task_center_instance
