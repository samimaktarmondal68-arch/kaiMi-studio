"""File system watcher that detects external changes to project files."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QFileSystemWatcher, QTimer


class ProjectFileWatcher:

    def __init__(self) -> None:
        self._watcher = QFileSystemWatcher()
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(500)
        self._on_change_callbacks: list[Callable[[str], None]] = []
        self._watch_dirs: dict[str, str] = {}
        self._pending: set[str] = set()

        self._watcher.directoryChanged.connect(self._on_dir_changed)
        self._watcher.fileChanged.connect(self._on_file_changed)
        self._debounce_timer.timeout.connect(self._fire_changes)

    def watch_project(self, project_name: str, project_path: Path) -> None:
        self._watch_dirs[str(project_path)] = project_name
        dirs_to_watch = [str(project_path)]
        for sub in ["audio", "exports", "history"]:
            sub_path = project_path / sub
            if sub_path.exists():
                dirs_to_watch.append(str(sub_path))
        self._watcher.addPaths(dirs_to_watch)
        json_files = list(project_path.glob("*.json"))
        self._watcher.addPaths([str(f) for f in json_files if f.exists()])

    def unwatch_project(self, project_path: Path) -> None:
        self._watcher.removePaths(self._watcher.directories())
        self._watcher.removePaths(self._watcher.files())
        self._watch_dirs.pop(str(project_path), None)

    def on_change(self, cb: Callable[[str], None]) -> None:
        self._on_change_callbacks.append(cb)

    def _on_dir_changed(self, path: str) -> None:
        for watch_path, proj_name in self._watch_dirs.items():
            if path.startswith(watch_path):
                self._pending.add(proj_name)
                self._debounce_timer.start()
                break

    def _on_file_changed(self, path: str) -> None:
        for watch_path, proj_name in self._watch_dirs.items():
            if path.startswith(watch_path):
                self._pending.add(proj_name)
                self._debounce_timer.start()
                break

    def _fire_changes(self) -> None:
        for proj_name in list(self._pending):
            for cb in self._on_change_callbacks:
                cb(proj_name)
        self._pending.clear()