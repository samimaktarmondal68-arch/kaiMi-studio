from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.autosave import get_autosave_manager
from core.export_service import ExportService
from core.history_manager import HistoryManager
from core.image_prompt_storage import ImagePromptStorage
from core.logger import get_logger
from core.notifications import NotificationService
from core.pipeline_service import get_pipeline_service
from core.project_manager import ProjectManager
from core.script_storage import ScriptStorage
from core.task_manager import TaskManager
from core.transcript_storage import TranscriptStorage
from core.theme import Fonts, Spacing, Radius
from operators.image_prompt.models import ImagePromptRequest
from operators.image_prompt.operator import ImagePromptOperator
from operators.image_prompt.parser import ImagePromptParser
from ui.theme_pyside import ThemeManager
from ui.widgets import (
    CardTitle,
    EmptyState,
    IconProvider,
    ModernButton,
    ModernCard,
    MutedLabel,
    ProgressWidget,
    SectionHeader,
    StatusBadge,
)


class _GenerationBridge(QObject):
    """Marshals background-thread task results back to the GUI thread.

    Qt signals connected to the ImagePromptsPage (a widget living on the
    main thread) use queued connections, so emitting from the worker thread
    is safe. This prevents direct Qt widget access from background threads.
    """

    completed = Signal(object)
    failed = Signal(object)


_log = get_logger()


def _format_timestamp(segment: dict) -> str:
    """Format a raw segment start as MM:SS for display."""
    raw = segment.get("start", 0) or 0
    total = int(raw)
    return f"{total // 60:02d}:{total % 60:02d}"


class ImagePromptsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.manager = ProjectManager()
        self.script_storage = ScriptStorage()
        self.prompt_storage = ImagePromptStorage()
        self.transcript_storage = TranscriptStorage()
        self.operator = ImagePromptOperator()
        self.parser = ImagePromptParser()
        self.export_service = ExportService(self.manager)
        self.task_manager = TaskManager()
        self._pipeline = get_pipeline_service()
        self.project_name = None
        self._prompts = []
        self._history = HistoryManager()
        self._autosave = get_autosave_manager()
        self._autosave.register("image_prompts", self._autosave_save)
        self._generation_bridge = _GenerationBridge()
        self._generation_bridge.completed.connect(self._on_generation_completed)
        self._generation_bridge.failed.connect(self._on_generation_failed)
        ThemeManager.instance().on_change(lambda _: self._on_theme_changed())
        self._build()

    def _on_theme_changed(self):
        self._refresh_theme_static()
        if self.project_name:
            self._load_project_data()

    def _refresh_theme_static(self):
        """Re-apply theme tokens to chrome built once in ``_build``.

        The controls description and the empty state keep the colors they
        were constructed with unless restyled here (Light-theme contrast
        regression after a runtime theme switch).
        """
        c = ThemeManager.instance().colors()
        self.controls_desc_label.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        self.status_badge.refresh_theme()
        if self.empty_state is not None:
            self.empty_state.refresh_theme()

    def set_project(self, name):
        self.project_name = name
        self._load_project_data()

    def cleanup(self):
        """Cancel any in-flight generation task before the app exits."""
        self.task_manager.cancel()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self._build_project_header(layout)

        self._build_controls(layout)

        self._build_source_context(layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)

        self.prompts_container = QWidget()
        self.prompts_layout = QVBoxLayout(self.prompts_container)
        self.prompts_layout.setContentsMargins(0, 0, 0, 0)
        self.prompts_layout.setSpacing(16)
        self.prompts_layout.addStretch()

        self.empty_state = EmptyState(
            title="No Prompts Yet",
            description="No prompts yet. Generate prompts from your script.",
        )
        self.prompts_layout.addWidget(self.empty_state)

        scroll.setWidget(self.prompts_container)
        layout.addWidget(scroll, 1)

    def _build_project_header(self, parent):
        card = ModernCard()
        card.content_layout.setSpacing(8)

        c = ThemeManager.instance().colors()

        row = QHBoxLayout()
        row.setSpacing(16)

        name_label = CardTitle("Image Prompts")
        row.addWidget(name_label)

        self.status_badge = StatusBadge("Image Prompts")
        row.addWidget(self.status_badge)

        row.addStretch()
        card.content_layout.addLayout(row)

        self.project_label = MutedLabel("")
        card.content_layout.addWidget(self.project_label)

        parent.addWidget(card)

    def _build_controls(self, parent):
        c = ThemeManager.instance().colors()
        controls_card = ModernCard()
        controls_card.content_layout.setSpacing(8)

        self.controls_desc_label = QLabel(
            "Uses your script and transcript to generate production-ready image prompts for each scene."
        )
        self.controls_desc_label.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        controls_card.content_layout.addWidget(self.controls_desc_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.generate_btn = ModernButton("Generate Prompts", primary=True)
        self.generate_btn.clicked.connect(self.generate_prompts)
        btn_row.addWidget(self.generate_btn)

        self.export_btn = ModernButton("Export TXT", primary=False)
        self.export_btn.clicked.connect(self.export_txt)
        btn_row.addWidget(self.export_btn)
        btn_row.addStretch()
        controls_card.content_layout.addLayout(btn_row)

        self.progress_widget = ProgressWidget()
        self.progress_widget.setVisible(False)
        controls_card.content_layout.addWidget(self.progress_widget)

        parent.addWidget(controls_card)

    def _build_source_context(self, parent):
        """Show which source data reached this stage (script, transcript, timestamps)."""
        c = ThemeManager.instance().colors()
        card = ModernCard()
        card.content_layout.setSpacing(8)

        card.content_layout.addWidget(SectionHeader("Source Context"))

        self.source_script_label = MutedLabel("Script: not found")
        self.source_transcript_label = MutedLabel("Transcript: not found")
        self.source_timestamps_label = MutedLabel("Timestamps: none")
        card.content_layout.addWidget(self.source_script_label)
        card.content_layout.addWidget(self.source_transcript_label)
        card.content_layout.addWidget(self.source_timestamps_label)

        parent.addWidget(card)

    def _load_project_data(self):
        if not self.project_name:
            return
        self.project_label.setText(f"/ {self.project_name}")
        stored = self.prompt_storage.load(self.project_name)
        self._prompts = stored.get("prompts", [])
        self._render_prompts()
        self._load_source_context()

    def _load_source_context(self):
        """Refresh the source-context summary from stored script and transcript."""
        script_text = ""
        script_data = self.script_storage.load(self.project_name)
        if script_data:
            script_text = (script_data.get("script_output") or "").strip()

        transcript_data = self.transcript_storage.load(self.project_name)
        transcript = (transcript_data.get("text") or "").strip()
        segments = transcript_data.get("segments") or []

        if script_text:
            self.source_script_label.setText(
                f"Script: {len(script_text):,} characters ready"
            )
        else:
            self.source_script_label.setText("Script: not found")

        if transcript:
            self.source_transcript_label.setText(
                f"Transcript: {len(transcript):,} characters ready"
            )
        else:
            self.source_transcript_label.setText("Transcript: not found")

        if segments:
            first_ts = segments[0].get("time", _format_timestamp(segments[0]))
            last_ts = segments[-1].get("time", _format_timestamp(segments[-1]))
            self.source_timestamps_label.setText(
                f"Timestamps: {len(segments)} segments ({first_ts} -> {last_ts})"
            )
        else:
            self.source_timestamps_label.setText("Timestamps: none")

    def _render_prompts(self):
        while self.prompts_layout.count():
            item = self.prompts_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not self._prompts:
            self.empty_state = EmptyState(
                title="No Prompts Yet",
                description="No prompts yet. Generate prompts from your script.",
            )
            self.prompts_layout.addWidget(self.empty_state)
            self.prompts_layout.addStretch()
            return

        self.empty_state = None
        for prompt in self._prompts:
            self._add_prompt_card(prompt)

        self.prompts_layout.addStretch()

    def _add_prompt_card(self, prompt):
        c = ThemeManager.instance().colors()
        card = ModernCard()
        card.content_layout.setSpacing(12)

        header = QHBoxLayout()
        scene_label = QLabel(f"Scene {prompt.get('scene_number', 1)}")
        scene_label.setStyleSheet(f"{Fonts.card_title(c.TEXT)}")
        header.addWidget(scene_label)

        ts = prompt.get("timestamp", "")
        if ts:
            ts_icon = IconProvider.icon_label("clock", 14, c.TEXT_SECONDARY)
            header.addWidget(ts_icon)
            ts_label = QLabel(ts)
            ts_label.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
            header.addWidget(ts_label)

        header.addStretch()

        copy_btn = ModernButton("Copy", primary=False)
        copy_btn.setFixedSize(80, 36)
        copy_btn.clicked.connect(lambda p=prompt: self._copy_prompt(p))
        header.addWidget(copy_btn)

        card.content_layout.addLayout(header)

        text_edit = QPlainTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(prompt.get("full_image_prompt", ""))
        text_edit.setMinimumHeight(80)
        text_edit.setMaximumHeight(140)
        card.content_layout.addWidget(text_edit)

        self.prompts_layout.addWidget(card)

    def _copy_prompt(self, prompt):
        text = prompt.get("full_image_prompt", "")
        if text:
            from PySide6.QtGui import QGuiApplication
            clipboard = QGuiApplication.clipboard()
            if clipboard:
                clipboard.setText(text)
            NotificationService.get().info("Prompt copied to clipboard.")

    def generate_prompts(self):
        if not self.project_name:
            NotificationService.get().warning("Select a project first.")
            return

        if self.task_manager.is_running:
            NotificationService.get().warning("Generation already in progress.")
            return

        validation = self._pipeline.validate_stage(self.project_name, "Image Prompts")
        if not validation.passed:
            for msg in validation.messages:
                NotificationService.get().warning(msg)
            return

        script_data = self.script_storage.load(self.project_name)
        script_text = script_data.get("script_output", "")
        if not script_text:
            NotificationService.get().warning("No script found. Generate a script first.")
            return

        project_data = self.manager.load_project(self.project_name)

        transcript_data = self.transcript_storage.load(self.project_name)
        transcript = transcript_data.get("text", "")
        timestamps = transcript_data.get("segments") or None

        self._pipeline.mark_stage_started(self.project_name, "Image Prompts")

        self.generate_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.progress_widget.setVisible(True)
        self.progress_widget.set_progress(0, status="Starting...")

        def run_task(task_manager):
            task_manager.update_progress(0.3, "Preparing prompt request...")
            request = ImagePromptRequest(
                script_text=script_text,
                transcript=transcript,
                timestamps=timestamps,
                topic=project_data.get("topic", ""),
                language=project_data.get("language", "English"),
            )
            task_manager.update_progress(0.5, "Generating image prompts...")
            raw = self.operator.execute(request)
            task_manager.update_progress(0.85, "Parsing prompts...")
            prompts = self.parser.parse(raw)
            task_manager.update_progress(0.95, "Finalizing...")
            return prompts

        def on_complete(prompts):
            self._generation_bridge.completed.emit(prompts)

        def on_error(exc):
            _log.error("ImagePromptsPage", "generate_prompts failed", exc)
            self._generation_bridge.failed.emit(exc)

        self.task_manager.run_task(
            task_name="Generate Image Prompts",
            task_func=run_task,
            on_complete=on_complete,
            on_error=on_error,
        )

    def _on_generation_completed(self, prompts):
        """Handle successful generation on the GUI thread."""
        self._prompts = prompts
        self.prompt_storage.save(self.project_name, prompts)
        self._render_prompts()

        self._pipeline.mark_stage_completed(self.project_name, "Image Prompts")

        self.generate_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.progress_widget.show_complete(f"Generated {len(prompts)} image prompts.")
        QTimer.singleShot(2000, lambda: self.progress_widget.setVisible(False))
        self._history.record_action(
            self.project_name, "Generated",
            f"Generated {len(prompts)} image prompts"
        )
        NotificationService.get().success(f"Generated {len(prompts)} image prompts.")

    def _on_generation_failed(self, exc):
        """Handle a failed generation on the GUI thread."""
        self.generate_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.progress_widget.setVisible(False)
        self._pipeline.mark_stage_failed(self.project_name, "Image Prompts", str(exc))
        NotificationService.get().error(str(exc))

    def _autosave_save(self):
        if not self.project_name:
            return
        self.prompt_storage.save(self.project_name, self._prompts)

    def export_txt(self):
        if not self.project_name:
            return
        if not self._prompts:
            NotificationService.get().warning("No prompts to export.")
            return
        try:
            project_data = self.manager.load_project(self.project_name)
            result = self.export_service.export_project(project_data, fmt="txt")
            NotificationService.get().success(f"Exported to {result}")
        except Exception as e:
            NotificationService.get().error(f"Export failed: {e}")
