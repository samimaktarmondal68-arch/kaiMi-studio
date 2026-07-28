from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from .sidebar import Sidebar
from .theme_pyside import ThemeManager
from .navigation import NavigationController
from core.autosave import get_autosave_manager
from core.file_watcher import ProjectFileWatcher
from core.notifications import NotificationService
from core.project_manager import ProjectManager
from core.shortcuts import KeyboardShortcuts


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("KaiMi Studio")
        self.setMinimumSize(1200, 700)
        self._current_page = None
        self._project_name = None
        self._file_watcher = ProjectFileWatcher()
        self._file_watcher.on_change(self._on_external_change)
        self._init_theme()
        self._init_ui()
        self._restore_geometry()

    def _init_theme(self):
        self.theme = ThemeManager.instance()
        self.theme.set_mode("dark")
        self.theme.on_change(lambda mode: self._on_theme_changed())

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self.sidebar = Sidebar()
        self._page_map = self._build_page_map()
        self.sidebar.set_page_map(self._page_map)
        layout.addWidget(self.sidebar)

        content_container = QWidget()
        content_container.setObjectName("content")
        content_container.setStyleSheet("background-color: transparent;")
        content_layout = QHBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self.content = QStackedWidget()
        self.content.setObjectName("content")
        content_layout.addWidget(self.content)

        layout.addWidget(content_container, 1)

        NotificationService.get().set_parent(self)
        self.shortcuts = KeyboardShortcuts(self)

        self.nav = NavigationController(self)
        self.nav.initialize(self._page_map)
        self.sidebar.set_nav_controller(self.nav)

        self._build_pages()
        self.navigate_to("Dashboard")

    def _build_page_map(self):
        from ui.pages.dashboard import DashboardPage
        from ui.pages.projects import ProjectsPage
        from ui.pages.script_page import ScriptPage
        from ui.pages.voice_page import VoicePage
        from ui.pages.image_prompts_page import ImagePromptsPage
        from ui.pages.export_page import ExportPage
        from ui.pages.settings_page import SettingsPage
        from ui.pages.asset_manager import AssetManagerPage

        return {
            "Dashboard": DashboardPage,
            "Projects": ProjectsPage,
            "Asset Manager": AssetManagerPage,
            "Script": ScriptPage,
            "Voice": VoicePage,
            "Image Prompts": ImagePromptsPage,
            "Export": ExportPage,
            "Exports": ExportPage,
            "Settings": SettingsPage,
        }

    def _build_pages(self):
        seen = {}
        for label, page_class in self._page_map.items():
            if page_class not in seen:
                page = page_class()
                self.content.addWidget(page)
                seen[page_class] = page

    def navigate_to(self, label, project_name=None):
        self.nav.navigate_to(label, project_name)

    def _update_sidebar_project(self, project_name):
        from core.project_manager import ProjectManager
        pm = ProjectManager()
        data = pm.load_project(project_name)
        workflow = data.get("workflow_state", {}) if data else {}
        self.sidebar.set_project_context(project_name, workflow)

    def _on_external_change(self, project_name: str):
        """Called when external file changes are detected."""
        from core.project_manager import ProjectManager
        pm = ProjectManager()
        data = pm.load_project(project_name)
        if data:
            self._update_sidebar_project(project_name)
            current = self.content.currentWidget()
            if hasattr(current, '_refresh_assets'):
                current._refresh_assets()
            if hasattr(current, '_load_project_data'):
                current._load_project_data()

    def _restore_geometry(self):
        self.resize(1500, 960)

    def _on_theme_changed(self):
        self.sidebar.update_theme()

    def get_project_context(self):
        return self._project_name

    def set_project_context(self, name):
        self._project_name = name
        if name:
            self._update_sidebar_project(name)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        from core.notifications import NotificationService
        ns = NotificationService.get()
        if ns._container and ns._parent:
            pw = self.width()
            ph = self.height()
            from core.notifications import NOTIFICATION_WIDTH, NOTIFICATION_MARGIN
            cw = NOTIFICATION_WIDTH
            x = pw - cw - NOTIFICATION_MARGIN
            y = ph - NOTIFICATION_MARGIN - 80
            ns._container.setGeometry(x, y, cw, ph - y - NOTIFICATION_MARGIN)
