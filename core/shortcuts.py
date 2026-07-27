# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Keyboard shortcuts manager for KaiMi Studio."""

from ui.global_search import GlobalSearchDialog


class KeyboardShortcuts:

    def __init__(self, root, home_window):
        self.root = root
        self.home = home_window
        self._bind_shortcuts()

    def _bind_shortcuts(self):
        self.root.bind("<Control-n>", lambda e: self._new_project())
        self.root.bind("<Control-s>", lambda e: self._save())
        self.root.bind("<Control-Shift-S>", lambda e: self._export())
        self.root.bind("<Control-k>", lambda e: self._open_search())
        self.root.bind("<Control-1>", lambda e: self._goto("Dashboard"))
        self.root.bind("<Control-2>", lambda e: self._goto("Projects"))
        self.root.bind("<Control-3>", lambda e: self._goto("Workflow"))
        self.root.bind("<Control-4>", lambda e: self._goto("Templates"))
        self.root.bind("<Control-5>", lambda e: self._goto("Settings"))

    def _goto(self, page_name):
        from ui.dashboard import Dashboard
        from ui.projects import ProjectsPage
        from ui.templates import TemplatesPage
        from ui.settings_page import SettingsPage
        from ui.workspace import WorkspacePage

        page_map = {
            "Dashboard": Dashboard,
            "Projects": ProjectsPage,
            "Workflow": WorkspacePage,
            "Templates": TemplatesPage,
            "Settings": SettingsPage,
        }
        cls = page_map.get(page_name)
        if cls:
            self.home.show_page(cls, page_name)

    def _new_project(self):
        from ui.dialogs import NewProjectDialog
        from ui.dashboard import Dashboard
        NewProjectDialog(self.root, on_project_created=lambda n: self.home.show_page(Dashboard, "Dashboard"))

    def _save(self):
        try:
            current = self.home.current_page
            if hasattr(current, "save_current"):
                current.save_current()
            else:
                from core.notifications import NotificationService
                NotificationService.get().info("Nothing to save.")
        except Exception:
            pass

    def _export(self):
        self._goto("Workflow")

    def _open_search(self):
        def on_select(data):
            if data.get("stage"):
                from ui.workspace import WorkspacePage
                self.home.show_page(
                    WorkspacePage, "Workflow",
                    initial_project_name=data.get("name"),
                )
            elif data.get("name"):
                from ui.workspace import WorkspacePage
                self.home.show_page(
                    WorkspacePage, "Workflow",
                    initial_project_name=data.get("name"),
                )
        GlobalSearchDialog(self.root, on_select=on_select)
