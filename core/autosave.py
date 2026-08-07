"""Autosave manager with debounced saving and status tracking."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Callable, Optional

from PySide6.QtCore import QTimer


class AutosaveManager:

    def __init__(self, debounce_ms: int = 7000) -> None:
        self._debounce_ms = debounce_ms
        self._timers: dict[str, QTimer] = {}
        self._callbacks: dict[str, Callable[[], None]] = {}
        self._status_callbacks: list[Callable[[str], None]] = []
        self._dirty_keys: set[str] = set()

    def register(self, key: str, save_fn: Callable[[], None]) -> None:
        self._callbacks[key] = save_fn
        if key not in self._timers:
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(lambda k=key: self._flush(k))
            self._timers[key] = timer

    def mark_dirty(self, key: str) -> None:
        self._dirty_keys.add(key)
        self._notify_status("Saving...")
        timer = self._timers.get(key)
        if timer:
            timer.stop()
            timer.start(self._debounce_ms)

    def _flush(self, key: str) -> None:
        fn = self._callbacks.get(key)
        if fn:
            try:
                fn()
                self._dirty_keys.discard(key)
                if not self._dirty_keys:
                    self._notify_status("All Changes Saved")
                else:
                    self._notify_status("Saved")
            except Exception:
                self._notify_status("Save Failed")

    def flush_all(self) -> None:
        for key in list(self._dirty_keys):
            self._flush(key)

    def on_status_change(self, cb: Callable[[str], None]) -> None:
        self._status_callbacks.append(cb)

    def _notify_status(self, status: str) -> None:
        for cb in self._status_callbacks:
            try:
                cb(status)
            except Exception:
                # Status callbacks target UI indicators that may already have
                # been destroyed; a stale indicator must not break the save.
                pass

    def is_dirty(self) -> bool:
        return len(self._dirty_keys) > 0

    def shutdown(self) -> None:
        for timer in self._timers.values():
            timer.stop()
            timer.deleteLater()
        self._timers.clear()
        self._callbacks.clear()
        self._status_callbacks.clear()
        self._dirty_keys.clear()


_autosave_instance: Optional[AutosaveManager] = None


def get_autosave_manager() -> AutosaveManager:
    global _autosave_instance
    if _autosave_instance is None:
        _autosave_instance = AutosaveManager()
    return _autosave_instance