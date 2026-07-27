# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Application settings with persistent storage.

Handles app-level settings (theme, window size, recent projects, preferences).
Provider configuration remains in providers.json via ProviderManager.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


_SETTINGS_DIR = Path(__file__).resolve().parent.parent / "config"
_SETTINGS_FILE = _SETTINGS_DIR / "settings.json"

_DEFAULTS: dict = {
    "theme": "dark",
    "window_width": 1600,
    "window_height": 1000,
    "window_maximized": False,
    "recent_projects": [],
    "max_recent": 10,
    "autosave_enabled": True,
    "autosave_interval": 30,
    "first_run": True,
}


class AppSettings:
    _instance: Optional["AppSettings"] = None

    def __new__(cls) -> "AppSettings":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_loaded", False):
            return
        _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        self._data: dict = dict(_DEFAULTS)
        self._load()
        self._loaded = True

    def _load(self) -> None:
        if _SETTINGS_FILE.exists():
            try:
                with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                    stored = json.load(f)
                self._data.update(stored)
            except (json.JSONDecodeError, OSError):
                pass

    def save(self) -> None:
        try:
            with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=4)
        except OSError:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    def get_theme(self) -> str:
        return self._data.get("theme", "dark")

    def set_theme(self, theme: str) -> None:
        self.set("theme", theme)

    def get_window_geometry(self) -> tuple[int, int]:
        return (
            self._data.get("window_width", 1600),
            self._data.get("window_height", 1000),
        )

    def set_window_geometry(self, width: int, height: int) -> None:
        self._data["window_width"] = width
        self._data["window_height"] = height
        self.save()

    def add_recent_project(self, name: str) -> None:
        recent = self._data.get("recent_projects", [])
        if name in recent:
            recent.remove(name)
        recent.insert(0, name)
        max_recent = self._data.get("max_recent", 10)
        self._data["recent_projects"] = recent[:max_recent]
        self.save()

    def get_recent_projects(self) -> list[str]:
        return self._data.get("recent_projects", [])

    def is_first_run(self) -> bool:
        return self._data.get("first_run", True)

    def mark_not_first_run(self) -> None:
        self.set("first_run", False)
