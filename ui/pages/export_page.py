from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from core.export_service import ExportService
from core.notifications import NotificationService
from core.pipeline_events import get_pipeline_events
from core.pipeline_service import get_pipeline_service, StageStatus
from core.project_manager import ProjectManager
from core.theme import Fonts, Theme
from ui.theme_pyside import ThemeManager
from ui.widgets import (
    CardTitle,
    EmptyState,
    IconProvider,
    MutedLabel,
    ModernButton,
    ModernCard,
    SectionHeader,
    StatusBadge,
)

STAGE_LABELS = ["Script", "Voice", "Image Prompts", "Export"]


class ExportPage(QWidget):
    def __init__(self):
        super().__init__()
        self.manager = ProjectManager()
        self.export_service = ExportService(self.manager)
        self._pipeline = get_pipeline_service()
        self._events = get_pipeline_events()
        self._events.stage_completed.connect(self._on_pipeline_event)
        self._events.project_updated.connect(self._on_pipeline_event)
        self._events.export_completed.connect(self._on_pipeline_event)
        self.project_name = None
        ThemeManager.instance().on_change(lambda _: self._on_theme_changed())
        self._build()

    def _on_pipeline_event(self, *args):
        if self.project_name:
            self._load_project_data()

    def _on_theme_changed(self):
        if self.project_name:
            self._load_project_data()

    def set_project(self, name):
        self.project_name = name
        self._load_project_data()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self._build_project_header(layout)

        self._build_export_card(layout)
        self._build_workflow_card(layout)
        self._build_history_card(layout)

        layout.addStretch()

    def _build_project_header(self, parent):
        card = ModernCard()
        card.content_layout.setSpacing(8)

        c = ThemeManager.instance().colors()

        row = QHBoxLayout()
        row.setSpacing(16)

        name_label = CardTitle("Export")
        row.addWidget(name_label)

        self.status_badge = StatusBadge("Export")
        row.addWidget(self.status_badge)

        row.addStretch()
        card.content_layout.addLayout(row)

        self.name_label = QLabel("No project selected.")
        self.name_label.setStyleSheet(f"{Fonts.subtitle(c.TEXT)}")
        card.content_layout.addWidget(self.name_label)

        self.info_label = QLabel("")
        self.info_label.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        card.content_layout.addWidget(self.info_label)

        parent.addWidget(card)

    def _build_export_card(self, parent):
        c = ThemeManager.instance().colors()

        card = ModernCard()
        card.content_layout.setSpacing(8)

        card.content_layout.addWidget(SectionHeader("Export Project"))

        desc = QLabel("Export your script and image prompts as a TXT file ready for production.")
        desc.setStyleSheet(f"{Fonts.caption(c.TEXT_SECONDARY)}")
        desc.setWordWrap(True)
        card.content_layout.addWidget(desc)

        self.status_label = MutedLabel("")
        card.content_layout.addWidget(self.status_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.export_btn = ModernButton("Export TXT", primary=True)
        self.export_btn.clicked.connect(self._do_export)
        self.export_btn.setEnabled(False)
        btn_row.addWidget(self.export_btn)

        btn_row.addStretch()
        card.content_layout.addLayout(btn_row)

        parent.addWidget(card)

    def _build_workflow_card(self, parent):
        card = ModernCard()
        card.content_layout.setSpacing(8)

        card.content_layout.addWidget(SectionHeader("Workflow Progress"))

        self.workflow_widget = QWidget()
        self.workflow_layout = QVBoxLayout(self.workflow_widget)
        self.workflow_layout.setContentsMargins(0, 0, 0, 0)
        self.workflow_layout.setSpacing(6)
        card.content_layout.addWidget(self.workflow_widget)

        parent.addWidget(card)

    def _build_history_card(self, parent):
        card = ModernCard()
        card.content_layout.setSpacing(8)

        card.content_layout.addWidget(SectionHeader("Export History"))

        self.history_label = MutedLabel("No exports yet.")
        card.content_layout.addWidget(self.history_label)

        parent.addWidget(card)

    def _load_project_data(self):
        if not self.project_name:
            return
        c = ThemeManager.instance().colors()

        pipeline_state = self._pipeline.get_pipeline_state(self.project_name)
        health = self._pipeline.get_project_health(self.project_name)

        all_completed = all(
            pipeline_state.get(s) == StageStatus.COMPLETED
            for s in STAGE_LABELS
        )

        self.export_btn.setEnabled(all_completed)

        project_data = self.manager.load_project(self.project_name)
        if project_data:
            topic = project_data.get("topic", "")
            platform = project_data.get("platform", "")
            language = project_data.get("language", "")
            self.name_label.setText(f"Project: {self.project_name}")
            self.info_label.setText(f"{topic}  \u2022  {platform}  \u2022  {language}")
            self.info_label.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        else:
            self.name_label.setText(f"Project: {self.project_name}")

        self._build_workflow_steps(pipeline_state)
        self._load_export_history()

    def _build_workflow_steps(self, pipeline_state):
        for i in reversed(range(self.workflow_layout.count())):
            w = self.workflow_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        c = ThemeManager.instance().colors()

        for stage_name in STAGE_LABELS:
            stage_color = Theme.get_stage_color(c, stage_name)
            status = pipeline_state.get(stage_name, StageStatus.BLOCKED)
            if status == StageStatus.COMPLETED:
                icon_name = "check_circle"
                color = c.SUCCESS
            elif status in (StageStatus.NOT_STARTED, StageStatus.IN_PROGRESS):
                icon_name = "circle"
                color = stage_color
            elif status == StageStatus.FAILED:
                icon_name = "warning"
                color = c.ERROR
            else:
                icon_name = "circle_empty"
                color = c.TEXT_MUTED

            step_row = QHBoxLayout()
            step_row.setSpacing(8)
            step_icon = IconProvider.icon_label(icon_name, 14, color)
            step_row.addWidget(step_icon)
            step_text = QLabel(stage_name)
            step_text.setStyleSheet(f"{Fonts.body(color)}")
            step_row.addWidget(step_text)
            step_row.addStretch()
            self.workflow_layout.addLayout(step_row)

        self.workflow_layout.addStretch()

    def _load_export_history(self):
        if not self.project_name:
            return
        from pathlib import Path
        exports_dir = self.manager.PROJECTS_DIR / self.project_name / "exports"
        if exports_dir.exists():
            files = list(exports_dir.glob("*.txt"))
            if files:
                text = "Recent: " + ", ".join(f.name for f in files[-3:])
                self.history_label.setText(text)
                return
        self.history_label.setText("No exports yet.")

    def _do_export(self):
        if not self.project_name:
            return

        validation = self._pipeline.validate_stage(self.project_name, "Export")
        if not validation.passed:
            for msg in validation.messages:
                NotificationService.get().warning(msg)
            return

        project_data = self.manager.load_project(self.project_name)
        if not project_data:
            self.status_label.setText("Project data not found.")
            return
        try:
            result = self.export_service.export_project(project_data, fmt="txt")
            self.status_label.setText(f"Exported to: {result}")
            c = ThemeManager.instance().colors()
            self.status_label.setStyleSheet(f"color: {c.SUCCESS}; font-weight: bold;")
            NotificationService.get().success(f"Exported '{self.project_name}' as TXT.")
            self._pipeline.mark_stage_completed(self.project_name, "Export")
            self._load_export_history()
        except Exception as e:
            self.status_label.setText(f"Export failed: {e}")
            c = ThemeManager.instance().colors()
            self.status_label.setStyleSheet(f"color: {c.ERROR};")
            self._pipeline.mark_stage_failed(self.project_name, "Export", str(e))
            NotificationService.get().error(f"Export failed: {e}")
