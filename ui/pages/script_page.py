from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtWidgets import (
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

    def set_project(self, name):
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
        self.info_target = QLabel("")
        self.info_target.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        meta_row.addWidget(self.info_topic)
        meta_row.addWidget(self.info_platform)
        meta_row.addWidget(self.info_language)
        meta_row.addWidget(self.info_target)
        meta_row.addStretch()
        card.content_layout.addLayout(meta_row)

        self.project_label = MutedLabel("")
        card.content_layout.addWidget(self.project_label)

        parent.addWidget(card)

    def _build_status_bar(self, parent):
        bar = QFrame()
        bar.setObjectName("card")
        bar.setAttribute(Qt.WA_StyledBackground, True)
        bar.setFixedHeight(40)

        c = ThemeManager.instance().colors()

        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 0, 16, 0)
        row.setSpacing(16)

        self.char_count_label = QLabel("0 characters")
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

        actions.addStretch()
        parent.addLayout(actions)

    def _count_words(self, text):
        return len(text.split()) if text.strip() else 0

    def _on_text_changed(self):
        current = self.editor.toPlainText()
        self._dirty = (current != self._saved_text)
        self.char_count_label.setText(f"{len(current)} characters")
        self.word_count_label.setText(f"{self._count_words(current)} words")
        self.save_btn.setEnabled(self._dirty)
        c = ThemeManager.instance().colors()
        if self._dirty:
            self.status_label.setText("Unsaved changes")
            self.status_label.setStyleSheet(f"color: {c.WARNING};")
        else:
            self.status_label.setText("Saved")
            self.status_label.setStyleSheet(f"color: {c.SUCCESS}; font-weight: bold;")
        self._autosave.mark_dirty("script")

    def _load_project_data(self):
        if not self.project_name:
            return
        project_data = self.manager.load_project(self.project_name)
        if project_data:
            topic = project_data.get("topic", "")
            platform = project_data.get("platform", "")
            language = project_data.get("language", "")
            script_min = project_data.get("script_min", 4500)
            script_max = project_data.get("script_max", 5000)

            c = ThemeManager.instance().colors()
            self.info_topic.setText(f"Topic: {topic}")
            self.info_topic.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
            self.info_platform.setText(f"Platform: {platform}")
            self.info_language.setText(f"Language: {language}")
            self.info_target.setText(f"Target: {script_min}-{script_max} chars")

            self.project_label.setText(f"/ {self.project_name}")
            self.status_badge.setText("Script")

        script_data = self.script_storage.load(self.project_name)
        output = script_data.get("script_output", "")
        if output:
            self.editor.setPlainText(output)
            self._saved_text = output
            self._dirty = False
            self.save_btn.setEnabled(False)
            c = ThemeManager.instance().colors()
            self.status_label.setText("Saved")
            self.status_label.setStyleSheet(f"color: {c.SUCCESS}; font-weight: bold;")
            self.char_count_label.setText(f"{len(output)} characters")
            self.word_count_label.setText(f"{self._count_words(output)} words")

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
            request = ScriptRequest(
                topic=project_data.get("topic", ""),
                platform=project_data.get("platform", "Long Form"),
                video_type=project_data.get("video_type", "Educational"),
                language=project_data.get("language", "English"),
                script_mode=project_data.get("script_mode", "characters"),
                script_min=project_data.get("script_min", 4500),
                script_max=project_data.get("script_max", 5000),
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

        self.script_storage.save(
            project_name=self.project_name,
            script_output=result,
            script_mode=project_data.get("script_mode", "characters"),
            script_min=project_data.get("script_min", 4500),
            script_max=project_data.get("script_max", 5000),
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
        c = ThemeManager.instance().colors()
        self.status_label.setText("Saved")
        self.status_label.setStyleSheet(f"color: {c.SUCCESS}; font-weight: bold;")
        self.char_count_label.setText(f"{len(result)} characters")
        self.word_count_label.setText(f"{self._count_words(result)} words")
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
