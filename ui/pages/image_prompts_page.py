import time
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
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
from core.task_manager import TaskCancelledError, TaskManager
from core.theme import Fonts, Spacing, Radius
from core.transcript_storage import TranscriptStorage
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
    cancelled = Signal()


_log = get_logger()

#: RC-7 pipeline stage keys -> friendly labels for the progress step line
#: and for failure diagnostics ("failed during Parsing Response").
STAGE_LABELS = {
    "idle": "Idle",
    "validating_source": "Validating Source",
    "selecting_provider": "Selecting Provider",
    "generating": "Generating",
    "parsing": "Parsing Response",
    "validating": "Validating Prompts",
    "retrying": "Retrying",
    "saving": "Saving",
    "completed": "Completed",
    "failed": "Failed",
    "cancelled": "Cancelled",
}


def _provider_preflight() -> tuple[bool, str]:
    """Return (ok, message) for the active AI provider's configuration.

    Runs before generation starts so a provider that cannot run at all (no
    active provider, missing model, missing API key) is reported immediately
    with an actionable message instead of leaving the page silently on
    'No Prompts Yet'. Network/quota failures still surface through the
    worker's failure path.
    """
    from providers.provider_manager import get_provider_manager
    return get_provider_manager().preflight_check()


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
        #: Human-readable failure from the last generation attempt; None when
        #: idle, running, or successful (RC-6: no silent 'No Prompts Yet').
        self._generation_error = None
        self._gen_started_at = None
        self._history = HistoryManager()
        self._autosave = get_autosave_manager()
        self._autosave.register("image_prompts", self._autosave_save)
        self._generation_bridge = _GenerationBridge()
        self._generation_bridge.completed.connect(self._on_generation_completed)
        self._generation_bridge.failed.connect(self._on_generation_failed)
        self._generation_bridge.cancelled.connect(self._on_generation_cancelled)
        self._progress_poll = QTimer(self)
        self._progress_poll.setInterval(200)
        self._progress_poll.timeout.connect(self._poll_progress)
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
        self._refresh_generation_error()
        self._refresh_export_status()

    def set_project(self, name):
        if name != self.project_name:
            # A failure from another project must not leak into this one.
            self._generation_error = None
            # An export result belongs to the previous project; never show a
            # stale success/error message on a freshly opened one (RC-7.1).
            self._export_status_message = ""
            self._export_status_error = False
            self._export_status_muted = False
            self._refresh_export_status()
            # An in-flight generation belongs to the previous project: request
            # a cooperative cancel. ``_generation_project`` is intentionally
            # NOT cleared here — if the worker still completes (the provider
            # call was already past the last cancel check), the completion
            # handler must still persist the result to the project the task
            # was started for, never to the newly opened one (RC-7).
            if self.task_manager.is_running:
                self.task_manager.cancel()
        self.project_name = name
        self._load_project_data()

    def cleanup(self):
        """Cancel any in-flight generation task before the app exits."""
        self._progress_poll.stop()
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
        self.controls_desc_label.setWordWrap(True)
        controls_card.content_layout.addWidget(self.controls_desc_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.generate_btn = ModernButton("Generate Prompts", primary=True)
        self.generate_btn.clicked.connect(self.generate_prompts)
        btn_row.addWidget(self.generate_btn)

        self.cancel_btn = ModernButton("Cancel", primary=False)
        self.cancel_btn.clicked.connect(self._cancel_generation)
        self.cancel_btn.setVisible(False)
        btn_row.addWidget(self.cancel_btn)

        self.export_btn = ModernButton("Export TXT", primary=False)
        self.export_btn.clicked.connect(self.export_txt)
        btn_row.addWidget(self.export_btn)
        btn_row.addStretch()
        controls_card.content_layout.addLayout(btn_row)

        self.progress_widget = ProgressWidget()
        self.progress_widget.setVisible(False)
        controls_card.content_layout.addWidget(self.progress_widget)

        # Persistent failure banner (RC-6): a failed generation must be
        # visible and actionable, never a silent 'No Prompts Yet'.
        self.failure_label = QLabel("")
        self.failure_label.setWordWrap(True)
        self.failure_label.setVisible(False)
        controls_card.content_layout.addWidget(self.failure_label)

        # Persistent export feedback (RC-7.1): success/failure of the last
        # TXT export stays visible instead of vanishing with a toast.
        self.export_status_label = QLabel("")
        self.export_status_label.setWordWrap(True)
        self.export_status_label.setVisible(False)
        controls_card.content_layout.addWidget(self.export_status_label)

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
        self._refresh_generation_error()
        self._update_action_labels()

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
        header.setSpacing(8)
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

        title = prompt.get("prompt_title", "")
        if title:
            title_label = QLabel(title)
            title_label.setStyleSheet(f"{Fonts.body_bold(c.TEXT)}")
            title_label.setWordWrap(True)
            card.content_layout.addWidget(title_label)

        text_edit = QPlainTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(prompt.get("full_image_prompt", ""))
        text_edit.setMinimumHeight(90)
        text_edit.setMaximumHeight(220)
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

    # ------------------------------------------------------------------
    # Generation pipeline (RC-7)
    # ------------------------------------------------------------------

    def generate_prompts(self):
        if not self.project_name:
            NotificationService.get().warning("Select a project first.")
            return

        if self.task_manager.is_running:
            NotificationService.get().warning("Generation already in progress.")
            return

        # Never silently destroy a completed prompt set (RC-7).
        if self._prompts and not self._confirm_regenerate():
            return

        validation = self._pipeline.validate_stage(self.project_name, "Image Prompts")
        if not validation.passed:
            for msg in validation.messages:
                NotificationService.get().warning(msg)
            return

        # Fail fast (and visibly) when the provider cannot run at all.
        ok, preflight_msg = _provider_preflight()
        if not ok:
            self._set_generation_error(
                f"Image prompt generation unavailable.\n\n{preflight_msg}"
            )
            NotificationService.get().error(
                f"Image prompt generation unavailable: {preflight_msg}"
            )
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

        self._set_generation_error(None)
        self._pipeline.mark_stage_started(self.project_name, "Image Prompts")
        self._generation_project = self.project_name

        self._gen_started_at = time.monotonic()
        self.generate_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self.cancel_btn.setEnabled(True)
        self.cancel_btn.setText("Cancel")
        self.progress_widget.setVisible(True)
        self.progress_widget.reset()
        self.progress_widget.set_indeterminate(
            status="Preparing source...", step="Stage: Validating Source"
        )
        self._progress_poll.start()

        def run_task(task_manager):
            task_manager.update_progress(
                0.02, "Preparing source...", stage="validating_source"
            )

            def on_stage(stage, message, fraction):
                task_manager.update_progress(fraction, message, stage=stage)

            # Guard against a project removed mid-session: a missing project
            # must fail with an actionable message, not an AttributeError.
            project = project_data or {}
            request = ImagePromptRequest(
                script_text=script_text,
                transcript=transcript,
                timestamps=timestamps,
                topic=project.get("topic", ""),
                language=project.get("language", "English"),
            )
            return self.operator.generate_prompts(
                request,
                progress_callback=on_stage,
                cancel_event=task_manager.cancel_event,
                max_retries=1,
            )

        def on_complete(prompts):
            self._generation_bridge.completed.emit(prompts)

        def on_error(exc):
            _log.error("ImagePromptsPage", "generate_prompts failed", exc)
            if isinstance(exc, TaskCancelledError):
                self._generation_bridge.cancelled.emit()
            else:
                self._generation_bridge.failed.emit(exc)

        self.task_manager.run_task(
            task_name="Generate Image Prompts",
            task_func=run_task,
            on_complete=on_complete,
            on_error=on_error,
        )

    def _on_generation_completed(self, prompts):
        """Handle successful generation on the GUI thread."""
        self._progress_poll.stop()
        # Persist to the project the task was started for, even if the user
        # navigated away mid-run (RC-7: results never land in the wrong
        # project).
        target = self._generation_project or self.project_name
        self.prompt_storage.save(target, prompts)
        self._pipeline.mark_stage_completed(target, "Image Prompts")
        if target != self.project_name:
            # The page moved on; restore controls and let the target project
            # load its fresh prompts from storage next time it is opened.
            self._generation_project = None
            self.generate_btn.setEnabled(True)
            self.export_btn.setEnabled(True)
            self.cancel_btn.setVisible(False)
            self.progress_widget.setVisible(False)
            return
        self._prompts = prompts
        self._set_generation_error(None)
        self._render_prompts()

        self.generate_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.progress_widget.show_complete(f"Generated {len(prompts)} image prompts.")
        # Never hide the bar mid-run: a new generation started within the
        # 2.5s window must keep its progress visible (RC-7).
        QTimer.singleShot(
            2500,
            lambda: (
                self.progress_widget.setVisible(False)
                if not self.task_manager.is_running
                else None
            ),
        )
        self._history.record_action(
            self.project_name, "Generated",
            f"Generated {len(prompts)} image prompts"
        )
        NotificationService.get().success(f"Generated {len(prompts)} image prompts.")
        self._update_action_labels()

    def _on_generation_failed(self, exc):
        """Handle a failed generation on the GUI thread.

        The failure is persisted in the page state and shown as a visible,
        stage-tagged banner so the user always sees why the page is not
        showing prompts (RC-6/RC-7: no silent 'No Prompts Yet').
        """
        self._progress_poll.stop()
        reason = str(exc).strip() or "Unknown generation error."
        stage_key = self.task_manager.stage or "generating"
        stage_label = STAGE_LABELS.get(stage_key, stage_key.title())
        target = self._generation_project or self.project_name
        if target != self.project_name:
            # The failure belongs to a project the user has left; only the
            # pipeline state of that project may be marked, never the current
            # one, and the current page must not show a foreign banner.
            self._generation_project = None
            self.generate_btn.setEnabled(True)
            self.export_btn.setEnabled(True)
            self.cancel_btn.setVisible(False)
            self.progress_widget.setVisible(False)
            self._pipeline.mark_stage_failed(target, "Image Prompts", reason)
            return
        if self._prompts:
            note = "Existing prompts were not modified."
        else:
            note = "No prompts were saved."
        self._set_generation_error(
            f"Image prompt generation failed during {stage_label}.\n\n"
            f"Reason: {reason}\n\n{note}"
        )
        self.generate_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.progress_widget.stop()
        self.progress_widget.setVisible(False)
        self._pipeline.mark_stage_failed(self.project_name, "Image Prompts", reason)
        NotificationService.get().error(
            f"Image prompt generation failed during {stage_label}: {reason}"
        )
        self._update_action_labels()

    def _on_generation_cancelled(self):
        """Restore the page after a user-initiated cancellation.

        Project state (including any existing prompt set) is left intact;
        only the in-flight generation is discarded.
        """
        self._progress_poll.stop()
        target = self._generation_project or self.project_name
        self._generation_project = None
        self.generate_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.progress_widget.stop()
        self.progress_widget.setVisible(False)
        if target == self.project_name:
            self._pipeline.mark_stage_reset(self.project_name, "Image Prompts")
            self._update_action_labels()
            NotificationService.get().info(
                "Generation cancelled. Existing prompts were not modified."
            )

    def _cancel_generation(self):
        """Request a cooperative cancel of the running generation."""
        if not self.task_manager.is_running:
            return
        self.task_manager.cancel()
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Cancelling...")
        self.progress_widget.set_indeterminate(
            status="Cancelling... the in-flight provider request must finish, "
            "then generation stops."
        )

    def _confirm_regenerate(self) -> bool:
        """Ask before replacing the current prompt set. Returns True on Regenerate."""
        box = QMessageBox(self)
        box.setWindowTitle("Regenerate Prompts")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(
            f"This will replace the current {len(self._prompts)} image prompts.\n\n"
            "Continue?"
        )
        regenerate_btn = box.addButton(
            "Regenerate", QMessageBox.ButtonRole.DestructiveRole
        )
        cancel_btn = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel_btn)
        box.exec()
        return box.clickedButton() is regenerate_btn

    def _update_action_labels(self):
        """Keep the action button honest about what it will do (RC-7)."""
        if self._prompts:
            self.generate_btn.setText("Regenerate Prompts")
        else:
            self.generate_btn.setText("Generate Prompts")

    def _set_generation_error(self, message):
        """Store the last generation failure and refresh the failure banner."""
        self._generation_error = message
        self._refresh_generation_error()

    def _refresh_generation_error(self):
        """Show or hide the persistent failure banner from page state."""
        c = ThemeManager.instance().colors()
        if self._generation_error:
            self.failure_label.setText(self._generation_error)
            self.failure_label.setStyleSheet(f"color: {c.ERROR}; font-weight: bold;")
            self.failure_label.setVisible(True)
        else:
            self.failure_label.setText("")
            self.failure_label.setVisible(False)

    def _poll_progress(self):
        """Mirror TaskManager stage state into an indeterminate progress widget.

        No fabricated percentages: the bar runs indeterminate and the step
        line shows the real pipeline stage plus elapsed time (RC-7).
        """
        if not self.task_manager.is_running:
            self._progress_poll.stop()
            return
        stage_key = self.task_manager.stage or "generating"
        stage_label = STAGE_LABELS.get(stage_key, stage_key.title())
        message = self.task_manager.status_message or "Generating image prompts..."
        self.progress_widget.set_indeterminate(
            status=message, step=f"Stage: {stage_label}"
        )
        if self._gen_started_at is not None:
            self.progress_widget.set_elapsed(time.monotonic() - self._gen_started_at)

    def _autosave_save(self):
        if not self.project_name:
            return
        self.prompt_storage.save(self.project_name, self._prompts)

    def export_txt(self):
        """Export the current prompt set to a user-chosen TXT destination.

        The OS save dialog lets the user pick the file; cancelling it is a
        silent no-op (never an error). The file is written as UTF-8 with the
        shared RC-7 block format (scene, timestamp, title, full prompt).
        Success and failure both leave a persistent status line on the page.
        """
        if not self.project_name:
            return
        # Export from the persisted project state (source of truth), never a
        # possibly-stale in-memory copy (RC-7).
        stored = self.prompt_storage.load(self.project_name)
        prompts = stored.get("prompts", [])
        if not prompts:
            # Informational empty state, not an error (RC-7.1).
            self._set_export_status("No prompts to export.", muted=True)
            NotificationService.get().warning("No prompts to export.")
            return

        default_dir = self.manager.PROJECTS_DIR / self.project_name / "exports"
        suggested = default_dir / f"{self.project_name}_image_prompts.txt"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Image Prompts",
            str(suggested),
            "Text Files (*.txt)",
        )
        if not file_path:
            # User cancelled the dialog: not an error, nothing to report.
            return
        if not file_path.lower().endswith(".txt"):
            file_path += ".txt"

        try:
            text = ExportService.build_image_prompts_txt(prompts)
            Path(file_path).write_text(text, encoding="utf-8")
        except OSError as e:
            self._set_export_status(f"Export failed: {e}", error=True)
            NotificationService.get().error(f"Export failed: {e}")
            return

        self._set_export_status("Prompts exported successfully.")
        NotificationService.get().success("Prompts exported successfully.")

    def _set_export_status(self, message: str, error: bool = False, muted: bool = False):
        """Store and show a persistent export status line on the page.

        ``error`` renders in the theme's error color, ``muted`` in the
        secondary text color (used for informational states such as an empty
        prompt set); the default success render is used otherwise.
        """
        self._export_status_message = message
        self._export_status_error = error
        self._export_status_muted = muted
        self._refresh_export_status()

    def _refresh_export_status(self):
        """Render the export status line with the current theme's colors."""
        c = ThemeManager.instance().colors()
        message = getattr(self, "_export_status_message", "")
        if not message:
            self.export_status_label.setText("")
            self.export_status_label.setVisible(False)
            return
        if getattr(self, "_export_status_error", False):
            color = c.ERROR
        elif getattr(self, "_export_status_muted", False):
            color = c.TEXT_SECONDARY
        else:
            color = c.SUCCESS
        self.export_status_label.setText(message)
        self.export_status_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        self.export_status_label.setVisible(True)
