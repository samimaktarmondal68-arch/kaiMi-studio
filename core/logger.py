"""Production logging system for KaiMi Studio.

Provides structured logging with separate files for:
    - application.log  (all INFO+ events)
    - errors.log       (ERROR+ only, with full tracebacks)
    - startup.log      (startup/shutdown lifecycle)

Usage:
    from core.logger import get_logger
    log = get_logger()
    log.info("App", "Application started")
    log.error("Export", "Failed to export", exc=e)
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional


class AppLogger:
    _instance: Optional["AppLogger"] = None

    def __new__(cls) -> "AppLogger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self.base_dir = Path(__file__).resolve().parent.parent
        self.logs_dir = self.base_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        self._app_log_path = self.logs_dir / "application.log"
        self._error_log_path = self.logs_dir / "errors.log"
        self._startup_log_path = self.logs_dir / "startup.log"

        self.logger = logging.getLogger("kaimi_studio")
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False

        if not self.logger.handlers:
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

            # Application log — all INFO+ (1 MB rotation, keep 10 backups)
            app_handler = logging.handlers.RotatingFileHandler(
                self._app_log_path,
                maxBytes=1_048_576,
                backupCount=10,
                encoding="utf-8",
            )
            app_handler.setLevel(logging.INFO)
            app_handler.setFormatter(formatter)

            # Error log — ERROR+ only with full tracebacks
            error_handler = logging.handlers.RotatingFileHandler(
                self._error_log_path,
                maxBytes=1_048_576,
                backupCount=10,
                encoding="utf-8",
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(formatter)

            # Startup log — append-only lifecycle events
            startup_handler = logging.FileHandler(
                self._startup_log_path,
                encoding="utf-8",
            )
            startup_handler.setLevel(logging.INFO)
            startup_handler.setFormatter(formatter)

            # Console handler — WARNING+ for development visibility
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.WARNING)
            console_handler.setFormatter(formatter)

            self.logger.addHandler(app_handler)
            self.logger.addHandler(error_handler)
            self.logger.addHandler(startup_handler)
            self.logger.addHandler(console_handler)

        self._initialized = True

    def _log(self, level: int, component: str, message: str,
             exc: Optional[BaseException] = None) -> None:
        if exc is not None:
            self.logger.log(level, f"[{component}] {message}",
                            exc_info=(type(exc), exc, exc.__traceback__))
        else:
            self.logger.log(level, f"[{component}] {message}")

    def debug(self, component: str, message: str) -> None:
        self._log(logging.DEBUG, component, message)

    def info(self, component: str, message: str) -> None:
        self._log(logging.INFO, component, message)

    def warning(self, component: str, message: str) -> None:
        self._log(logging.WARNING, component, message)

    def error(self, component: str, message: str,
              exc: Optional[BaseException] = None) -> None:
        self._log(logging.ERROR, component, message, exc)

    def startup(self, message: str) -> None:
        self._log(logging.INFO, "Startup", message)

    def shutdown(self, message: str) -> None:
        self._log(logging.INFO, "Shutdown", message)


_log_instance: Optional[AppLogger] = None


def get_logger() -> AppLogger:
    global _log_instance
    if _log_instance is None:
        _log_instance = AppLogger()
    return _log_instance
