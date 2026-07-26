from __future__ import annotations

import logging
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
        self.log_path = self.logs_dir / f"{today}.log"

        self.logger = logging.getLogger("kaimi_studio")
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False

        if not self.logger.handlers:
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler = logging.FileHandler(self.log_path, encoding="utf-8")
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

        self._initialized = True

    def _log(self, level: int, component: str, message: str, exc: Optional[BaseException] = None) -> None:
        if exc is not None:
            self.logger.log(level, f"[{component}] {message} | exception={exc!r}")
        else:
            self.logger.log(level, f"[{component}] {message}")

    def info(self, component: str, message: str) -> None:
        self._log(logging.INFO, component, message)

    def warning(self, component: str, message: str) -> None:
        self._log(logging.WARNING, component, message)

    def error(self, component: str, message: str, exc: Optional[BaseException] = None) -> None:
        self._log(logging.ERROR, component, message, exc)


def get_logger() -> AppLogger:
    return AppLogger()
