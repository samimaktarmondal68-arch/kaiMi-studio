from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.project_manager import ProjectManager
from core.notifications import NotificationService
from core.theme import Fonts, Theme
from ui.theme_pyside import ThemeManager
from ui.widgets import (
    EmptyState,
    ModernButton,
    ModernCard,
    MutedLabel,
    PageTitle,
    SearchInput,
    StatusBadge,
)
from ui.dialogs import NewProjectDialog
from ui.pages.version_history import VersionHistoryDialog

STAGE_LABELS = ["Script", "Voice", "Image Prompts", "Export"]
SORT_OPTIONS = ["Last Modified", "Name", "Status", "Created"]
FILTER_OPTIONS = ["All", "Script", "Voice", "Image Prompts", "Export"]
SORT_KEY_MAP = {
    "Last Modified": "last_modified",
    "Name": "name",
    "Status": "status",
    "Created": "created",
}


def _format_size(bytes_val: int) -> str:
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    else:
        return f"{bytes_val / (1024 * 1024):.1f} MB"


class _ProjectCard(ModernCard):
    def __init__(self, project, navigate_callback):
        super().__init__()
        self._project = project
        self._navigate_callback = navigate_callback
        self.setFixedHeight(200)
        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._build()

    def _build(self):
        name = self._project.get("name", "Untitled")
        topic = self._project.get("topic", "No topic")
        language = self._project.get("language", "English")
        platform = self._project.get("platform", "")
        template = self._project.get("template", "Custom")
        workflow = self._project.get("workflow_state", {})
        last_modified = self._project.get("last_modified", "")
        asset_count = self._project.get("asset_count", 0)
        storage_used = self._project.get("storage_used", 0)

        c = ThemeManager.instance().colors()

        completed_count = sum(1 for s in STAGE_LABELS if workflow.get(s) == "COMPLETED")
        pct = int(completed_count / len(STAGE_LABELS) * 100)

        active_stage = next(
            (s for s in STAGE_LABELS if workflow.get(s) not in ("COMPLETED",)),
            STAGE_LABELS[-1],
        )
        badge_color = Theme.get_stage_color(c, active_stage)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        thumbnail = QFrame()
        gradient = f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c.PRIMARY_LIGHT}, stop:1 {c.SURFACE})"
        thumbnail.setStyleSheet(
            f"background: {gradient}; "
            f"border-top-left-radius: 16px; border-bottom-left-radius: 16px; "
            f"min-width: 160px; max-width: 160px;"
        )
        thumb_layout = QVBoxLayout(thumbnail)
        thumb_layout.setAlignment(Qt.AlignCenter)

        pct_label = QLabel(f"{pct}%")
        pct_label.setStyleSheet(f"{Fonts.css(32, 'bold', c.PRIMARY)} background: transparent;")
        thumb_layout.addWidget(pct_label)

        pct_sub = QLabel("complete")
        pct_sub.setStyleSheet(f"{Fonts.tiny(c.TEXT_MUTED)} background: transparent;")
        thumb_layout.addWidget(pct_sub)

        layout.addWidget(thumbnail)

        content = QVBoxLayout()
        content.setContentsMargins(24, 20, 24, 20)
        content.setSpacing(4)

        name_label = QLabel(name)
        name_label.setStyleSheet(f"{Fonts.card_title(c.TEXT)}")
        content.addWidget(name_label)

        meta = QLabel(f"{topic}  \u00B7  {language}" + (f"  \u00B7  {platform}" if platform else ""))
        meta.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        content.addWidget(meta)

        content.addSpacing(2)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)
        for label_text, value in [("Template", template), ("Assets", str(asset_count)), ("Storage", _format_size(storage_used))]:
            col = QVBoxLayout()
            col.setSpacing(0)
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"{Fonts.tiny(c.TEXT_MUTED)} background: transparent;")
            col.addWidget(lbl)
            val = QLabel(value)
            val.setStyleSheet(f"{Fonts.caption_bold(c.TEXT)} background: transparent;")
            col.addWidget(val)
            stats_row.addLayout(col)
        content.addLayout(stats_row)

        content.addSpacing(4)

        progress_bar = QFrame()
        bar_layout = QHBoxLayout(progress_bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(0)

        bar_bg = QFrame()
        bar_bg.setStyleSheet(f"background-color: {c.SURFACE}; border-radius: 4px; min-height: 6px; max-height: 6px;")
        bar_fill = QFrame()
        bar_fill.setStyleSheet(
            f"background-color: {c.PRIMARY}; border-radius: 4px; "
            f"min-height: 6px; max-height: 6px; min-width: {max(pct, 4)}%; max-width: {pct}%;"
        )

        bar_fill_layout = QHBoxLayout(bar_bg)
        bar_fill_layout.setContentsMargins(0, 0, 0, 0)
        bar_fill_layout.addWidget(bar_fill)
        bar_fill_layout.addStretch()

        bar_layout.addWidget(bar_bg)
        content.addWidget(progress_bar)

        step_labels = QHBoxLayout()
        step_labels.setSpacing(8)
        for stage in STAGE_LABELS:
            state = workflow.get(stage, "LOCKED")
            if state == "COMPLETED":
                text = f"\u2713 {stage}"
                sc = c.SUCCESS
            elif state == "AVAILABLE":
                text = f"\u25CF {stage}"
                sc = Theme.get_stage_color(c, stage)
            else:
                text = f"\u25CB {stage}"
                sc = c.TEXT_MUTED
            lbl = QLabel(text)
            lbl.setStyleSheet(f"{Fonts.tiny(sc)} background: transparent;")
            step_labels.addWidget(lbl)
        step_labels.addStretch()
        content.addLayout(step_labels)

        if last_modified:
            mod = QLabel(f"Last modified: {last_modified}")
            mod.setStyleSheet(f"{Fonts.tiny(c.TEXT_MUTED)} background: transparent;")
            content.addWidget(mod)

        layout.addLayout(content, 1)

        actions = QVBoxLayout()
        actions.setContentsMargins(16, 16, 16, 16)
        actions.setSpacing(8)
        actions.setAlignment(Qt.AlignTop | Qt.AlignRight)

        badge = StatusBadge(active_stage, color=c.TEXT_ON_PRIMARY, bg=badge_color)
        actions.addWidget(badge)

        open_btn = ModernButton("Resume", primary=True)
        open_btn.setFixedSize(90, 34)
        open_btn.clicked.connect(lambda checked, n=name: self._navigate_callback(n))
        actions.addWidget(open_btn)

        history_btn = ModernButton("History", primary=False)
        history_btn.setFixedSize(90, 34)
        history_btn.clicked.connect(lambda checked, n=name: self._show_history(n))
        actions.addWidget(history_btn)

        actions.addStretch()
        layout.addLayout(actions)

        self.content_layout.addLayout(layout)

    def _show_history(self, project_name):
        dlg = VersionHistoryDialog(project_name)
        dlg.exec()


class ProjectsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.manager = ProjectManager()
        self._search_query = ""
        self._sort_by = "last_modified"
        self._sort_reverse = True
        self._filter_status = "All"
        ThemeManager.instance().on_change(lambda _: self._on_theme_changed())
        self._build()

    def _on_theme_changed(self):
        self.refresh()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        header = QHBoxLayout()
        header.setSpacing(16)

        title = PageTitle("Projects")
        header.addWidget(title)
        header.addStretch()

        new_btn = ModernButton("+ New Project", primary=True)
        new_btn.setFixedSize(160, 40)
        new_btn.clicked.connect(self._create_new)
        header.addWidget(new_btn)

        layout.addLayout(header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        self.search_input = SearchInput(placeholder="Search projects...")
        self.search_input.setFixedWidth(280)
        self.search_input.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self.search_input)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(SORT_OPTIONS)
        self.sort_combo.setMinimumWidth(160)
        self.sort_combo.currentTextChanged.connect(self._on_sort_changed)
        toolbar.addWidget(self.sort_combo)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(FILTER_OPTIONS)
        self.filter_combo.setMinimumWidth(150)
        self.filter_combo.currentTextChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.filter_combo)

        toolbar.addStretch()

        self.count_label = MutedLabel("")
        toolbar.addWidget(self.count_label)

        layout.addLayout(toolbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(16)
        self.cards_layout.addStretch()

        scroll.setWidget(self.cards_container)
        layout.addWidget(scroll, 1)

        self.refresh()

    def _build_cards(self, projects):
        for i in reversed(range(self.cards_layout.count())):
            item = self.cards_layout.itemAt(i)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        if not projects:
            empty = EmptyState(
                icon="\U0001F4C1",
                title="No Projects Found",
                description="Create a new project to get started.",
                action_callback=self._create_new,
                action_text="Create New Project",
            )
            self.cards_layout.addWidget(empty, 1)
            return

        for project in projects:
            name = project.get("name", "")
            card = _ProjectCard(project, lambda n=name: self._navigate("", n))
            self.cards_layout.addWidget(card)

        self.cards_layout.addStretch()

    def _navigate(self, page_label, project_name=None):
        parent = self.parent()
        while parent and not hasattr(parent, "navigate_to"):
            parent = parent.parent()
        if parent:
            from core.workflow import get_resume_page_class
            data = self.manager.load_project(project_name)
            if data:
                _page_class, stage_label = get_resume_page_class(data.get("workflow_state", {}))
                parent.set_project_context(project_name)
                parent.navigate_to(stage_label, project_name)

    def _create_new(self):
        parent = self.window()
        dlg = NewProjectDialog(parent, on_project_created=self._on_project_created)
        dlg.exec()

    def _on_project_created(self, name):
        self.refresh()
        from core.notifications import NotificationService
        NotificationService.get().success(f"Project '{name}' created.")
        parent = self.window()
        if parent and hasattr(parent, 'navigate_to'):
            from core.workflow import get_resume_page_class
            data = self.manager.load_project(name)
            if data:
                _page_class, stage_label = get_resume_page_class(data.get("workflow_state", {}))
                parent.set_project_context(name)
                parent.navigate_to(stage_label, name)

    def refresh(self):
        projects = self.manager.search_projects(self._search_query)
        projects = self.manager.filter_projects(projects, self._filter_status)
        projects = self.manager.sort_projects(projects, self._sort_by, self._sort_reverse)

        favorites = [p for p in projects if p.get("favorite")]
        regular = [p for p in projects if not p.get("favorite")]
        display = favorites + regular

        count = len(display)
        label = f"{count} project{'s' if count != 1 else ''}"
        self.count_label.setText(label)

        self._build_cards(display)

    def set_project(self, name=None):
        self.refresh()

    def _on_search_changed(self, text):
        self._search_query = text.strip()
        self.refresh()

    def _on_sort_changed(self, value):
        self._sort_by = SORT_KEY_MAP.get(value, "last_modified")
        self.refresh()

    def _on_filter_changed(self, value):
        self._filter_status = value
        self.refresh()
