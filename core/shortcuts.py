from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QWidget


class KeyboardShortcuts:

    def __init__(self, main_window):
        self.main_window = main_window
        self._bind_shortcuts()

    def _bind_shortcuts(self):
        self._add("Ctrl+N", self._new_project)
        self._add("Ctrl+K", self._open_search)
        self._add("Ctrl+1", lambda: self._goto("Dashboard"))
        self._add("Ctrl+2", lambda: self._goto("Projects"))
        self._add("Ctrl+3", lambda: self._goto("Asset Manager"))
        self._add("Ctrl+4", lambda: self._goto("Settings"))

    def _add(self, shortcut, callback):
        action = QAction(self.main_window)
        action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(callback)
        self.main_window.addAction(action)

    def _goto(self, page_name):
        if hasattr(self.main_window, 'navigate_to'):
            self.main_window.navigate_to(page_name)

    def _new_project(self):
        from ui.dialogs import NewProjectDialog

        def on_created(name):
            from core.workflow import get_resume_page_class
            from core.project_manager import ProjectManager
            pm = ProjectManager()
            data = pm.load_project(name)
            if data:
                _pc, stage = get_resume_page_class(data.get("workflow_state", {}))
                self.main_window.set_project_context(name)
                self.main_window.navigate_to(stage, name)

        dlg = NewProjectDialog(self.main_window, on_project_created=on_created)
        dlg.exec()

    def _open_search(self):
        from ui.global_search import GlobalSearchDialog

        def on_select(data):
            if data.get("name"):
                from core.workflow import get_resume_page_class
                from core.project_manager import ProjectManager
                pm = ProjectManager()
                project_data = pm.load_project(data["name"])
                if project_data:
                    _pc, stage = get_resume_page_class(project_data.get("workflow_state", {}))
                    self.main_window.set_project_context(data["name"])
                    self.main_window.navigate_to(stage, data["name"])

        GlobalSearchDialog(self.main_window, on_select=on_select).exec()
