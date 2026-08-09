import json
import shutil
import struct
import threading
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QObject, QThread, QTimer, Qt, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QScrollArea,
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
from core.theme import Fonts
from core.transcription_service import WHISPER_MODELS, get_transcription_service
from core.voice_generation_service import (
    DEFAULT_SPEED,
    DEFAULT_VOICE_ID,
    STAGE_MESSAGES,
    VoiceGenerationCancelled,
    get_voice_generation_service,
)
from ..dialogs import _dialog_styles
from ..dialogs.voice_selection import VoiceSelectionDialog
from ..theme_pyside import ThemeManager
from ..widgets import (
    AutosaveIndicator,
    CardTitle,
    IconProvider,
    ModernButton,
    ModernCard,
    MutedLabel,
    ProgressWidget,
    SectionHeader,
    StatusBadge,
)

AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a")

TRANSCRIPTION_STATUSES = [
    (10, "Preparing audio..."),
    (30, "Loading Whisper model..."),
    (55, "Transcribing speech locally..."),
    (75, "Building timestamps..."),
    (90, "Finalizing transcript..."),
]

# ---------------------------------------------------------------------------
# Voice source modes
# ---------------------------------------------------------------------------

VOICE_SOURCE_AI = "ai"
VOICE_SOURCE_IMPORT = "import"
VOICE_SOURCES = (VOICE_SOURCE_AI, VOICE_SOURCE_IMPORT)

#: Allowed playback-speed multipliers for local TTS.
SPEED_OPTIONS = (0.9, 1.0, 1.1, 1.2)

# ---------------------------------------------------------------------------
# Kokoro voice catalogue (display names + descriptions)
#
# The backend service exposes the eight curated profiles used in the
# Recommended section. The remaining installed Kokoro speakers come from the
# kokoro voices file on disk; this catalogue gives each one a friendly display
# name and description. Unknown ids fall back to a derived label.
# ---------------------------------------------------------------------------

KOKORO_VOICE_CATALOG: dict[str, tuple[str, str]] = {
    "af_alloy": ("Alloy", "American female — bright, crisp and modern"),
    "af_aoede": ("Aoede", "American female — lyrical and melodic"),
    "af_heart": ("Heart", "American female — calm, warm documentary tone"),
    "af_jessica": ("Jessica", "American female — energetic and clear"),
    "af_kore": ("Kore", "American female — soft and calm"),
    "af_nicole": ("Nicole", "American female — warm and expressive"),
    "af_nova": ("Nova", "American female — dynamic and confident"),
    "af_river": ("River", "American female — smooth and natural"),
    "af_sarah": ("Sarah", "American female — soft educational narration"),
    "af_sky": ("Sky", "American female — airy and light"),
    "am_adam": ("Adam", "American male — energetic explainer"),
    "am_echo": ("Echo", "American male — resonant and bold"),
    "am_eric": ("Eric", "American male — casual and friendly"),
    "am_fenrir": ("Fenrir", "American male — deep and dramatic"),
    "am_liam": ("Liam", "American male — youthful and bright"),
    "am_michael": ("Michael", "American male — deep educational voice"),
    "am_onyx": ("Onyx", "American male — rich and authoritative"),
    "am_puck": ("Puck", "American male — playful and expressive"),
    "am_santa": ("Santa", "American male — warm and jolly"),
    "af_bella": ("Bella", "American female — warm storytelling"),
    "bf_alice": ("Alice", "British female — polite and refined"),
    "bf_emma": ("Emma", "British female — clear and composed"),
    "bf_isabella": ("Isabella", "British female — friendly conversational"),
    "bf_lily": ("Lily", "British female — gentle and bright"),
    "bm_daniel": ("Daniel", "British male — professional presenter"),
    "bm_fable": ("Fable", "British male — storybook and theatrical"),
    "bm_george": ("George", "British male — confident documentary"),
    "bm_lewis": ("Lewis", "British male — confident documentary voice"),
    "ef_dora": ("Dora", "Spanish female — spirited and clear"),
    "em_alex": ("Alex", "Spanish male — smooth and natural"),
    "em_santa": ("Santa", "Spanish male — warm and friendly"),
    "ff_siwis": ("Siwis", "French female — elegant and refined"),
    "hf_alpha": ("Alpha", "Hindi female — crisp and articulate"),
    "hf_beta": ("Beta", "Hindi female — warm and clear"),
    "hm_omega": ("Omega", "Hindi male — deep and composed"),
    "hm_psi": ("Psi", "Hindi male — bright and expressive"),
    "if_sara": ("Sara", "Italian female — warm and musical"),
    "im_nicola": ("Nicola", "Italian male — confident and smooth"),
    "jf_alpha": ("Alpha", "Japanese female — bright and cheerful"),
    "jf_gongitsune": ("Gongitsune", "Japanese female — tender and soft"),
    "jf_nezumi": ("Nezumi", "Japanese female — lively and playful"),
    "jf_tebukuro": ("Tebukuro", "Japanese female — gentle and calm"),
    "jm_kumo": ("Kumo", "Japanese male — calm and steady"),
    "pf_dora": ("Dora", "Portuguese female — clear and expressive"),
    "pm_alex": ("Alex", "Portuguese male — warm and natural"),
    "pm_santa": ("Santa", "Portuguese male — friendly and relaxed"),
    "zf_xiaobei": ("Xiaobei", "Chinese female — youthful and bright"),
    "zf_xiaoni": ("Xiaoni", "Chinese female — sweet and gentle"),
    "zf_xiaoxiao": ("Xiaoxiao", "Chinese female — playful and lively"),
    "zf_xiaoyi": ("Xiaoyi", "Chinese female — soft and calm"),
    "zm_yunjian": ("Yunjian", "Chinese male — deep and grand"),
    "zm_yunxi": ("Yunxi", "Chinese male — warm and clear"),
    "zm_yunxia": ("Yunxia", "Chinese male — energetic and bright"),
    "zm_yunyang": ("Yunyang", "Chinese male — relaxed and natural"),
}

_LOCALE_NAMES = {
    "a": "American English",
    "b": "British English",
    "e": "Spanish",
    "f": "French",
    "h": "Hindi",
    "i": "Italian",
    "j": "Japanese",
    "p": "Portuguese",
    "z": "Chinese",
}


def _load_installed_voice_ids() -> list[str]:
    """Return the exact list of Kokoro speaker ids installed on disk.

    Reads the kokoro voices file the same way the TTS backend loads it. When
    the file is missing (package not downloaded), an empty list is returned
    and the UI falls back to the full catalogue.
    """
    try:
        voices_file = (
            Path.home() / ".cache" / "kaimi" / "kokoro" / "voices-v1.0.bin"
        )
        if not voices_file.exists():
            return []
        import numpy as np

        data = np.load(str(voices_file))
        return sorted(str(key) for key in data.keys())
    except Exception:
        return []


def _voice_locale(voice_id: str) -> tuple[str, str]:
    """Return (locale, gender) parsed from a Kokoro speaker id (e.g. bf_emma)."""
    prefix = voice_id.split("_")[0] if "_" in voice_id else ""
    locale = _LOCALE_NAMES.get(prefix[:1], "International")
    gender = "Female" if len(prefix) > 1 and prefix[1] == "f" else "Male"
    return locale, gender


def _fallback_voice_entry(voice_id: str) -> tuple[str, str]:
    """Derive a display name and description for an unknown Kokoro id."""
    if "_" in voice_id:
        prefix, _, raw = voice_id.partition("_")
        name = " ".join(word.capitalize() for word in raw.split("_"))
        locale, gender = _voice_locale(voice_id)
        desc = f"{locale} — {gender} voice"
        return name, desc
    return voice_id.capitalize(), "Local Kokoro voice"


def _voice_language(voice_id: str) -> str:
    """Derive a human language label from a Kokoro speaker id (e.g. bf_emma)."""
    locale, gender = _voice_locale(voice_id)
    return f"{locale} \u00b7 {gender}"


def transcribe_audio_locally(audio_path: str) -> tuple[str, list[dict]]:
    """Transcribe an audio file with the local faster-whisper engine.

    Delegates to the shared TranscriptionService so the Whisper model is loaded
    once and reused. Never falls back to a hosted API; a clear error is raised
    when local Whisper is unavailable.

    Returns:
        (transcript_text, segments) where each segment is a dict with
        {"start", "end", "text", "time"} keys.

    Raises:
        RuntimeError: When faster-whisper is missing or transcription fails.
    """
    return get_transcription_service().transcribe(audio_path)


class TranscribeWorker(QObject):
    finished = Signal(str, list)
    error = Signal(str)

    def __init__(self, audio_path):
        super().__init__()
        self.audio_path = audio_path

    def run(self):
        try:
            transcript, segments = transcribe_audio_locally(self.audio_path)
            self.finished.emit(transcript, segments)
        except Exception as e:
            self.error.emit(str(e))


class PreviewWorker(QObject):
    """Generate a voice preview clip on a background thread."""

    finished = Signal(str, object)
    error = Signal(str, str)

    def __init__(self, voice_id, speed):
        super().__init__()
        self.voice_id = voice_id
        self.speed = speed

    def run(self):
        try:
            service = get_voice_generation_service()
            wav_bytes = service.generate_preview(self.voice_id, self.speed)
            self.finished.emit(self.voice_id, wav_bytes)
        except Exception as e:
            self.error.emit(self.voice_id, str(e))


class VoiceGenWorker(QObject):
    """Synthesize the narration for a project on a background thread.

    Reports the real pipeline stage (model init, text prep, synthesis, WAV
    encoding, file save) through :attr:`stage` with measured fractions, and
    supports cooperative cancellation between stages via a shared
    ``threading.Event``.
    """

    #: (stage_key, human_message, fraction) — real pipeline stage updates.
    stage = Signal(str, str, float)
    #: Download progress (message, percent) when the model files are missing.
    progress = Signal(str, int)
    finished = Signal(str)
    #: (failed_stage, human-readable error) — stage named for diagnostics.
    error = Signal(str, str)
    cancelled = Signal()

    def __init__(self, text, voice_id, speed, output_path, cancel_event=None):
        super().__init__()
        self.text = text
        self.voice_id = voice_id
        self.speed = speed
        self.output_path = output_path
        self.cancel_event = cancel_event or threading.Event()
        self._started = time.monotonic()
        self._log = get_logger()
        self._failed_stage = "unknown"

    def run(self):
        service = get_voice_generation_service()
        self._log.info(
            "Voice",
            f"Generation started — voice={self.voice_id}, "
            f"speed={self.speed:.2f}, chars={len(self.text)}, "
            f"output={self.output_path}",
        )
        try:
            self.stage.emit("init", "Initializing Voice Engine", 0.02)
            service.ensure_model_ready(
                self._report_progress, cancel_event=self.cancel_event
            )
            self.stage.emit("ready", "Voice Engine Ready", 0.05)
            service.generate_to_file(
                self.text,
                self.voice_id,
                self.speed,
                self.output_path,
                progress_callback=self._report_stage,
                cancel_event=self.cancel_event,
            )
            self.stage.emit("done", "Voice generated", 1.0)
            self._log.info(
                "Voice",
                f"Generation finished — output={self.output_path}, "
                f"total={time.monotonic() - self._started:.2f}s",
            )
            self.finished.emit(str(self.output_path))
        except VoiceGenerationCancelled:
            self._log.info("Voice", "Generation cancelled by user.")
            self.cancelled.emit()
        except Exception as e:
            self._log.error(
                "Voice",
                f"Generation failed at '{self._failed_stage}' — {e} "
                f"(total={time.monotonic() - self._started:.2f}s)",
            )
            self.error.emit(self._failed_stage, str(e))

    def _report_progress(self, message, percent):
        self.progress.emit(message, percent)

    def _report_stage(self, stage, message, fraction):
        self._failed_stage = stage
        self.stage.emit(stage, message, fraction)


class _ModeOption(QFrame):
    """Clickable source selector used to switch between AI voice / import."""

    clicked = Signal(str)

    def __init__(self, source, title, description, icon_name, parent=None):
        super().__init__(parent)
        self.source = source
        self._selected = False
        self.setObjectName("card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)

        c = ThemeManager.instance().colors()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        self.icon_label = IconProvider.icon_label(icon_name, 26, c.SECONDARY)
        self.icon_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(self.icon_label)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"{Fonts.body_bold(c.TEXT)}")
        self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        text_col.addWidget(self.title_label)

        self.desc_label = QLabel(description)
        self.desc_label.setStyleSheet(f"{Fonts.caption(c.TEXT_SECONDARY)}")
        self.desc_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        text_col.addWidget(self.desc_label)
        layout.addLayout(text_col, 1)

        self.selected_badge = QLabel("Selected")
        self.selected_badge.setStyleSheet(
            f"{Fonts.tiny(c.SUCCESS)} padding: 2px 8px; border-radius: 6px; "
            f"background-color: {c.SUCCESS_LIGHT};"
        )
        self.selected_badge.setVisible(False)
        self.selected_badge.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(self.selected_badge, 0, Qt.AlignTop)

    def mousePressEvent(self, event):
        self.clicked.emit(self.source)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        self._selected = selected
        c = ThemeManager.instance().colors()
        if selected:
            self.setStyleSheet(
                f"QFrame#card {{ border: 1px solid {c.PRIMARY}; "
                f"background-color: {c.CARD}; }}"
            )
            self.selected_badge.setVisible(True)
        else:
            self.setStyleSheet("")
            self.selected_badge.setVisible(False)

    def refresh_theme(self):
        """Re-apply current theme colors to this card's labels and border.

        The mode cards are static chrome built once in ``_build``; without a
        refresh they keep the theme colors they were constructed with after a
        runtime theme switch (Light-theme contrast regression).
        """
        c = ThemeManager.instance().colors()
        self.title_label.setStyleSheet(f"{Fonts.body_bold(c.TEXT)}")
        self.desc_label.setStyleSheet(f"{Fonts.caption(c.TEXT_SECONDARY)}")
        self.selected_badge.setStyleSheet(
            f"{Fonts.tiny(c.SUCCESS)} padding: 2px 8px; border-radius: 6px; "
            f"background-color: {c.SUCCESS_LIGHT};"
        )
        self.set_selected(self._selected)


class TranscriptEditorDialog(QDialog):
    """Modal editor for the project transcript (RC-6.1).

    Hosts the Voice page's single transcript editor widget (temporarily
    reparented into this dialog) so the editing logic, dirty tracking, and
    autosave stay in one place. Save, Copy, and Download TXT reuse the
    page's existing handlers; the widgets return to the page on close.
    """

    def __init__(self, page, parent=None):
        super().__init__(parent)
        self._page = page
        self.setWindowTitle("Transcript")
        self.setModal(True)
        self.setMinimumSize(680, 560)
        self.setStyleSheet(_dialog_styles())
        self._build()
        self.finished.connect(self._restore_widgets)

    def _build(self):
        c = ThemeManager.instance().colors()
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Transcript")
        title.setStyleSheet(f"{Fonts.css(20, '600', c.TEXT)}")
        layout.addWidget(title)

        subtitle = QLabel(
            "Edit the narration transcript. Changes are saved to this project."
        )
        subtitle.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        layout.addWidget(subtitle)

        page = self._page
        # The shared editor chrome is created hidden on the page (and re-hidden
        # by _restore_widgets on close). An explicitly hidden widget stays
        # hidden even after setParent() + layout.addWidget(), so the dialog
        # must re-show every hosted widget or it opens with an invisible,
        # 'completely blank' editor (RC-6 blank-transcript-viewer regression).
        page.transcript_box.setParent(self)
        page.transcript_box.setVisible(True)
        layout.addWidget(page.transcript_box, 1)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)
        page.status_label.setParent(self)
        page.status_label.setVisible(True)
        meta_row.addWidget(page.status_label)
        page.timestamps_label.setParent(self)
        page.timestamps_label.setVisible(True)
        meta_row.addWidget(page.timestamps_label)
        page._autosave_indicator.setParent(self)
        page._autosave_indicator.setVisible(True)
        meta_row.addWidget(page._autosave_indicator)
        meta_row.addStretch()
        layout.addLayout(meta_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        page.save_btn.setParent(self)
        page.save_btn.setVisible(True)
        btn_row.addWidget(page.save_btn)
        page.download_btn.setParent(self)
        page.download_btn.setVisible(True)
        btn_row.addWidget(page.download_btn)
        copy_btn = ModernButton("Copy", primary=False)
        copy_btn.clicked.connect(self._copy_transcript)
        btn_row.addWidget(copy_btn)
        btn_row.addStretch()
        close_btn = ModernButton("Close", primary=True)
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _copy_transcript(self):
        QApplication.clipboard().setText(self._page.transcript_box.toPlainText())
        NotificationService.get().success("Transcript copied.")

    def _restore_widgets(self, _result=None):
        """Return the shared editor chrome to the page after the dialog closes."""
        page = self._page
        for widget in (
            page.transcript_box,
            page.status_label,
            page.timestamps_label,
            page._autosave_indicator,
            page.save_btn,
            page.download_btn,
        ):
            widget.setParent(page)
            widget.setVisible(False)


class VoicePage(QWidget):
    def __init__(self):
        super().__init__()
        self.manager = ProjectManager()
        self._pipeline = get_pipeline_service()
        self._script_storage = ScriptStorage()
        self._voice_service = get_voice_generation_service()
        self.project_name = None
        self._audio_path = None
        self._transcript_text = ""
        self._segments = []
        #: Human-readable reason when the last transcription attempt failed;
        #: None while idle / generating / after success (RC-6 status model).
        self._transcript_error = None
        self._saved_text = ""
        self._dirty = False
        self._transcribing = False
        self._auto_advance = False
        self._generating = False
        self._worker_thread = None
        self._worker = None
        self._transcription_timer = None
        self._progress_index = 0
        self._history = HistoryManager()
        self._autosave = get_autosave_manager()
        self._autosave.register("voice", self._autosave_save)
        self._autosave_indicator = AutosaveIndicator()
        self._autosave.on_status_change(self._autosave_indicator.set_status)
        self._voice_source = VOICE_SOURCE_AI
        self._selected_voice_id = DEFAULT_VOICE_ID
        self._voice_dialog = None
        self._transcript_dialog = None
        self._preview_cache = {}
        self._preview_thread = None
        self._preview_worker = None
        self._gen_thread = None
        self._gen_worker = None
        self._gen_cancel_event = None
        self._gen_started_at = None
        self._synthesis_started_at = None
        self._reassurance_shown = False
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._update_elapsed_display)
        self._media_player = None
        self._audio_output = None
        self._media_buffer = None
        self._narration_duration_ms = 0
        #: True while the media player is bound to the narration file. When
        #: False a preview clip is the active source, so Play must switch to
        #: the narration file instead of toggling the preview.
        self._playing_narration = False
        self._installed_voice_ids = _load_installed_voice_ids()
        self._recommended_profiles = self._voice_service.get_available_voices()
        ThemeManager.instance().on_change(lambda _: self._on_theme_changed())
        self._build()

    def _on_theme_changed(self):
        self._refresh_theme_static()
        if self.project_name:
            self._load_project_data()

    def _refresh_theme_static(self):
        """Re-apply theme tokens to chrome built once in ``_build``.

        Static labels (mode cards, voice summary, project info) keep the
        colors they were constructed with unless restyled here; without this
        they render as near-white Dark-theme text on Light backgrounds after
        a runtime theme switch.
        """
        c = ThemeManager.instance().colors()
        for option in self._mode_options.values():
            option.refresh_theme()
        self.selected_voice_name_label.setStyleSheet(f"{Fonts.body_bold(c.TEXT)}")
        self.selected_voice_desc_label.setStyleSheet(f"{Fonts.caption(c.TEXT_SECONDARY)}")
        self.selected_voice_lang_label.setStyleSheet(f"{Fonts.tiny(c.TEXT_MUTED)}")
        self.imported_title_label.setStyleSheet(f"{Fonts.tiny(c.TEXT_MUTED)}")
        self.imported_file_label.setStyleSheet(f"{Fonts.body_bold(c.TEXT)}")
        self.imported_meta_label.setStyleSheet(f"{Fonts.caption(c.TEXT_SECONDARY)}")
        self.ai_voice_icon.setPixmap(IconProvider.pixmap("voice", 30, c.SECONDARY))
        self.import_audio_icon.setPixmap(
            IconProvider.pixmap("document", 30, c.SECONDARY)
        )
        self.info_project.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        self.info_topic.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        self.info_language.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        self.status_badge.refresh_theme()
        self.summary_check_label.setPixmap(
            IconProvider.pixmap("check_circle", 18, c.SUCCESS)
        )
        self.summary_title_label.setStyleSheet(f"{Fonts.body_bold(c.SUCCESS)}")
        for label in (
            self.summary_voice_label,
            self.narration_duration_label,
            self.narration_size_label,
            self.summary_generated_label,
        ):
            label.setStyleSheet(f"{Fonts.caption(c.TEXT)}")
        for label in self._group_labels:
            label.setStyleSheet(f"{Fonts.caption_bold(c.TEXT_SECONDARY)}")

    def cleanup(self):
        """Stop background workers and wait for their threads to finish.

        Workers cannot be interrupted mid-operation (transcription / TTS), so
        the GUI thread waits while processing events. Deleting a running
        QThread would abort the application on exit (Sprint 3.4B / C3).
        """
        self._stop_progress_animation()
        self._elapsed_timer.stop()
        if self._gen_cancel_event is not None:
            self._gen_cancel_event.set()
        if self._media_player:
            self._media_player.stop()
        for thread in (self._worker_thread, self._preview_thread, self._gen_thread):
            if thread and thread.isRunning():
                thread.quit()
        for thread in (self._worker_thread, self._preview_thread, self._gen_thread):
            if thread and thread.isRunning():
                self._wait_for_thread(thread)
        for worker in (self._worker, self._preview_worker, self._gen_worker):
            if worker:
                worker.deleteLater()
        self._worker = None
        self._preview_worker = None
        self._gen_worker = None
        if self._worker_thread:
            self._worker_thread.deleteLater()
            self._worker_thread = None
        if self._preview_thread:
            self._preview_thread.deleteLater()
            self._preview_thread = None
        if self._gen_thread:
            self._gen_thread.deleteLater()
            self._gen_thread = None

    @staticmethod
    def _wait_for_thread(thread: QThread) -> None:
        """Block the GUI thread until a worker thread has fully finished.

        Events are intentionally not processed while waiting: processing them
        during shutdown could deliver completion slots that start follow-up
        work on new threads (e.g. the auto-advance chain after voice
        generation), which would then be destroyed while still running.
        """
        thread.wait()

    def set_project(self, name):
        if name != self.project_name:
            # Persist pending edits to the OLD project before its autosave
            # callback could fire after we switch (Sprint 3.4B / C1, C2).
            self._autosave.flush_all()
            self._dirty = False
            # A failure from another project must not leak into this one.
            self._transcript_error = None
        self.project_name = name
        self._load_project_data()

    def _build(self):
        # The page scrolls as a whole (same pattern as Settings / Dashboard /
        # Projects). Without a scroll container the tall Narration card was
        # compressed below its minimum height by the window and its bottom
        # sections (Playback / Export / Transcript) were painted outside the
        # visible area — the RC-6.2 clipping regression.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        outer.addWidget(self._scroll)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self._build_project_header(layout)

        self._build_mode_selector(layout)

        self._create_transcript_widgets()

        self._build_narration_section(layout)

        self._build_upload_section(layout)

        self._build_action_bar(layout)

        layout.addStretch()
        self._scroll.setWidget(content)

        self._set_mode_ui(self._voice_source)
        self._update_voice_summary()

    def _build_project_header(self, parent):
        card = ModernCard()
        card.content_layout.setSpacing(8)

        c = ThemeManager.instance().colors()

        row = QHBoxLayout()
        row.setSpacing(16)

        name_label = CardTitle("Voice / Transcript")
        row.addWidget(name_label)

        self.status_badge = StatusBadge("Voice")
        row.addWidget(self.status_badge)

        row.addStretch()
        card.content_layout.addLayout(row)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(24)
        self.info_project = QLabel("")
        self.info_project.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        self.info_topic = QLabel("")
        self.info_topic.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        self.info_language = QLabel("")
        self.info_language.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        meta_row.addWidget(self.info_project)
        meta_row.addWidget(self.info_topic)
        meta_row.addWidget(self.info_language)
        meta_row.addStretch()
        card.content_layout.addLayout(meta_row)

        self.project_label = MutedLabel("")
        card.content_layout.addWidget(self.project_label)

        parent.addWidget(card)

    def _build_mode_selector(self, parent):
        card = ModernCard()
        card.content_layout.setSpacing(8)
        card.content_layout.addWidget(SectionHeader("Voice Source"))

        row = QHBoxLayout()
        row.setSpacing(12)
        self._mode_options = {}

        specs = [
            (VOICE_SOURCE_AI, "Built-in AI Voice",
             "Generate narration locally with Kokoro voices", "voice"),
            (VOICE_SOURCE_IMPORT, "Import Existing Audio",
             "Transcribe an MP3, WAV, or M4A file", "folder_open"),
        ]
        for source, title, desc, icon in specs:
            option = _ModeOption(source, title, desc, icon)
            option.clicked.connect(self._on_mode_selected)
            self._mode_options[source] = option
            row.addWidget(option, 1)

        card.content_layout.addLayout(row)
        parent.addWidget(card)
        self._mode_card = card

    def _build_narration_section(self, parent):
        """One unified narration module (RC-6.2 layout).

        Holds two mutually exclusive identity blocks — the selected AI voice
        (name, description, language) and the imported audio (filename,
        duration, size) — followed by the AI-only speed/generation controls,
        the shared progress bar and generated summary, and the grouped
        Playback / Export / Transcript controls. The Transcript group stays
        visible in every state so the workflow dependency never disappears.
        """
        c = ThemeManager.instance().colors()
        card = ModernCard()
        card.content_layout.setSpacing(14)
        self._group_labels = []

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)
        header_row.addWidget(SectionHeader("Narration"))
        header_row.addStretch()
        self.narration_status_badge = StatusBadge("Ready")
        header_row.addWidget(self.narration_status_badge, 0, Qt.AlignVCenter)
        card.content_layout.addLayout(header_row)

        # --- AI voice identity --------------------------------------------------
        self.ai_identity_container = QWidget()
        ai_row = QHBoxLayout(self.ai_identity_container)
        ai_row.setContentsMargins(0, 0, 0, 0)
        ai_row.setSpacing(14)

        self.ai_voice_icon = IconProvider.icon_label("voice", 30, c.SECONDARY)
        ai_row.addWidget(self.ai_voice_icon, 0, Qt.AlignTop)

        ai_text_col = QVBoxLayout()
        ai_text_col.setSpacing(4)
        self.selected_voice_name_label = QLabel("")
        self.selected_voice_name_label.setStyleSheet(f"{Fonts.body_bold(c.TEXT)}")
        ai_text_col.addWidget(self.selected_voice_name_label)

        self.selected_voice_desc_label = QLabel("")
        self.selected_voice_desc_label.setStyleSheet(f"{Fonts.caption(c.TEXT_SECONDARY)}")
        self.selected_voice_desc_label.setWordWrap(True)
        ai_text_col.addWidget(self.selected_voice_desc_label)

        self.selected_voice_lang_label = QLabel("")
        self.selected_voice_lang_label.setStyleSheet(f"{Fonts.tiny(c.TEXT_MUTED)}")
        ai_text_col.addWidget(self.selected_voice_lang_label)
        ai_row.addLayout(ai_text_col, 1)

        self.preview_btn = ModernButton("Preview", primary=False)
        self.preview_btn.clicked.connect(self._preview_selected_voice)
        ai_row.addWidget(self.preview_btn, 0, Qt.AlignTop)

        self.change_voice_btn = ModernButton("Change Voice", primary=False)
        self.change_voice_btn.clicked.connect(self._open_voice_dialog)
        ai_row.addWidget(self.change_voice_btn, 0, Qt.AlignTop)

        card.content_layout.addWidget(self.ai_identity_container)

        # --- Imported audio identity ----------------------------------------------
        self.import_identity_container = QWidget()
        import_row = QHBoxLayout(self.import_identity_container)
        import_row.setContentsMargins(0, 0, 0, 0)
        import_row.setSpacing(14)

        self.import_audio_icon = IconProvider.icon_label("document", 30, c.SECONDARY)
        import_row.addWidget(self.import_audio_icon, 0, Qt.AlignTop)

        import_text_col = QVBoxLayout()
        import_text_col.setSpacing(4)
        self.imported_title_label = QLabel("Imported Audio")
        self.imported_title_label.setStyleSheet(f"{Fonts.tiny(c.TEXT_MUTED)}")
        import_text_col.addWidget(self.imported_title_label)

        self.imported_file_label = QLabel("")
        self.imported_file_label.setStyleSheet(f"{Fonts.body_bold(c.TEXT)}")
        self.imported_file_label.setWordWrap(True)
        import_text_col.addWidget(self.imported_file_label)

        self.imported_meta_label = QLabel("")
        self.imported_meta_label.setStyleSheet(f"{Fonts.caption(c.TEXT_SECONDARY)}")
        import_text_col.addWidget(self.imported_meta_label)
        import_row.addLayout(import_text_col, 1)

        self.import_preview_btn = ModernButton("Preview", primary=False)
        self.import_preview_btn.clicked.connect(self._play_narration)
        import_row.addWidget(self.import_preview_btn, 0, Qt.AlignTop)

        self.replace_audio_btn = ModernButton("Replace Audio", primary=False)
        self.replace_audio_btn.clicked.connect(self.choose_audio)
        import_row.addWidget(self.replace_audio_btn, 0, Qt.AlignTop)

        card.content_layout.addWidget(self.import_identity_container)

        # --- AI-only: voice speed ---------------------------------------------------
        self.ai_speed_container = QWidget()
        meta_row = QHBoxLayout(self.ai_speed_container)
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(8)
        meta_row.addWidget(MutedLabel("Voice speed:"))
        self.speed_combo = QComboBox()
        for speed in SPEED_OPTIONS:
            self.speed_combo.addItem(f"{speed:.1f}\u00d7", float(speed))
        idx = self.speed_combo.findData(float(DEFAULT_SPEED))
        self.speed_combo.setCurrentIndex(max(idx, 0))
        self.speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        meta_row.addWidget(self.speed_combo)
        meta_row.addStretch()
        card.content_layout.addWidget(self.ai_speed_container)

        # --- AI-only: generation -------------------------------------------------------
        self.ai_generation_container = QWidget()
        gen_row = QHBoxLayout(self.ai_generation_container)
        gen_row.setContentsMargins(0, 0, 0, 0)
        gen_row.setSpacing(8)
        self.generate_btn = ModernButton("Generate Voice", primary=True)
        self.generate_btn.clicked.connect(self.generate_voice)
        gen_row.addWidget(self.generate_btn)
        self.tts_status_label = MutedLabel("")
        gen_row.addWidget(self.tts_status_label)
        self.tts_setup_btn = ModernButton("TTS Setup", primary=False)
        self.tts_setup_btn.clicked.connect(self.show_tts_setup)
        gen_row.addWidget(self.tts_setup_btn)
        gen_row.addStretch()
        card.content_layout.addWidget(self.ai_generation_container)

        # --- Generation progress + cancel/retry -----------------------------------
        self.progress_widget = ProgressWidget()
        self.progress_widget.setVisible(False)
        card.content_layout.addWidget(self.progress_widget)

        self.gen_actions = QWidget()
        gen_actions_row = QHBoxLayout(self.gen_actions)
        gen_actions_row.setContentsMargins(0, 0, 0, 0)
        gen_actions_row.setSpacing(8)
        self.cancel_gen_btn = ModernButton("Cancel Generation", primary=False)
        self.cancel_gen_btn.clicked.connect(self._cancel_generation)
        gen_actions_row.addWidget(self.cancel_gen_btn)
        self.retry_gen_btn = ModernButton("Retry", primary=True)
        self.retry_gen_btn.clicked.connect(self._retry_voice)
        gen_actions_row.addWidget(self.retry_gen_btn)
        gen_actions_row.addStretch()
        self.gen_actions.setVisible(False)
        card.content_layout.addWidget(self.gen_actions)

        # --- Generated narration summary (Part 7) ---------------------------------
        self.narration_summary = QFrame()
        self.narration_summary.setObjectName("card")
        self.narration_summary.setAttribute(Qt.WA_StyledBackground, True)
        summary_layout = QVBoxLayout(self.narration_summary)
        summary_layout.setContentsMargins(14, 12, 14, 12)
        summary_layout.setSpacing(6)

        summary_title_row = QHBoxLayout()
        summary_title_row.setSpacing(8)
        self.summary_check_label = IconProvider.icon_label("check_circle", 18, c.SUCCESS)
        summary_title_row.addWidget(self.summary_check_label)
        self.summary_title_label = QLabel("Voice Generated")
        self.summary_title_label.setStyleSheet(f"{Fonts.body_bold(c.SUCCESS)}")
        summary_title_row.addWidget(self.summary_title_label)
        summary_title_row.addStretch()
        summary_layout.addLayout(summary_title_row)

        summary_body = QVBoxLayout()
        summary_body.setContentsMargins(26, 0, 0, 0)
        summary_body.setSpacing(4)
        self.summary_voice_label = QLabel("Voice: \u2014")
        self.summary_voice_label.setStyleSheet(f"{Fonts.caption(c.TEXT)}")
        summary_body.addWidget(self.summary_voice_label)
        self.narration_duration_label = QLabel("Duration: \u2014")
        self.narration_duration_label.setStyleSheet(f"{Fonts.caption(c.TEXT)}")
        summary_body.addWidget(self.narration_duration_label)
        self.narration_size_label = QLabel("File size: \u2014")
        self.narration_size_label.setStyleSheet(f"{Fonts.caption(c.TEXT)}")
        summary_body.addWidget(self.narration_size_label)
        self.summary_generated_label = QLabel("Generated: \u2014")
        self.summary_generated_label.setStyleSheet(f"{Fonts.caption(c.TEXT)}")
        summary_body.addWidget(self.summary_generated_label)
        summary_layout.addLayout(summary_body)
        card.content_layout.addWidget(self.narration_summary)

        # --- Playback controls (Part 6) --------------------------------------------
        self.playback_container = QWidget()
        play_col = QVBoxLayout(self.playback_container)
        play_col.setContentsMargins(0, 0, 0, 0)
        play_col.setSpacing(8)
        play_col.addWidget(self._group_label("Playback"))

        play_row = QHBoxLayout()
        play_row.setSpacing(8)
        self.play_btn = ModernButton("\u25b6 Play", primary=True)
        self.play_btn.setFixedWidth(110)
        self.play_btn.clicked.connect(self._play_narration)
        play_row.addWidget(self.play_btn)

        self.pause_btn = ModernButton("\u23f8 Pause", primary=False)
        self.pause_btn.setFixedWidth(110)
        self.pause_btn.clicked.connect(self._pause_narration)
        play_row.addWidget(self.pause_btn)

        self.stop_btn = ModernButton("\u23f9 Stop", primary=False)
        self.stop_btn.setFixedWidth(100)
        self.stop_btn.clicked.connect(self._stop_audio)
        play_row.addWidget(self.stop_btn)
        play_row.addStretch()
        play_col.addLayout(play_row)
        card.content_layout.addWidget(self.playback_container)

        # --- Export controls (Part 6) ------------------------------------------------
        self.export_container = QWidget()
        export_col = QVBoxLayout(self.export_container)
        export_col.setContentsMargins(0, 0, 0, 0)
        export_col.setSpacing(8)
        export_col.addWidget(self._group_label("Export"))

        export_row = QHBoxLayout()
        export_row.setSpacing(8)
        self.download_audio_btn = ModernButton("\u2b07 Download", primary=False)
        self.download_audio_btn.clicked.connect(self._download_audio)
        export_row.addWidget(self.download_audio_btn)

        self.regenerate_btn = ModernButton("\U0001f501 Regenerate", primary=False)
        self.regenerate_btn.clicked.connect(self._regenerate_voice)
        export_row.addWidget(self.regenerate_btn)
        export_row.addStretch()
        export_col.addLayout(export_row)
        card.content_layout.addWidget(self.export_container)

        # --- Transcript controls (always visible) ----------------------------------------
        self.transcript_container = QWidget()
        transcript_col = QVBoxLayout(self.transcript_container)
        transcript_col.setContentsMargins(0, 0, 0, 0)
        transcript_col.setSpacing(8)

        transcript_header = QHBoxLayout()
        transcript_header.setSpacing(8)
        transcript_header.addWidget(self._group_label("Transcript"))
        self.transcript_summary_label = MutedLabel("Status: Not Generated")
        transcript_header.addWidget(self.transcript_summary_label)
        transcript_header.addStretch()
        transcript_col.addLayout(transcript_header)

        transcript_row = QHBoxLayout()
        transcript_row.setSpacing(8)
        self.generate_transcript_btn = ModernButton("Generate Transcript", primary=False)
        self.generate_transcript_btn.clicked.connect(self.transcribe_audio)
        transcript_row.addWidget(self.generate_transcript_btn)

        self.view_transcript_btn = ModernButton("View Transcript", primary=False)
        self.view_transcript_btn.clicked.connect(self._open_transcript_editor)
        transcript_row.addWidget(self.view_transcript_btn)
        transcript_row.addStretch()
        transcript_col.addLayout(transcript_row)
        card.content_layout.addWidget(self.transcript_container)

        #: Shared transcription trigger. The old Upload-Audio button was removed
        #: (RC-6.2: no duplicate Generate Transcript), but the ``transcribe_btn``
        #: name is kept as an alias so the transcription pipeline and existing
        #: tests keep working against the single Narration-card button.
        self.transcribe_btn = self.generate_transcript_btn

        self.narration_empty_label = MutedLabel(
            "No narration generated yet. Generate a voice to enable playback."
        )
        card.content_layout.addWidget(self.narration_empty_label)

        parent.addWidget(card)
        self._ai_card = card
        self._refresh_tts_status()
        self._refresh_narration_ui()

    def _build_upload_section(self, parent):
        """Import-mode card: choose and configure the audio file.

        Only handles importing/configuring the audio (Choose Audio File,
        selected filename, Whisper model, Whisper Setup). The transcription
        trigger lives in the Narration card's Transcript group (RC-6.2) so
        the two sections no longer duplicate the Generate Transcript action.
        """
        card = ModernCard()
        card.content_layout.setSpacing(8)

        card.content_layout.addWidget(SectionHeader("Upload Audio"))

        self.file_label = MutedLabel("No file selected. Choose an MP3, WAV, or M4A file.")
        card.content_layout.addWidget(self.file_label)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(12)

        self.upload_btn = ModernButton("Choose Audio File", primary=True)
        self.upload_btn.clicked.connect(self.choose_audio)
        btn_row.addWidget(self.upload_btn)

        btn_row.addStretch()
        card.content_layout.addLayout(btn_row)

        model_row = QHBoxLayout()
        model_row.setContentsMargins(0, 0, 0, 0)
        model_row.setSpacing(8)

        model_label = MutedLabel("Whisper model:")
        model_row.addWidget(model_label)

        self.model_combo = QComboBox()
        self.model_combo.addItems(list(WHISPER_MODELS))
        self.model_combo.setCurrentText(get_transcription_service().get_configured_model())
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        model_row.addWidget(self.model_combo)

        self.setup_btn = ModernButton("Whisper Setup", primary=False)
        self.setup_btn.clicked.connect(self.show_whisper_setup)
        model_row.addWidget(self.setup_btn)

        model_row.addStretch()
        card.content_layout.addLayout(model_row)

        parent.addWidget(card)
        self._upload_card = card

    def _create_transcript_widgets(self):
        """Create the transcript editor chrome, kept hidden on the page.

        The editor and its status / save / copy chrome live inside the
        transcript dialog while it is open; the widgets stay owned by this
        page so dirty tracking, autosave, and the transcription pipeline
        keep a single source of truth (RC-6.1: the editor no longer
        permanently occupies the Voice page).
        """
        self.transcript_box = QPlainTextEdit(self)
        self.transcript_box.setPlaceholderText(
            "No transcript yet. Generate a transcript first."
        )
        self.transcript_box.setMinimumHeight(260)
        self.transcript_box.textChanged.connect(self._on_text_edit)
        self.transcript_box.setVisible(False)

        self.status_label = MutedLabel("")
        self.status_label.setParent(self)
        self.status_label.setVisible(False)

        self.timestamps_label = MutedLabel("")
        self.timestamps_label.setParent(self)
        self.timestamps_label.setVisible(False)

        self.save_btn = ModernButton("Save Transcript", primary=True)
        self.save_btn.clicked.connect(self.save_transcript)
        self.save_btn.setParent(self)
        self.save_btn.setEnabled(False)
        self.save_btn.setVisible(False)

        self.download_btn = ModernButton("Download TXT", primary=False)
        self.download_btn.clicked.connect(self.download_transcript)
        self.download_btn.setParent(self)
        self.download_btn.setEnabled(False)
        self.download_btn.setVisible(False)

        self._autosave_indicator.setParent(self)
        self._autosave_indicator.setVisible(False)

    def _build_action_bar(self, parent):
        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(12)

        bar.addStretch()

        self.next_btn = ModernButton("Next \u2192 Image Prompts", primary=True)
        self.next_btn.clicked.connect(self.go_to_image_prompts)
        self.next_btn.setEnabled(False)
        bar.addWidget(self.next_btn)

        parent.addLayout(bar)

    def _on_text_edit(self):
        current = self.transcript_box.toPlainText()
        self._dirty = (current != self._saved_text)
        self.save_btn.setEnabled(self._dirty)
        c = ThemeManager.instance().colors()
        if self._dirty:
            self.status_label.setText("Unsaved changes")
            self.status_label.setStyleSheet(f"color: {c.WARNING};")
        else:
            self.status_label.setText("Saved")
            self.status_label.setStyleSheet(f"color: {c.SUCCESS}; font-weight: bold;")
        self._autosave.mark_dirty("voice")

    def _update_status_clean(self):
        self._dirty = False
        self.save_btn.setEnabled(False)
        c = ThemeManager.instance().colors()
        self.status_label.setText("Saved")
        self.status_label.setStyleSheet(f"color: {c.SUCCESS}; font-weight: bold;")

    # ------------------------------------------------------------------
    # Mode switching
    # ------------------------------------------------------------------

    def _on_mode_selected(self, source):
        if source == self._voice_source:
            return
        self._set_mode_ui(source)
        self._persist_voice_prefs()

    def _set_mode_ui(self, source):
        self._voice_source = source if source in VOICE_SOURCES else VOICE_SOURCE_AI
        for key, option in self._mode_options.items():
            option.set_selected(key == self._voice_source)
        ai_visible = self._voice_source == VOICE_SOURCE_AI
        # AI and Import are true UI states: the selected AI voice, speed and
        # TTS controls never leak into the imported state, and the imported
        # audio identity never shows under an AI voice (RC-6.2). Visibility is
        # applied to the group containers AND their direct controls so both
        # the rendered layout and isHidden()/isVisible() reflect the state
        # consistently (Qt only reports isHidden() true for a never-shown
        # widget when it was itself explicitly hidden).
        self.ai_identity_container.setVisible(ai_visible)
        self.selected_voice_name_label.setVisible(ai_visible)
        self.selected_voice_desc_label.setVisible(ai_visible)
        self.selected_voice_lang_label.setVisible(ai_visible)
        self.preview_btn.setVisible(ai_visible)
        self.change_voice_btn.setVisible(ai_visible)
        self.ai_speed_container.setVisible(ai_visible)
        self.ai_generation_container.setVisible(ai_visible)
        self.generate_btn.setVisible(ai_visible)
        self.tts_status_label.setVisible(ai_visible)
        self.tts_setup_btn.setVisible(ai_visible)
        self.import_identity_container.setVisible(not ai_visible)
        self.imported_file_label.setVisible(not ai_visible)
        self.imported_meta_label.setVisible(not ai_visible)
        self.import_preview_btn.setVisible(not ai_visible)
        self.replace_audio_btn.setVisible(not ai_visible)
        self._upload_card.setVisible(not ai_visible)
        self._refresh_import_ui()
        self._refresh_narration_ui()

    def _refresh_import_ui(self):
        if self._transcribing:
            self.transcribe_btn.setEnabled(False)
            return
        if self._audio_path:
            self.file_label.setText(f"Selected: {Path(self._audio_path).name}")
            self.transcribe_btn.setEnabled(True)
        else:
            self.file_label.setText("No file selected. Choose an MP3, WAV, or M4A file.")
            self.transcribe_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Voice selection (summary + dialog)
    # ------------------------------------------------------------------

    def _current_speed(self):
        if self.speed_combo is None:
            return float(DEFAULT_SPEED)
        data = self.speed_combo.itemData(self.speed_combo.currentIndex())
        return float(data) if data is not None else float(DEFAULT_SPEED)

    def _set_speed(self, speed):
        if self.speed_combo is None:
            return
        idx = self.speed_combo.findData(float(speed))
        self.speed_combo.setCurrentIndex(max(idx, 0))

    def _all_voice_ids(self):
        if self._installed_voice_ids:
            return self._installed_voice_ids
        return list(KOKORO_VOICE_CATALOG.keys())

    def _voice_catalog_entry(self, voice_id):
        entry = KOKORO_VOICE_CATALOG.get(voice_id)
        if entry:
            return entry
        return _fallback_voice_entry(voice_id)

    def _remaining_voices(self):
        recommended_ids = {p.id for p in self._recommended_profiles}
        result = []
        for voice_id in self._all_voice_ids():
            if voice_id in recommended_ids:
                continue
            name, description = self._voice_catalog_entry(voice_id)
            result.append((voice_id, name, description))
        return result

    def _display_name(self, voice_id):
        for profile in self._recommended_profiles:
            if profile.id == voice_id:
                return profile.name
        return self._voice_catalog_entry(voice_id)[0]

    def _open_voice_dialog(self):
        """Open the modal voice picker, pre-selecting the current voice."""
        recommended = [
            (p.id, p.name, p.description, _voice_language(p.id))
            for p in self._recommended_profiles
        ]
        remaining = [
            (voice_id, name, description, _voice_language(voice_id))
            for voice_id, name, description in self._remaining_voices()
        ]
        dialog = VoiceSelectionDialog(
            current_voice_id=self._selected_voice_id,
            recommended=recommended,
            remaining=remaining,
            parent=self,
        )
        dialog.preview_requested.connect(self._preview_voice)
        dialog.voice_selected.connect(self._on_dialog_voice_selected)
        self._voice_dialog = dialog
        dialog.exec()
        self._voice_dialog = None

    def _on_dialog_voice_selected(self, voice_id):
        self._select_voice(voice_id)

    def _open_transcript_editor(self):
        """Open the modal transcript editor (RC-6.1 Part 3)."""
        if not self._transcript_text:
            NotificationService.get().info(
                "No transcript yet. Generate a transcript first."
            )
            return
        self._transcript_dialog = TranscriptEditorDialog(self, parent=self)
        self._transcript_dialog.exec()
        self._transcript_dialog = None

    def _select_voice(self, voice_id):
        self._selected_voice_id = voice_id
        self._update_voice_summary()
        self._persist_voice_prefs()

    def _update_voice_summary(self):
        voice_id = self._selected_voice_id
        profile = self._voice_service.get_voice_by_id(voice_id)
        if profile is not None:
            name = profile.name
            description = profile.description
        else:
            name = self._display_name(voice_id)
            description = self._voice_catalog_entry(voice_id)[1]
        self.selected_voice_name_label.setText(name)
        self.selected_voice_desc_label.setText(description)
        self.selected_voice_lang_label.setText(_voice_language(voice_id))

    def _on_speed_changed(self, _index):
        self._persist_voice_prefs()

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _preview_selected_voice(self):
        self._preview_voice(self._selected_voice_id)

    def _preview_voice(self, voice_id):
        speed = self._current_speed()
        key = (voice_id, speed)
        if key in self._preview_cache:
            self._play_wav_bytes(self._preview_cache[key])
            return
        if self._preview_thread and self._preview_thread.isRunning():
            NotificationService.get().info(
                "A voice preview is already being generated. Please wait."
            )
            return

        self._set_preview_loading(voice_id, True)
        self._preview_thread = QThread()
        self._preview_worker = PreviewWorker(voice_id, speed)
        self._preview_worker.moveToThread(self._preview_thread)

        self._preview_thread.started.connect(self._preview_worker.run)
        self._preview_worker.finished.connect(self._on_preview_ready)
        self._preview_worker.error.connect(self._on_preview_error)
        self._preview_worker.finished.connect(self._preview_thread.quit)
        self._preview_worker.error.connect(self._preview_thread.quit)
        self._preview_thread.finished.connect(self._cleanup_preview_thread)

        self._preview_thread.start()

    def _on_preview_ready(self, voice_id, wav_bytes):
        self._preview_cache[(voice_id, self._current_speed())] = wav_bytes
        self._set_preview_loading(voice_id, False)
        self._play_wav_bytes(wav_bytes)

    def _on_preview_error(self, voice_id, message):
        self._set_preview_loading(voice_id, False)
        NotificationService.get().error(f"Preview failed: {message}")

    def _set_preview_loading(self, voice_id, loading: bool):
        dialog = self._voice_dialog
        if dialog is not None:
            dialog.set_preview_loading(voice_id, loading)

    def _cleanup_preview_thread(self):
        if self._preview_worker:
            self._preview_worker.deleteLater()
            self._preview_worker = None
        if self._preview_thread:
            self._preview_thread.deleteLater()
            self._preview_thread = None

    # ------------------------------------------------------------------
    # Audio playback
    # ------------------------------------------------------------------

    def _ensure_media_player(self):
        if self._media_player is None:
            self._media_player = QMediaPlayer(self)
            self._audio_output = QAudioOutput(self)
            self._media_player.setAudioOutput(self._audio_output)
            self._media_player.playbackStateChanged.connect(
                self._on_playback_state_changed
            )
            self._media_player.durationChanged.connect(self._on_duration_changed)

    def _play_wav_bytes(self, data: bytes):
        """Play an in-memory preview clip (short built-in sample).

        Starting a preview stops narration playback first so that only one
        audio source ever plays at a time.
        """
        self._ensure_media_player()
        if self._playing_narration:
            self._media_player.stop()
        self._media_player.setSource(QUrl())
        if self._media_buffer is not None:
            self._media_buffer.close()
            self._media_buffer.deleteLater()
            self._media_buffer = None
        self._media_buffer = QBuffer(self)
        self._media_buffer.setData(data)
        self._media_buffer.open(QIODevice.ReadOnly)
        self._media_player.setSourceDevice(self._media_buffer)
        self._playing_narration = False
        self._media_player.play()

    def _play_audio_file(self, path):
        """Play the generated or imported narration file directly."""
        self._ensure_media_player()
        if self._media_buffer is not None:
            self._media_buffer.close()
            self._media_buffer.deleteLater()
            self._media_buffer = None
        self._media_player.setSource(QUrl.fromLocalFile(str(path)))
        self._playing_narration = True
        self._media_player.play()

    def _play_narration(self):
        """Start or resume narration playback (never the preview clip)."""
        if not self._audio_path or not Path(self._audio_path).exists():
            NotificationService.get().warning("No narration audio available.")
            return
        if self._media_player is None:
            self._play_audio_file(self._audio_path)
            return
        state = self._media_player.playbackState()
        if self._playing_narration and state == QMediaPlayer.PlaybackState.PausedState:
            self._media_player.play()
        else:
            self._play_audio_file(self._audio_path)

    def _pause_narration(self):
        if self._media_player is not None:
            self._media_player.pause()

    def _stop_audio(self):
        if self._media_player is not None:
            self._media_player.stop()

    def _on_playback_state_changed(self, state):
        """Update the narration status badge; previews never touch it."""
        if not self._playing_narration:
            return
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._set_narration_status("playing")
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self._set_narration_status("paused")
        else:
            self._refresh_narration_ui()

    def _on_duration_changed(self, ms):
        if not self._audio_path:
            return
        try:
            if self._media_player.source() != QUrl.fromLocalFile(str(self._audio_path)):
                return  # a preview clip's duration
        except Exception:
            return
        self._narration_duration_ms = ms
        self._update_narration_meta()

    def _download_audio(self):
        if not self._audio_path or not Path(self._audio_path).exists():
            NotificationService.get().warning("No narration audio available.")
            return
        src = Path(self._audio_path)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Download Narration Audio",
            f"{self.project_name or 'project'}_narration{src.suffix}",
            "Audio Files (*.mp3 *.wav *.m4a);;All Files (*.*)",
        )
        if not file_path:
            return
        try:
            shutil.copy2(str(src), file_path)
            NotificationService.get().success("Narration saved successfully.")
        except Exception as e:
            NotificationService.get().error(f"Download failed: {e}")

    def _confirm_regenerate(self) -> bool:
        """Ask before replacing an existing narration. Returns True on Regenerate."""
        box = QMessageBox(self)
        box.setWindowTitle("Regenerate Narration")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText("This will replace the current narration.\n\nContinue?")
        regenerate_btn = box.addButton(
            "Regenerate", QMessageBox.ButtonRole.DestructiveRole
        )
        cancel_btn = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel_btn)
        box.exec()
        return box.clickedButton() is regenerate_btn

    def _regenerate_voice(self):
        """Regenerate narration with the current script, voice, and speed."""
        if self._audio_path and Path(self._audio_path).exists():
            if not self._confirm_regenerate():
                return
        if self._voice_source == VOICE_SOURCE_IMPORT:
            NotificationService.get().info(
                "Switching to Built-in AI Voice to regenerate narration."
            )
            self._on_mode_selected(VOICE_SOURCE_AI)
        self.generate_voice()

    # ------------------------------------------------------------------
    # Narration module state
    # ------------------------------------------------------------------

    #: (label, theme color attr, theme background attr) per status key.
    _STATUS_BADGE = {
        "ready": ("Ready", "TEXT_MUTED", "SURFACE"),
        "generated": ("Generated", "SUCCESS", "SUCCESS_LIGHT"),
        "imported": ("Imported", "SECONDARY", "SECONDARY_LIGHT"),
        "generating": ("Generating...", "WARNING", "WARNING_LIGHT"),
        "playing": ("Playing", "SUCCESS", "SUCCESS_LIGHT"),
        "paused": ("Paused", "WARNING", "WARNING_LIGHT"),
        "error": ("Error", "ERROR", "ERROR_LIGHT"),
    }

    def _set_narration_status(self, status: str):
        label, color_attr, bg_attr = self._STATUS_BADGE[status]
        c = ThemeManager.instance().colors()
        self.narration_status_badge.setText(label)
        self.narration_status_badge.update_colors(
            getattr(c, color_attr), getattr(c, bg_attr)
        )

    def _group_label(self, text: str) -> QLabel:
        """Small caption used to label a control group inside the card."""
        c = ThemeManager.instance().colors()
        label = QLabel(text)
        label.setStyleSheet(f"{Fonts.caption_bold(c.TEXT_SECONDARY)}")
        self._group_labels.append(label)
        return label

    def _refresh_transcript_controls(self):
        """Enable transcript actions from the current page state."""
        has_audio = bool(self._audio_path) and Path(self._audio_path).exists()
        has_transcript = bool(self._transcript_text)
        busy = self._transcribing or self._generating
        self.generate_transcript_btn.setEnabled(has_audio and not busy)
        self.view_transcript_btn.setEnabled(has_transcript and not busy)
        self._update_transcript_status()

    def _update_transcript_status(self):
        """Refresh the Transcript group status and button label from real state.

        RC-6 status model distinguishes 'Generating...', 'Failed — reason', and
        a generated summary with character/segment counts from 'Not Generated',
        so 'Status: Ready' can never masquerade as a missing transcript.
        """
        c = ThemeManager.instance().colors()
        if self._transcribing:
            self.transcript_summary_label.setText("Status: Generating...")
            self.transcript_summary_label.setStyleSheet(f"{Fonts.tiny(c.WARNING)}")
            self.generate_transcript_btn.setText("Generate Transcript")
            return
        if self._transcript_error:
            reason = " ".join(str(self._transcript_error).split())
            if len(reason) > 100:
                reason = reason[:97] + "..."
            self.transcript_summary_label.setText(f"Status: Failed \u2014 {reason}")
            self.transcript_summary_label.setStyleSheet(f"{Fonts.tiny(c.ERROR)}")
            self.generate_transcript_btn.setText("Retry Transcription")
            return
        if self._transcript_text:
            n_chars = len(self._transcript_text)
            n_segs = len(self._segments)
            char_word = "character" if n_chars == 1 else "characters"
            seg_word = "segment" if n_segs == 1 else "segments"
            summary = f"{n_chars:,} {char_word}"
            if n_segs:
                summary += f" \u00b7 {n_segs:,} {seg_word}"
            self.transcript_summary_label.setText(f"Status: Generated \u2014 {summary}")
            self.transcript_summary_label.setStyleSheet(f"{Fonts.tiny(c.SUCCESS)}")
            self.generate_transcript_btn.setText("Regenerate Transcript")
            return
        self.transcript_summary_label.setText("Status: Not Generated")
        self.transcript_summary_label.setStyleSheet("")
        self.generate_transcript_btn.setText("Generate Transcript")

    def _set_playback_enabled(self, enabled: bool):
        for btn in (
            self.play_btn,
            self.pause_btn,
            self.stop_btn,
            self.download_audio_btn,
            self.regenerate_btn,
        ):
            btn.setEnabled(enabled)

    def _set_mode_options_enabled(self, enabled: bool):
        for option in self._mode_options.values():
            option.setEnabled(enabled)

    def _refresh_narration_status_from_player(self):
        """Badge by audio source, preserving live Playing/Paused states.

        A refresh (mode switch, theme change, project reload) must not
        overwrite "Playing"/"Paused" while the narration is actually
        playing or paused.
        """
        if self._playing_narration and self._media_player is not None:
            state = self._media_player.playbackState()
            if state == QMediaPlayer.PlaybackState.PlayingState:
                self._set_narration_status("playing")
                return
            if state == QMediaPlayer.PlaybackState.PausedState:
                self._set_narration_status("paused")
                return
        if self._voice_source == VOICE_SOURCE_IMPORT:
            self._set_narration_status("imported")
        else:
            self._set_narration_status("generated")

    def _refresh_narration_ui(self):
        """Show the empty state or the narration controls + status.

        The Transcript group is always visible (RC-6.2) so the core workflow
        dependency never disappears; only the post-generation Playback /
        Export / summary sections depend on an audio file existing.
        """
        has_audio = bool(self._audio_path) and Path(self._audio_path).exists()
        self.playback_container.setVisible(has_audio)
        self.export_container.setVisible(has_audio)
        self.narration_summary.setVisible(has_audio)
        self.narration_empty_label.setVisible(not has_audio)
        self._refresh_transcript_controls()
        self._update_import_identity()
        if not has_audio:
            self._set_narration_status("ready")
            if self._voice_source == VOICE_SOURCE_IMPORT:
                self.narration_empty_label.setText(
                    "No narration audio yet. Import an audio file to enable playback."
                )
            else:
                self.narration_empty_label.setText(
                    "No narration generated yet. Generate a voice to enable playback."
                )
            self._update_narration_meta()
            return
        if self._generating:
            self._set_narration_status("generating")
        else:
            self._refresh_narration_status_from_player()
        self._update_narration_meta()

    def _update_import_identity(self):
        """Populate the Imported Audio block from the real file metadata."""
        if not self._audio_path or not Path(self._audio_path).exists():
            self.imported_file_label.setText("No audio file selected")
            self.imported_meta_label.setText(
                "Choose an MP3, WAV, or M4A file in the Upload Audio section."
            )
            self.import_preview_btn.setEnabled(False)
            return
        self.imported_file_label.setText(Path(self._audio_path).name)
        parts = []
        ms = self._wav_duration_ms(self._audio_path) or self._narration_duration_ms
        if ms > 0:
            total_sec = ms // 1000
            parts.append(f"Duration: {total_sec // 60}:{total_sec % 60:02d}")
        try:
            size = Path(self._audio_path).stat().st_size
            parts.append(f"File size: {self._format_file_size(size)}")
        except OSError:
            pass
        self.imported_meta_label.setText("  \u00b7  ".join(parts) or "Imported audio")
        self.import_preview_btn.setEnabled(True)
        self.replace_audio_btn.setEnabled(True)

    def _update_narration_meta(self):
        """Refresh the generated-narration summary (Part 7) from real metadata."""
        if not self._audio_path or not Path(self._audio_path).exists():
            self.narration_duration_label.setText("Duration: \u2014")
            self.narration_size_label.setText("File size: \u2014")
            self.summary_voice_label.setText("Voice: \u2014")
            self.summary_generated_label.setText("Generated: \u2014")
            self._set_summary_title()
            return
        ms = self._wav_duration_ms(self._audio_path) or self._narration_duration_ms
        if ms > 0:
            total_sec = ms // 1000
            self.narration_duration_label.setText(
                f"Duration: {total_sec // 60}:{total_sec % 60:02d}"
            )
        else:
            self.narration_duration_label.setText("Duration: \u2014")
        try:
            stat = Path(self._audio_path).stat()
            size = stat.st_size
            generated_text = self._format_generated_time(stat.st_mtime)
        except OSError:
            size = 0
            generated_text = "\u2014"
        self.narration_size_label.setText(f"File size: {self._format_file_size(size)}")
        if self._voice_source == VOICE_SOURCE_IMPORT:
            voice_text = Path(self._audio_path).name
        else:
            voice_text = self._display_name(self._selected_voice_id)
        self.summary_voice_label.setText(f"Voice: {voice_text}")
        self.summary_generated_label.setText(f"Generated: {generated_text}")
        self._set_summary_title()

    def _set_summary_title(self):
        is_import = self._voice_source == VOICE_SOURCE_IMPORT
        self.summary_title_label.setText(
            "Audio Imported" if is_import else "Voice Generated"
        )

    @staticmethod
    def _format_generated_time(mtime) -> str:
        """Format a file mtime like 'Today 10:42 PM' (RC-6.1 Part 7)."""
        dt = datetime.fromtimestamp(mtime)
        now = datetime.now()
        if dt.date() == now.date():
            prefix = "Today"
        elif (now.date() - dt.date()).days == 1:
            prefix = "Yesterday"
        else:
            prefix = dt.strftime("%b %d")
        hour = dt.hour % 12 or 12
        ampm = "AM" if dt.hour < 12 else "PM"
        return f"{prefix} {hour}:{dt.minute:02d} {ampm}"

    @staticmethod
    def _format_file_size(size_bytes) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.0f} KB"
        return f"{size_bytes / (1024 * 1024):.1f} MB"

    @staticmethod
    def _wav_duration_ms(path) -> int:
        """Return the duration of a PCM WAV file in ms, or 0 when unknown."""
        try:
            with open(path, "rb") as f:
                head = f.read(12)
                if head[:4] != b"RIFF" or head[8:12] != b"WAVE":
                    return 0
                byte_rate = 0
                while True:
                    header = f.read(8)
                    if len(header) < 8:
                        break
                    chunk_id = header[:4]
                    (chunk_size,) = struct.unpack("<I", header[4:8])
                    if chunk_id == b"fmt ":
                        fmt_data = f.read(min(chunk_size, 1024))
                        if len(fmt_data) >= 12:
                            byte_rate = struct.unpack("<I", fmt_data[8:12])[0]
                        if chunk_size % 2:
                            f.read(1)
                    elif chunk_id == b"data":
                        if byte_rate > 0:
                            return int(chunk_size * 1000 / byte_rate)
                        break
                    else:
                        f.seek(chunk_size, 1)
                        if chunk_size % 2:
                            f.read(1)
        except Exception:
            return 0
        return 0

    # ------------------------------------------------------------------
    # Voice generation
    # ------------------------------------------------------------------

    def _refresh_tts_status(self):
        c = ThemeManager.instance().colors()
        service = self._voice_service
        if service.is_available():
            if service.is_model_ready():
                self.tts_status_label.setText(
                    "TTS ready \u2014 voice generation runs locally."
                )
                self.tts_status_label.setStyleSheet(f"color: {c.SUCCESS};")
            else:
                self.tts_status_label.setText(
                    "Model files not downloaded yet \u2014 they will download on first use."
                )
                self.tts_status_label.setStyleSheet(f"color: {c.WARNING};")
        else:
            self.tts_status_label.setText("kokoro-onnx not installed.")
            self.tts_status_label.setStyleSheet(f"color: {c.ERROR};")

    def show_tts_setup(self):
        service = self._voice_service
        if service.is_available():
            ready = service.is_model_ready()
            QMessageBox.information(
                self,
                "Local TTS",
                f"Local TTS (Kokoro-ONNX) is installed.\n\n"
                f"Model files cached: {'Yes' if ready else 'No'}\n"
                f"Voice generation runs entirely on this computer.",
            )
            return
        QMessageBox.warning(self, "TTS Setup Required", service.install_instruction())

    def generate_voice(self):
        if not self.project_name:
            NotificationService.get().warning("Select a project first.")
            return

        validation = self._pipeline.validate_stage(self.project_name, "Voice")
        if not validation.passed:
            for msg in validation.messages:
                NotificationService.get().warning(msg)
            return

        script_data = self._script_storage.load(self.project_name) or {}
        script_text = (script_data.get("script_output") or "").strip()
        if not script_text:
            NotificationService.get().warning(
                "No script exists. Generate a script first."
            )
            return

        service = self._voice_service
        if not service.is_available():
            NotificationService.get().warning(service.install_instruction())
            return

        if self._gen_thread and self._gen_thread.isRunning():
            NotificationService.get().warning("Voice generation is already running.")
            return

        project_path = self.manager.PROJECTS_DIR / self.project_name
        audio_dir = project_path / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        output_path = audio_dir / f"{self._selected_voice_id}_narration.wav"

        self._pipeline.mark_stage_started(self.project_name, "Voice")

        self._generating = True
        self._set_narration_status("generating")
        self._set_playback_enabled(False)
        self._set_mode_options_enabled(False)
        self.generate_btn.setEnabled(False)
        self.upload_btn.setEnabled(False)
        self.transcribe_btn.setEnabled(False)
        self.generate_transcript_btn.setEnabled(False)
        self.progress_widget.setVisible(True)
        self.progress_widget.reset()
        self.progress_widget.set_progress(2, "Initializing Voice Engine...")

        self._gen_cancel_event = threading.Event()
        self._gen_started_at = time.monotonic()
        self._synthesis_started_at = None
        self._reassurance_shown = False
        self.gen_actions.setVisible(True)
        self.cancel_gen_btn.setEnabled(True)
        self.cancel_gen_btn.setText("Cancel Generation")
        self.retry_gen_btn.setVisible(False)
        self._elapsed_timer.start()

        self._gen_thread = QThread()
        self._gen_worker = VoiceGenWorker(
            script_text,
            self._selected_voice_id,
            self._current_speed(),
            str(output_path),
            cancel_event=self._gen_cancel_event,
        )
        self._gen_worker.moveToThread(self._gen_thread)

        self._gen_thread.started.connect(self._gen_worker.run)
        self._gen_worker.stage.connect(self._on_voice_stage)
        self._gen_worker.progress.connect(self._on_voice_progress)
        self._gen_worker.finished.connect(self._on_voice_generated)
        self._gen_worker.error.connect(self._on_voice_error)
        self._gen_worker.cancelled.connect(self._on_voice_cancelled)
        self._gen_worker.finished.connect(self._gen_thread.quit)
        self._gen_worker.error.connect(self._gen_thread.quit)
        self._gen_worker.cancelled.connect(self._gen_thread.quit)
        self._gen_thread.finished.connect(self._cleanup_gen_thread)

        self._gen_thread.start()

    def _on_voice_stage(self, stage, message, fraction):
        """Update the progress display to the real pipeline stage.

        Measured stage milestones (model init, text prep, WAV encoding, file
        save) drive the determinate bar. The blocking Kokoro synthesis stage
        has no measurable completion percentage (the service reports only a
        fixed entry fraction), so it uses the animated indeterminate
        treatment with the elapsed-time readout rather than a fake percentage
        (FIX D).
        """
        if stage == "synthesis":
            if self._synthesis_started_at is None:
                self._synthesis_started_at = time.monotonic()
            self.progress_widget.set_indeterminate(status=message)
            return
        pct = int(max(0.0, min(1.0, fraction)) * 100)
        self.progress_widget.set_progress(pct, status=message)

    def _on_voice_progress(self, message, percent):
        if percent is None or percent < 0:
            self.progress_widget.set_progress(5, message)
            return
        self.progress_widget.set_progress(min(60, percent), message)

    def _update_elapsed_display(self):
        """Refresh the elapsed-time readout every second during generation.

        Once synthesis has been running for more than five seconds, show the
        reassurance hint so the user knows the app is still working.
        """
        if not self._generating or self._gen_started_at is None:
            self._elapsed_timer.stop()
            return
        elapsed = time.monotonic() - self._gen_started_at
        self.progress_widget.set_elapsed(elapsed)
        if (
            not self._reassurance_shown
            and self._synthesis_started_at is not None
            and time.monotonic() - self._synthesis_started_at > 5.0
        ):
            self._reassurance_shown = True
            self.progress_widget.set_hint(
                "Large narrations may take a little longer. "
                "KaiMi Studio is still generating your voice."
            )

    def _cancel_generation(self):
        """Ask the running worker to stop at the next stage boundary.

        The project (script, voice prefs, transcript) is left untouched; only
        the in-flight WAV is discarded.
        """
        if self._gen_cancel_event is None or self._gen_cancel_event.is_set():
            return
        self._gen_cancel_event.set()
        self.cancel_gen_btn.setEnabled(False)
        self.cancel_gen_btn.setText("Cancelling...")
        self.progress_widget.set_progress(
            self.progress_widget.progress_bar.value(),
            status="Stopping voice generation...",
        )

    def _on_voice_cancelled(self):
        """Restore the page after a user-initiated cancellation.

        The pipeline stage is reset to its previous state (not marked failed)
        so the project stays intact and can be retried at any time.
        """
        self._generating = False
        self._elapsed_timer.stop()
        self.gen_actions.setVisible(False)
        self.progress_widget.setVisible(False)
        self.generate_btn.setEnabled(True)
        self.upload_btn.setEnabled(True)
        self.transcribe_btn.setEnabled(True)
        self._set_playback_enabled(True)
        self._set_mode_options_enabled(True)
        self._pipeline.mark_stage_reset(self.project_name, "Voice")
        self._refresh_narration_ui()
        NotificationService.get().info(
            "Voice generation cancelled. The project was not modified."
        )

    def _on_voice_generated(self, output_path):
        self._audio_path = output_path
        self._generating = False
        self._elapsed_timer.stop()
        self.gen_actions.setVisible(False)
        self.generate_btn.setEnabled(True)
        self.upload_btn.setEnabled(True)
        self.generate_transcript_btn.setEnabled(True)
        self._set_playback_enabled(True)
        self._set_mode_options_enabled(True)
        self._refresh_narration_ui()
        self._auto_advance = True
        self.transcribe_audio()

    def _on_voice_error(self, stage, message):
        self._generating = False
        self._elapsed_timer.stop()
        self.generate_btn.setEnabled(True)
        self.upload_btn.setEnabled(True)
        self.transcribe_btn.setEnabled(True)
        self.generate_transcript_btn.setEnabled(True)
        self._set_playback_enabled(True)
        self._set_mode_options_enabled(True)
        self.cancel_gen_btn.setVisible(False)
        self.retry_gen_btn.setVisible(True)
        self.progress_widget.setVisible(True)
        stage_label = STAGE_MESSAGES.get(stage, stage)
        self.progress_widget.show_error(
            f"Failed at {stage_label} — {message}"
        )
        self._pipeline.mark_stage_failed(
            self.project_name, "Voice", f"[{stage}] {message}"
        )
        self._set_narration_status("error")
        NotificationService.get().error(
            f"Voice generation failed: {message}"
        )

    def _retry_voice(self):
        """Restart generation with the current script, voice, and speed."""
        self.retry_gen_btn.setVisible(False)
        self.generate_voice()

    def _cleanup_gen_thread(self):
        if self._gen_worker:
            self._gen_worker.deleteLater()
            self._gen_worker = None
        if self._gen_thread:
            self._gen_thread.deleteLater()
            self._gen_thread = None
        self._gen_cancel_event = None

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _read_voice_prefs(self):
        if not self.project_name:
            return {}
        fp = self.manager.PROJECTS_DIR / self.project_name / "voice.json"
        if not fp.exists():
            return {}
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _persist_voice_prefs(self):
        if not self.project_name:
            return
        fp = self.manager.PROJECTS_DIR / self.project_name / "voice.json"
        data = self._read_voice_prefs()
        data["voice_source"] = self._voice_source
        data["voice_id"] = self._selected_voice_id
        data["voice_speed"] = self._current_speed()
        try:
            fp.write_text(json.dumps(data, indent=4), encoding="utf-8")
        except Exception:
            pass

    def _restore_voice_settings(self):
        prefs = self._read_voice_prefs()
        source = prefs.get("voice_source", VOICE_SOURCE_AI)
        if source not in VOICE_SOURCES:
            source = VOICE_SOURCE_AI
        voice_id = prefs.get("voice_id") or DEFAULT_VOICE_ID
        try:
            speed = float(prefs.get("voice_speed", DEFAULT_SPEED))
        except (TypeError, ValueError):
            speed = float(DEFAULT_SPEED)
        if speed not in SPEED_OPTIONS:
            speed = float(DEFAULT_SPEED)

        self._voice_source = source
        self._selected_voice_id = voice_id
        self._set_mode_ui(source)
        self._set_speed(speed)
        self._update_voice_summary()

    # ------------------------------------------------------------------
    # Project data / transcript (existing import workflow preserved)
    # ------------------------------------------------------------------

    def _load_project_data(self):
        if not self.project_name:
            return
        self.project_label.setText(f"/ {self.project_name}")

        project_data = self.manager.load_project(self.project_name)
        if project_data:
            self.info_project.setText(f"Project: {self.project_name}")
            self.info_topic.setText(f"Topic: {project_data.get('topic', '\u2014')}")
            self.info_language.setText(f"Language: {project_data.get('language', '\u2014')}")

        project_path = self.manager.PROJECTS_DIR / self.project_name
        # A project with no narration audio must not keep the previous
        # project's audio path (RC-6.2 cross-project state isolation): Play,
        # Download, and Transcription otherwise operate on another project's
        # file while the user is looking at this project.
        self._audio_path = None
        audio_dir = project_path / "audio"
        if audio_dir.exists():
            audio_files = [f for f in audio_dir.iterdir() if f.is_file()]
            if audio_files:
                self._audio_path = str(audio_files[0])

        if not self._dirty:
            # A project switch must not keep the previous project's transcript
            # (RC-6.2 cross-project state isolation). Unsaved editor edits are
            # preserved (Sprint 3.4B / C2).
            self._transcript_text = ""
            self._segments = []

        self._load_saved_transcript(project_path)

        self._restore_voice_settings()
        self._refresh_import_ui()
        self._refresh_narration_ui()

        if self._transcript_text and not self._dirty:
            # Never overwrite unsaved user edits (Sprint 3.4B / C2). Pipeline
            # events reload page data; only reload the editor when it is clean.
            self.next_btn.setEnabled(True)
            self.view_transcript_btn.setEnabled(True)
            self._update_transcript_status()
            self.transcript_box.setPlainText(self._transcript_text)
            self._saved_text = self._transcript_text
            self._update_status_clean()
            seg_count = len(self._segments)
            if seg_count:
                first_time = self._segments[0].get("time", "")
                last_time = self._segments[-1].get("time", "")
                self.timestamps_label.setText(
                    f"{seg_count} segments  |  First: {first_time}  |  Last: {last_time}"
                )
        elif not self._dirty:
            # A project with no transcript must not keep another project's text.
            self._saved_text = ""
            self.transcript_box.setPlainText("")
            self.next_btn.setEnabled(False)
            self.view_transcript_btn.setEnabled(False)
            self._update_transcript_status()
            self.timestamps_label.setText("")

    def _load_saved_transcript(self, project_path):
        fp = project_path / "transcript.json"
        if fp.exists():
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                text = data.get("text", "").strip()
                if text:
                    self._transcript_text = text
                    self._saved_text = text
                    voice_path = project_path / "voice.json"
                    if voice_path.exists():
                        vdata = json.loads(voice_path.read_text(encoding="utf-8"))
                        self._segments = vdata.get("segments", [])
                    return
            except Exception:
                pass

        fp = project_path / "voice.json"
        if fp.exists():
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                text = data.get("transcript", "").strip()
                if text:
                    self._transcript_text = text
                    self._saved_text = text
                    self._segments = data.get("segments", [])
            except Exception:
                pass

    def choose_audio(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio File",
            "",
            "Audio Files (*.mp3 *.wav *.m4a);;All Files (*.*)",
        )
        if not file_path:
            return

        ext = Path(file_path).suffix.lower()
        if ext not in AUDIO_EXTENSIONS:
            NotificationService.get().error("Unsupported audio format. Use MP3, WAV, or M4A.")
            return

        self._audio_path = file_path
        self.file_label.setText(f"Selected: {Path(file_path).name}")
        if not self._transcribing:
            self.transcribe_btn.setEnabled(True)

        if self.project_name:
            audio_dir = self.manager.PROJECTS_DIR / self.project_name / "audio"
            audio_dir.mkdir(parents=True, exist_ok=True)
            dest = audio_dir / Path(file_path).name
            shutil.copy2(file_path, str(dest))
            self._audio_path = str(dest)

        self._refresh_narration_ui()

    def _on_model_changed(self, model_name: str):
        service = get_transcription_service()
        try:
            service.set_model(model_name)
            NotificationService.get().info(
                f"Whisper model set to '{model_name}'. It will load on the next transcription."
            )
        except ValueError as exc:
            NotificationService.get().error(str(exc))

    def show_whisper_setup(self):
        service = get_transcription_service()
        if service.is_available():
            model = service.get_configured_model()
            QMessageBox.information(
                self,
                "Local Whisper",
                f"Local Whisper (faster-whisper) is installed.\n\n"
                f"Active model: {model}\n"
                f"Transcription runs entirely on this computer.",
            )
            return
        QMessageBox.warning(
            self,
            "Whisper Setup Required",
            service.install_instruction(),
        )

    def transcribe_audio(self):
        if self._transcribing:
            NotificationService.get().warning(
                "Transcription is already running."
            )
            return
        if not self.project_name:
            NotificationService.get().warning("Select a project first.")
            return
        if not self._audio_path:
            NotificationService.get().warning(
                "No audio file selected. Choose an MP3, WAV, or M4A file first."
            )
            return

        validation = self._pipeline.validate_stage(self.project_name, "Voice")
        if not validation.passed:
            for msg in validation.messages:
                NotificationService.get().warning(msg)
            return

        transcription_service = get_transcription_service()
        if not transcription_service.is_available():
            NotificationService.get().warning(transcription_service.install_instruction())
            return

        self._pipeline.mark_stage_started(self.project_name, "Voice")

        self._transcribing = True
        self._transcript_error = None
        self._set_mode_options_enabled(False)
        self.transcribe_btn.setEnabled(False)
        self.upload_btn.setEnabled(False)
        self.generate_transcript_btn.setEnabled(False)
        self.progress_widget.setVisible(True)
        self.progress_widget.reset()
        self._update_transcript_status()
        self._start_progress_animation()

        self._worker_thread = QThread()
        self._worker = TranscribeWorker(self._audio_path)
        self._worker.moveToThread(self._worker_thread)

        self._worker_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_transcription_done)
        self._worker.error.connect(self._on_transcription_error)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.error.connect(self._worker_thread.quit)
        self._worker_thread.finished.connect(self._cleanup_thread)

        self._worker_thread.start()

    def _start_progress_animation(self):
        self._progress_index = 0
        self._transcription_timer = QTimer(self)
        self._transcription_timer.timeout.connect(self._animate_progress)
        self._transcription_timer.start(1200)
        self._animate_progress()

    def _animate_progress(self):
        if not self._transcribing:
            self._stop_progress_animation()
            return
        if self._progress_index >= len(TRANSCRIPTION_STATUSES):
            self.progress_widget.set_progress(95, "Finalizing transcript...")
            if self._transcription_timer:
                self._transcription_timer.stop()
            return
        pct, status = TRANSCRIPTION_STATUSES[self._progress_index]
        self.progress_widget.set_progress(pct, status)
        self._progress_index += 1

    def _stop_progress_animation(self):
        if self._transcription_timer:
            self._transcription_timer.stop()
            self._transcription_timer.deleteLater()
            self._transcription_timer = None

    def _cleanup_thread(self):
        if self._worker:
            self._worker.deleteLater()
            self._worker = None
        if self._worker_thread:
            self._worker_thread.deleteLater()
            self._worker_thread = None

    def _on_transcription_done(self, transcript, segments):
        self._transcribing = False
        self._transcript_error = None
        self._stop_progress_animation()
        self._transcript_text = transcript
        self._segments = segments

        self.progress_widget.show_complete("Transcript generated successfully.")
        QTimer.singleShot(1500, lambda: self.progress_widget.setVisible(False))

        self.transcript_box.setPlainText(transcript)

        segs_out = []
        for seg in segments:
            segs_out.append({
                "start": seg.get("start", 0),
                "end": seg.get("end", 0),
                "text": seg.get("text", ""),
                "time": f"{int(seg.get('start', 0) // 60):02d}:{int(seg.get('start', 0) % 60):02d}",
            })

        voice_data = {
            "transcript": transcript,
            "segments": segs_out,
            "audio_file": self._audio_path,
            "voice_source": self._voice_source,
            "voice_id": self._selected_voice_id,
            "voice_speed": self._current_speed(),
        }
        project_path = self.manager.PROJECTS_DIR / self.project_name
        voice_path = project_path / "voice.json"
        voice_path.write_text(json.dumps(voice_data, indent=4), encoding="utf-8")

        transcript_path = project_path / "transcript.json"
        transcript_path.write_text(
            json.dumps({"text": transcript}, indent=4), encoding="utf-8"
        )

        self._saved_text = transcript
        self._update_status_clean()

        self.next_btn.setEnabled(True)
        self.view_transcript_btn.setEnabled(True)
        self._update_transcript_status()

        if segs_out:
            self.timestamps_label.setText(
                f"{len(segs_out)} segments  |  First: {segs_out[0]['time']}  |  Last: {segs_out[-1]['time']}"
            )

        self._pipeline.mark_stage_completed(self.project_name, "Voice")

        self.transcribe_btn.setEnabled(True)
        self.upload_btn.setEnabled(True)
        self.generate_btn.setEnabled(True)
        self.generate_transcript_btn.setEnabled(True)
        self._set_mode_options_enabled(True)
        self._refresh_narration_ui()
        self._history.record_action(
            self.project_name, "Transcribed",
            f"Generated transcript from audio ({len(segs_out)} segments)"
        )
        NotificationService.get().success("Transcript generated successfully.")

        if self._auto_advance:
            self._auto_advance = False
            QTimer.singleShot(300, self.go_to_image_prompts)

    def _on_transcription_error(self, error_msg):
        self._transcribing = False
        self._transcript_error = error_msg
        self._stop_progress_animation()
        self.progress_widget.setVisible(False)
        self.transcribe_btn.setEnabled(True)
        self.upload_btn.setEnabled(True)
        self.generate_btn.setEnabled(True)
        self.generate_transcript_btn.setEnabled(True)
        self._set_mode_options_enabled(True)
        self._pipeline.mark_stage_failed(self.project_name, "Voice", error_msg)
        self._set_narration_status("error")
        self._update_transcript_status()
        NotificationService.get().error(f"Transcription failed: {error_msg}")

    def _autosave_save(self):
        if not self.project_name:
            return
        text = self.transcript_box.toPlainText()
        project_path = self.manager.PROJECTS_DIR / self.project_name
        fp = project_path / "transcript.json"
        fp.write_text(json.dumps({"text": text}, indent=4), encoding="utf-8")
        self._saved_text = text
        self._update_status_clean()

    def save_transcript(self):
        if not self.project_name:
            return
        self._autosave_save()
        self._history.record_action(self.project_name, "Saved", "Manually saved transcript")
        NotificationService.get().success("Transcript saved.")

    def download_transcript(self):
        if not self.project_name:
            return
        text = self.transcript_box.toPlainText()
        if not text.strip():
            NotificationService.get().warning("Nothing to download.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Download Transcript",
            f"{self.project_name}_transcript.txt",
            "Text Files (*.txt);;All Files (*.*)",
        )
        if not file_path:
            return

        try:
            lines = [f"Transcript: {self.project_name}", "", text]
            Path(file_path).write_text("\n".join(lines), encoding="utf-8")
            NotificationService.get().success(
                f"Transcript saved to {Path(file_path).name}"
            )
        except Exception as e:
            NotificationService.get().error(f"Download failed: {e}")

    def go_to_image_prompts(self):
        if not self.project_name:
            return
        main = self.window()
        if main and hasattr(main, "navigate_to"):
            main.navigate_to("Image Prompts", self.project_name)
