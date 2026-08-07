from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.autosave import get_autosave_manager
from core.history_manager import HistoryManager
from core.logger import get_logger
from core.notifications import NotificationService
from core.pipeline_service import get_pipeline_service
from core.project_manager import ProjectManager
from core.script_storage import ScriptStorage
from core.task_manager import TaskManager
from core.theme import Fonts, Spacing, Radius
from core.script_lengths import (
    DEFAULT_SCRIPT_MAX,
    DEFAULT_SCRIPT_MIN,
    SCRIPT_LENGTH_PRESETS,
    estimate_duration,
    find_preset,
    get_preset,
    project_script_bounds,
)
from operators.script.models import ScriptRequest
from operators.script.operator import ScriptOperator
from providers.provider_manager import get_provider_manager
from ..theme_pyside import ThemeManager
from ..widgets import (
    AutosaveIndicator,
    CardTitle,
    IconProvider,
    ModernButton,
    ModernCard,
    MutedLabel,
    ProgressWidget,
    StatusBadge,
)


_log = get_logger()


class _GenerationBridge(QObject):
    """Marshals background-thread task results back to the GUI thread.

    Qt signals connected to the ScriptPage (a widget living on the main
    thread) use queued connections, so emitting from the worker thread is
    safe. This prevents direct Qt widget access from background threads.
    """

    completed = Signal(str)
    failed = Signal(str)


PROGRESS_STAGES = [
    "Researching...",
    "Finding sources...",
    "Analyzing...",
    "Writing...",
    "Improving...",
    "Finalizing...",
]


class ScriptPage(QWidget):
    def __init__(self):
        super().__init__()
        self.manager = ProjectManager()
        self.script_storage = ScriptStorage()
        self.operator = ScriptOperator()
        self.task_manager = TaskManager()
        self._pipeline = get_pipeline_service()
        self.project_name = None
        self._script_min = DEFAULT_SCRIPT_MIN
        self._script_max = DEFAULT_SCRIPT_MAX
        self._loading_bounds = False
        self._script_text = ""
        self._saved_text = ""
        self._dirty = False
        self._progress_index = 0
        self._progress_timer = None
        self._last_research_context = ""
        self._history = HistoryManager()
        self._autosave = get_autosave_manager()
        self._autosave.register("script", self._autosave_save)
        self._autosave_indicator = AutosaveIndicator()
        self._autosave.on_status_change(self._autosave_indicator.set_status)
        ThemeManager.instance().on_change(lambda _: self._on_theme_changed())
        self._generation_bridge = _GenerationBridge()
        self._generation_bridge.completed.connect(self._on_generation_completed)
        self._generation_bridge.failed.connect(self._on_generation_failed)
        self._build()

    def _on_theme_changed(self):
        if self.project_name:
            self._load_project_data()

    def cleanup(self):
        self._stop_progress_animation()
        self.task_manager.cancel()

    def set_project(self, name):
        if name != self.project_name:
            # Persist pending edits to the OLD project before its autosave
            # callback could fire after we switch (Sprint 3.4B / C1, C2).
            self._autosave.flush_all()
            self._dirty = False
        self.project_name = name
        self._load_project_data()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self._build_project_header(layout)

        self._build_status_bar(layout)

        self._build_editor(layout)

        self._build_actions(layout)

        self.progress_widget = ProgressWidget()
        self.progress_widget.setVisible(False)
        layout.addWidget(self.progress_widget)

        # Default selection shown before any project is loaded.
        self._set_bounds(DEFAULT_SCRIPT_MIN, DEFAULT_SCRIPT_MAX, persist=False)

        layout.addStretch()

    def _build_project_header(self, parent):
        card = ModernCard()
        card.content_layout.setSpacing(8)

        c = ThemeManager.instance().colors()

        row = QHBoxLayout()
        row.setSpacing(16)

        name_label = CardTitle("")
        row.addWidget(name_label)

        self.status_badge = StatusBadge("")
        row.addWidget(self.status_badge)

        row.addStretch()
        card.content_layout.addLayout(row)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(24)
        self.info_topic = QLabel("")
        self.info_topic.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        self.info_platform = QLabel("")
        self.info_platform.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        self.info_language = QLabel("")
        self.info_language.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        meta_row.addWidget(self.info_topic)
        meta_row.addWidget(self.info_platform)
        meta_row.addWidget(self.info_language)
        meta_row.addStretch()
        card.content_layout.addLayout(meta_row)

        # Script Length preset selector (Sprint 3.4D).
        length_row = QHBoxLayout()
        length_row.setSpacing(8)
        length_label = QLabel("Script Length")
        length_label.setStyleSheet(f"{Fonts.caption_bold(c.TEXT_SECONDARY)}")
        length_row.addWidget(length_label)

        self.script_length_combo = QComboBox()
        for preset in SCRIPT_LENGTH_PRESETS:
            self.script_length_combo.addItem(self._preset_label(preset), preset.name)
        self.script_length_combo.setMinimumWidth(420)
        self.script_length_combo.currentIndexChanged.connect(self._on_preset_changed)
        length_row.addWidget(self.script_length_combo)
        length_row.addStretch()
        card.content_layout.addLayout(length_row)

        # "Selected Script Length" summary panel; updates instantly on
        # selection change.
        selection = QFrame()
        selection.setAttribute(Qt.WA_StyledBackground, True)
        selection.setStyleSheet(
            f"background-color: {c.SURFACE}; border: 1px solid {c.BORDER}; border-radius: 10px;"
        )
        selection_layout = QVBoxLayout(selection)
        selection_layout.setContentsMargins(12, 10, 12, 10)
        selection_layout.setSpacing(4)

        selection_title = QLabel("Selected Script Length")
        selection_title.setStyleSheet(f"{Fonts.caption_bold(c.TEXT_SECONDARY)}")
        selection_layout.addWidget(selection_title)

        def make_summary_row(caption, value_style):
            row = QHBoxLayout()
            row.setSpacing(8)
            caption_label = QLabel(caption)
            caption_label.setStyleSheet(f"{Fonts.caption(c.TEXT_MUTED)}")
            value_label = QLabel("")
            value_label.setStyleSheet(value_style)
            row.addWidget(caption_label)
            row.addWidget(value_label)
            row.addStretch()
            selection_layout.addLayout(row)
            return value_label

        self.preset_name_label = make_summary_row("Name", Fonts.css(13, '600', c.PRIMARY))
        self.preset_range_label = make_summary_row(
            "Character Range", Fonts.caption(c.TEXT_SECONDARY)
        )
        self.preset_duration_label = make_summary_row(
            "Estimated Duration", Fonts.caption(c.TEXT_SECONDARY)
        )

        card.content_layout.addWidget(selection)

        self.project_label = MutedLabel("")
        card.content_layout.addWidget(self.project_label)

        parent.addWidget(card)

    @staticmethod
    def _preset_label(preset):
        """Combo display text: name, character range, estimated duration."""
        return (
            f"{preset.name}  \u00B7  {preset.min_characters:,}\u2013{preset.max_characters:,} "
            f"characters  \u00B7  {preset.estimated_duration}"
        )

    def _on_preset_changed(self, index):
        if self._loading_bounds or index < 0:
            return
        # Resolve by the combo's item data so the selection stays correct
        # even if the combo item order ever diverges from the preset list.
        preset = get_preset(self.script_length_combo.itemData(index))
        if preset is None:
            return
        self._set_bounds(preset.min_characters, preset.max_characters, persist=True)

    def _set_bounds(self, min_characters, max_characters, persist=False):
        """Apply script length bounds to every label and optionally persist them."""
        changed = (
            min_characters != self._script_min or max_characters != self._script_max
        )
        self._script_min = min_characters
        self._script_max = max_characters

        preset = find_preset(min_characters, max_characters)
        name = preset.name if preset else f"{min_characters:,}\u2013{max_characters:,}"
        duration = (
            preset.estimated_duration
            if preset
            else estimate_duration(min_characters, max_characters)
        )

        c = ThemeManager.instance().colors()
        self.preset_name_label.setText(name)
        self.preset_name_label.setStyleSheet(f"{Fonts.css(13, '600', c.PRIMARY)}")
        self.preset_range_label.setText(f"{min_characters:,}\u2013{max_characters:,} characters")
        self.preset_range_label.setStyleSheet(f"{Fonts.caption(c.TEXT_SECONDARY)}")
        self.preset_duration_label.setText(duration)
        self.preset_duration_label.setStyleSheet(f"{Fonts.caption(c.TEXT_SECONDARY)}")

        # Sync the combo without re-triggering persistence.
        self._loading_bounds = True
        index = self.script_length_combo.findData(name)
        if index >= 0:
            self.script_length_combo.setCurrentIndex(index)
        self._loading_bounds = False

        self._update_text_metrics(self.editor.toPlainText())

        if persist and changed and self.project_name:
            self._persist_bounds(min_characters, max_characters)

    def _persist_bounds(self, min_characters, max_characters):
        """Write the selected bounds into the project metadata."""
        data = self.manager.load_project(self.project_name)
        if data is None:
            return
        data["script_min_characters"] = min_characters
        data["script_max_characters"] = max_characters
        # Keep the legacy keys in sync for backward-compatible consumers.
        data["script_min"] = min_characters
        data["script_max"] = max_characters
        data["last_modified"] = datetime.now().strftime("%d-%m-%Y %H:%M")
        self.manager.update_project(self.project_name, data)
        # Let the rest of the UI (e.g. the Projects page) refresh.
        from core.pipeline_events import get_pipeline_events
        get_pipeline_events().project_updated.emit(self.project_name)

    def _build_status_bar(self, parent):
        bar = QFrame()
        bar.setObjectName("card")
        bar.setAttribute(Qt.WA_StyledBackground, True)
        bar.setFixedHeight(40)

        c = ThemeManager.instance().colors()

        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 0, 16, 0)
        row.setSpacing(16)

        self.char_count_label = QLabel(f"0 / {DEFAULT_SCRIPT_MIN} minimum")
        self.char_count_label.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        row.addWidget(self.char_count_label)

        self.word_count_label = QLabel("0 words")
        self.word_count_label.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        row.addWidget(self.word_count_label)

        self.target_label = QLabel("")
        self.target_label.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        row.addWidget(self.target_label)

        self.status_label = MutedLabel("")
        row.addWidget(self.status_label)

        row.addStretch()

        row.addWidget(self._autosave_indicator)

        parent.addWidget(bar)

    def _build_editor(self, parent):
        self.editor = QPlainTextEdit()
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.setMinimumHeight(300)
        self.editor.setPlaceholderText("Your script will appear here...")
        parent.addWidget(self.editor, 1)

    def _build_actions(self, parent):
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(12)

        self.generate_btn = ModernButton("Generate Script", primary=True)
        self.generate_btn.clicked.connect(self.generate_script)
        actions.addWidget(self.generate_btn)

        self.save_btn = ModernButton("Save Script", primary=False)
        self.save_btn.clicked.connect(self.save_script)
        self.save_btn.setEnabled(False)
        actions.addWidget(self.save_btn)

        self.copy_btn = ModernButton("Copy Script", primary=False)
        self.copy_btn.clicked.connect(self.copy_script)
        actions.addWidget(self.copy_btn)

        actions.addStretch()
        parent.addLayout(actions)

    def _count_words(self, text):
        return len(text.split()) if text.strip() else 0

    def _on_text_changed(self):
        current = self.editor.toPlainText()
        self._dirty = (current != self._saved_text)
        self._update_text_metrics(current)
        self.save_btn.setEnabled(self._dirty)
        c = ThemeManager.instance().colors()
        if self._dirty:
            self.status_label.setText("Unsaved changes")
            self.status_label.setStyleSheet(f"color: {c.WARNING};")
        else:
            self.status_label.setText("Saved")
            self.status_label.setStyleSheet(f"color: {c.SUCCESS}; font-weight: bold;")
        self._autosave.mark_dirty("script")

    def _update_text_metrics(self, text):
        length = len(text)
        if length < self._script_min:
            self.char_count_label.setText(f"{length} / {self._script_min} minimum")
        else:
            self.char_count_label.setText(f"{length} / {self._script_max} maximum")
        self.word_count_label.setText(f"{self._count_words(text)} words")

    def _load_project_data(self):
        if not self.project_name:
            return
        project_data = self.manager.load_project(self.project_name)
        if project_data:
            topic = project_data.get("topic", "")
            platform = project_data.get("platform", "")
            language = project_data.get("language", "")

            c = ThemeManager.instance().colors()
            self.info_topic.setText(f"Topic: {topic}")
            self.info_topic.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
            self.info_platform.setText(f"Platform: {platform}")
            self.info_language.setText(f"Language: {language}")

            self.project_label.setText(f"/ {self.project_name}")
            self.status_badge.setText("Script")

            min_characters, max_characters = project_script_bounds(project_data)
            self._set_bounds(min_characters, max_characters, persist=False)

        script_data = self.script_storage.load(self.project_name)
        output = script_data.get("script_output", "")
        if output:
            # Never overwrite unsaved user edits (Sprint 3.4B / C2). Pipeline
            # events reload page data; only reload the editor when it is clean.
            if self._dirty:
                return
            self.editor.setPlainText(output)
            self._saved_text = output
            self._dirty = False
            self.save_btn.setEnabled(False)
            c = ThemeManager.instance().colors()
            self.status_label.setText("Saved")
            self.status_label.setStyleSheet(f"color: {c.SUCCESS}; font-weight: bold;")
            self._update_text_metrics(output)
        elif not self._dirty:
            # A project with no saved script must not keep another project's text.
            self._saved_text = ""
            self.editor.setPlainText("")
            self._dirty = False
            self.save_btn.setEnabled(False)
            self._update_text_metrics("")

    def generate_script(self):
        if not self.project_name:
            NotificationService.get().warning("Select a project first.")
            return

        validation = self._pipeline.validate_stage(self.project_name, "Script")
        if not validation.passed:
            for msg in validation.messages:
                NotificationService.get().warning(msg)
            return

        project_data = self.manager.load_project(self.project_name)
        if not project_data:
            return

        ok, provider_msg = get_provider_manager().preflight_check()
        if not ok:
            NotificationService.get().warning(provider_msg)
            return

        self._pipeline.mark_stage_started(self.project_name, "Script")

        self.generate_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.progress_widget.setVisible(True)
        self.progress_widget.reset()
        self._progress_index = 0
        self._start_progress_animation()

        def run_task(task_manager):
            research_context = self._obtain_research_context(project_data)
            min_characters, max_characters = project_script_bounds(project_data)
            request = ScriptRequest(
                topic=project_data.get("topic", ""),
                platform=project_data.get("platform", "Long Form"),
                video_type=project_data.get("video_type", "Educational"),
                language=project_data.get("language", "English"),
                script_mode=project_data.get("script_mode", "characters"),
                script_min=min_characters,
                script_max=max_characters,
                duration_preset=project_data.get("duration_preset", ""),
                research_sources=research_context,
                keywords=project_data.get("keywords", ""),
            )
            self._last_research_context = research_context
            return self.operator.execute(request)

        def on_complete(result):
            self._generation_bridge.completed.emit(result)

        def on_error(exc):
            _log.error("ScriptPage", f"generate_script failed: {exc}", exc)
            self._generation_bridge.failed.emit(str(exc))

        self.task_manager.run_task(
            task_name="Generate Script",
            task_func=run_task,
            on_complete=on_complete,
            on_error=on_error,
        )

    def _obtain_research_context(self, project_data):
        """Return research context for script generation.

        Reuses stored research when available; otherwise runs the research
        operator automatically in the backend and persists the result.
        """
        from core.research_storage import ResearchStorage
        from operators.research.operator import ResearchOperator
        from operators.research.prompt_builder import ResearchRequest

        storage = ResearchStorage()
        existing = storage.load(self.project_name) or {}
        generated = (existing.get("generated_research") or "").strip()
        if generated:
            return generated

        _log.info("ScriptPage", f"No stored research for {self.project_name}; generating automatically")
        topic = project_data.get("topic", "")
        operator = ResearchOperator()
        request = ResearchRequest(
            topic=topic,
            keywords=project_data.get("keywords", ""),
            goal=f"Provide thorough, accurate background research for a {project_data.get('video_type', 'Educational')} video about: {topic}.",
            sources=project_data.get("research_sources", ""),
            audience="general audience",
            language=project_data.get("language", "English"),
        )
        fresh_research = operator.execute(request)
        storage.save(
            project_name=self.project_name,
            topic=topic,
            keywords=str(request.keywords),
            goal=request.goal,
            sources=str(request.sources),
            prompt_preview=operator.get_prompt_preview(request),
            generated_research=fresh_research,
        )
        return fresh_research

    def _on_generation_completed(self, result):
        """Handle a successful script generation on the GUI thread."""
        self._stop_progress_animation()
        self.editor.setPlainText(result)
        self._saved_text = result
        self._dirty = False

        project_data = self.manager.load_project(self.project_name) or {}

        min_characters, max_characters = project_script_bounds(project_data)
        self.script_storage.save(
            project_name=self.project_name,
            script_output=result,
            script_mode=project_data.get("script_mode", "characters"),
            script_min=min_characters,
            script_max=max_characters,
            duration_preset=project_data.get("duration_preset", ""),
            research_data=self._last_research_context,
        )
        self._last_research_context = ""

        project_data["last_modified"] = __import__("datetime").datetime.now().strftime("%d-%m-%Y %H:%M")
        project_data["status"] = "Script"
        self.manager.update_project(self.project_name, project_data)

        self._pipeline.mark_stage_completed(self.project_name, "Script")

        self.progress_widget.show_complete("Script generated successfully.")
        QTimer.singleShot(2000, lambda: self.progress_widget.setVisible(False))

        self.generate_btn.setEnabled(True)
        self.save_btn.setEnabled(False)
        c = ThemeManager.instance().colors()
        self.status_label.setText("Saved")
        self.status_label.setStyleSheet(f"color: {c.SUCCESS}; font-weight: bold;")
        self._update_text_metrics(result)
        self._history.record_action(
            self.project_name, "Generated",
            f"Generated script ({self._count_words(result)} words)"
        )
        NotificationService.get().success("Script generated successfully.")

    def _on_generation_failed(self, message):
        """Handle a failed generation on the GUI thread."""
        self._stop_progress_animation()
        self.generate_btn.setEnabled(True)
        self.progress_widget.setVisible(False)
        friendly = self._friendly_error_message(message)
        self._pipeline.mark_stage_failed(self.project_name, "Script", friendly)
        c = ThemeManager.instance().colors()
        self.status_label.setText(f"Error: {friendly}")
        self.status_label.setStyleSheet(f"color: {c.ERROR};")
        NotificationService.get().error(friendly)

    @staticmethod
    def _friendly_error_message(message):
        """Condense a raw provider error into a concise user-facing message.

        Provider failover errors embed the full SDK JSON payload; strip it
        so the status label and notification stay readable.
        """
        text = str(message)
        marker = "Last error: "
        if marker in text:
            text = "All available providers are exhausted. " + text.split(marker, 1)[1]
        if " {" in text:
            text = text.split(" {", 1)[0]
        if text.endswith("RESOURCE_EXHAUSTED."):
            text = text[:-len("RESOURCE_EXHAUSTED.")] + "(quota exceeded)."
        return text.strip()

    def _autosave_save(self):
        if not self.project_name:
            return
        text = self.editor.toPlainText()
        self.script_storage.save(
            project_name=self.project_name,
            script_output=text,
        )
        self._saved_text = text
        self._dirty = False
        self.save_btn.setEnabled(False)
        c = ThemeManager.instance().colors()
        self.status_label.setText("Saved")
        self.status_label.setStyleSheet(f"color: {c.SUCCESS}; font-weight: bold;")

    def copy_script(self):
        text = self.editor.toPlainText()
        QApplication.clipboard().setText(text)
        NotificationService.get().success("Script copied.")

    def _start_progress_animation(self):
        self._progress_timer = QTimer(self)
        self._progress_timer.timeout.connect(self._animate_progress)
        self._progress_timer.start(3000)
        self._animate_progress()

    def _animate_progress(self):
        if self._progress_index >= len(PROGRESS_STAGES):
            self.progress_widget.set_progress(95, "Finalizing...", "", "")
            if self._progress_timer:
                self._progress_timer.stop()
            return
        stage = PROGRESS_STAGES[self._progress_index]
        pct = int((self._progress_index + 1) / len(PROGRESS_STAGES) * 95)
        self.progress_widget.set_progress(pct, stage, "", "")
        self._progress_index += 1

    def _stop_progress_animation(self):
        if self._progress_timer:
            self._progress_timer.stop()
            self._progress_timer.deleteLater()
            self._progress_timer = None

    def save_script(self):
        if not self.project_name:
            return
        self._autosave_save()
        self._history.record_action(self.project_name, "Saved", "Manually saved script")
        NotificationService.get().success("Script saved.")
