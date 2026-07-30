from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QWidget


class KeyboardShortcuts:

    def __init__(self, main_window):
        self.main_window = main_window
        self._actions = []
        self._bind_shortcuts()

    def _bind_shortcuts(self):
        self._add("Ctrl+N", self._new_project)
        self._add("Ctrl+K", self._open_search)
        self._add("Ctrl+1", lambda: self._goto("Dashboard"))
        self._add("Ctrl+2", lambda: self._goto("Projects"))
        self._add("Ctrl+3", lambda: self._goto("Asset Manager"))
        self._add("Ctrl+4", lambda: self._goto("Settings"))
        self._add("Ctrl+5", lambda: self._goto_workflow_stage("Script"))
        self._add("Ctrl+6", lambda: self._goto_workflow_stage("Voice"))
        self._add("Ctrl+7", lambda: self._goto_workflow_stage("Image Prompts"))
        self._add("Ctrl+8", lambda: self._goto_workflow_stage("Export"))
        self._add("F5", self._refresh_current)
        self._add("Ctrl+S", self._save_current)

    def _add(self, shortcut, callback):
        action = QAction(self.main_window)
        action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(callback)
        self.main_window.addAction(action)
        self._actions.append(action)

    def _goto(self, page_name):
        if hasattr(self.main_window, 'navigate_to'):
            self.main_window.navigate_to(page_name)

    def _goto_workflow_stage(self, stage):
        nav = getattr(self.main_window, 'nav', None)
        project = nav.current_project if nav else None
        if project:
            self.main_window.navigate_to(stage, project)
        else:
            self.main_window.navigate_to(stage)

    def _refresh_current(self):
        current = self.main_window.content.currentWidget()
        if hasattr(current, 'refresh'):
            current.refresh()
        elif hasattr(current, 'set_project'):
            nav = getattr(self.main_window, 'nav', None)
            project = nav.current_project if nav else None
            current.set_project(project)

    def _save_current(self):
        current = self.main_window.content.currentWidget()
        if hasattr(current, 'save_script'):
            current.save_script()
        elif hasattr(current, 'save_transcript'):
            current.save_transcript()

    def _new_project(self):
        from ui.dialogs import NewProjectDialog

        def on_created(name):
            self.main_window.set_project_context(name)
            self.main_window.navigate_to("Script", name)

        dlg = NewProjectDialog(self.main_window, on_project_created=on_created)
        dlg.exec()

    def _open_search(self):
        from ui.global_search import GlobalSearchDialog

        def on_select(data):
            if data.get("name"):
                nav = getattr(self.main_window, 'nav', None)
                project = nav.current_project if nav else None
                self.main_window.set_project_context(data["name"])
                self.main_window.navigate_to("Script", data["name"])

        GlobalSearchDialog(self.main_window, on_select=on_select).exec()
