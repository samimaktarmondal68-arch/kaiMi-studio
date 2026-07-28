"""Centralized navigation controller for KaiMi Studio.

All page switching goes through this controller.
No page should switch pages directly.
"""

from PySide6.QtCore import QObject, Signal


class NavigationController(QObject):
    """Single source of truth for navigation state and page switching.

    Flow: Sidebar -> NavigationController -> MainWindow -> QStackedWidget
    """

    page_changed = Signal(str)
    project_opened = Signal(str)

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main_window = main_window
        self._page_map = {}
        self._current_page_label = None
        self._current_project = None
        self._initialized = False

    def initialize(self, page_map):
        """Set the page map and mark controller as ready."""
        self._page_map = page_map
        self._initialized = True

    def navigate_to(self, label, project_name=None):
        """Navigate to a page by label. All navigation must go through here.

        Args:
            label: The page label (e.g., "Dashboard", "Projects", "Script").
            project_name: Optional project name to set as context.
        """
        if not self._initialized:
            return

        label = self._normalize_label(label)
        if label is None:
            return

        page_class = self._page_map.get(label)
        if page_class is None:
            return

        target_widget = self._find_page_widget(page_class)
        if target_widget is None:
            return

        if hasattr(target_widget, 'set_project'):
            target_widget.set_project(project_name)

        self._main_window.content.setCurrentWidget(target_widget)
        self._main_window.sidebar.set_active(label)
        self._current_page_label = label
        self._current_project = project_name or self._current_project

        if project_name:
            self._handle_project_context(project_name)

        self.page_changed.emit(label)

    def _normalize_label(self, label):
        """Normalize label aliases."""
        if label == "Exports":
            return "Export"
        if label in self._page_map:
            return label
        return None

    def _find_page_widget(self, page_class):
        """Find the widget instance in QStackedWidget matching the page class."""
        stacked = self._main_window.content
        for i in range(stacked.count()):
            w = stacked.widget(i)
            if isinstance(w, page_class):
                return w
        return None

    def _handle_project_context(self, project_name):
        """Handle project context update: file watcher, sidebar, marking opened."""
        self._main_window._project_name = project_name
        self._main_window._update_sidebar_project(project_name)

        from core.project_manager import ProjectManager
        pm = ProjectManager()
        pm.mark_opened(project_name)
        proj_path = pm.PROJECTS_DIR / project_name
        self._main_window._file_watcher.unwatch_project(proj_path)
        self._main_window._file_watcher.watch_project(project_name, proj_path)

        self.project_opened.emit(project_name)

    @property
    def current_page(self):
        return self._current_page_label

    @property
    def current_project(self):
        return self._current_project

    def get_project_context(self):
        return self._current_project

    def set_project_context(self, name):
        self._current_project = name
        if name:
            self._handle_project_context(name)
