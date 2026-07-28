from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QVBoxLayout, QWidget,
)

from core.image_prompt_storage import ImagePromptStorage
from core.project_manager import ProjectManager
from core.research_storage import ResearchStorage
from core.script_storage import ScriptStorage
from core.storyboard_storage import StoryboardStorage
from core.theme import Fonts
from ui.theme_pyside import ThemeManager


class GlobalSearchDialog(QDialog):

    def __init__(self, parent=None, on_select=None):
        super().__init__(parent)
        self.setWindowTitle("Search")
        self.setMinimumSize(640, 480)
        self.setModal(True)
        self.on_select = on_select
        self.pm = ProjectManager()
        self._results = []

        c = ThemeManager.instance().colors()
        self.setStyleSheet(f"background-color: {c.BG}; color: {c.TEXT};")
        self._build()
        QTimer.singleShot(50, self.search_entry.setFocus)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        c = ThemeManager.instance().colors()

        search_frame = QFrame()
        search_frame.setObjectName("card")
        search_frame.setAttribute(Qt.WA_StyledBackground, True)
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(16, 12, 16, 12)

        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Search projects, research, scripts...")
        self.search_entry.setMinimumHeight(40)
        self.search_entry.setStyleSheet(f"{Fonts.body(c.TEXT)} border: none;")
        self.search_entry.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_entry)

        shortcut_lbl = QLabel("ESC")
        shortcut_lbl.setStyleSheet(
            f"{Fonts.tiny(c.TEXT_MUTED)} "
            f"background-color: {c.HOVER}; border-radius: 4px; padding: 2px 8px;"
        )
        search_layout.addWidget(shortcut_lbl)

        layout.addWidget(search_frame)

        self.results_list = QListWidget()
        self.results_list.setFrameShape(QFrame.NoFrame)
        self.results_list.setAttribute(Qt.WA_StyledBackground, True)
        self.results_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.results_list, 1)

        self._show_recent_projects()

    def _show_recent_projects(self):
        self.results_list.clear()
        self._results = []

        projects = self.pm.get_recent_projects(8)
        if not projects:
            self._add_empty("No projects found.")
            return

        self._add_header("Recent Projects")
        for p in projects:
            self._add_result(p.get("name", ""), "Project", p)

    def _on_search(self, query):
        self.results_list.clear()
        self._results = []

        if not query.strip():
            self._show_recent_projects()
            return

        projects = self.pm.search_projects(query)
        for p in projects[:5]:
            self._add_result(p.get("name", ""), "Project", p)

        for stage_name, storage_cls in [
            ("Research", ResearchStorage),
            ("Script", ScriptStorage),
            ("Storyboard", StoryboardStorage),
            ("Image Prompts", ImagePromptStorage),
        ]:
            storage = storage_cls()
            for p in self.pm.get_projects()[:10]:
                pname = p.get("name", "")
                data = storage.load(pname)
                self._search_stage_data(data, stage_name, pname, query)

        if not self._results:
            self._add_empty(f'No results for "{query}"')

    def _search_stage_data(self, data, stage, project_name, query):
        searchable_parts = []
        for v in data.values():
            if isinstance(v, str):
                searchable_parts.append(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        searchable_parts.extend(str(val) for val in item.values() if isinstance(val, str))
        full_text = " ".join(searchable_parts).lower()
        if query.lower() in full_text:
            self._add_result(f"{project_name} \u2014 {stage}", stage, {
                "name": project_name, "stage": stage,
            })

    def _add_header(self, text):
        item = QListWidgetItem(text)
        c = ThemeManager.instance().colors()
        item.setForeground(QColor(c.TEXT_MUTED))
        item.setFlags(Qt.NoItemFlags)
        font = item.font()
        font.setBold(True)
        font.setPointSize(10)
        item.setFont(font)
        self.results_list.addItem(item)

    def _add_result(self, title, category, data):
        c = ThemeManager.instance().colors()
        item = QListWidgetItem(f"\U0001F4C1  {title}  \u2014  {category}")
        item.setForeground(QColor(c.TEXT))
        item.setData(Qt.UserRole, data)
        self.results_list.addItem(item)
        self._results.append((item, data))

    def _add_empty(self, text):
        item = QListWidgetItem(text)
        c = ThemeManager.instance().colors()
        item.setForeground(QColor(c.TEXT_MUTED))
        item.setFlags(Qt.NoItemFlags)
        self.results_list.addItem(item)

    def _on_item_clicked(self, item):
        data = item.data(Qt.UserRole)
        if data and self.on_select:
            self.on_select(data)
        self.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            current = self.results_list.currentItem()
            if current:
                self._on_item_clicked(current)
        else:
            super().keyPressEvent(event)
