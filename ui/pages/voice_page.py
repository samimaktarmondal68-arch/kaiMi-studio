import json
import shutil
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QObject, QThread, QTimer, Qt, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
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
from core.notifications import NotificationService
from core.pipeline_service import get_pipeline_service
from core.project_manager import ProjectManager
from core.script_storage import ScriptStorage
from core.theme import Fonts, Spacing, Radius
from core.transcription_service import WHISPER_MODELS, get_transcription_service
from core.voice_generation_service import (
    DEFAULT_SPEED,
    DEFAULT_VOICE_ID,
    get_voice_generation_service,
)
from ..theme_pyside import ThemeManager
from ..widgets import (
    AutosaveIndicator,
    CardTitle,
    IconProvider,
    ModernButton,
    ModernCard,
    MutedLabel,
    ProgressWidget,
    SearchInput,
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

_VOICE_GRID_COLUMNS = 3


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


def _fallback_voice_entry(voice_id: str) -> tuple[str, str]:
    """Derive a display name and description for an unknown Kokoro id."""
    if "_" in voice_id:
        prefix, _, raw = voice_id.partition("_")
        name = " ".join(word.capitalize() for word in raw.split("_"))
        locale = _LOCALE_NAMES.get(prefix[0] if prefix else "", "International")
        gender = "Female" if len(prefix) > 1 and prefix[1] == "f" else "Male"
        desc = f"{locale} — {gender} voice"
        return name, desc
    return voice_id.capitalize(), "Local Kokoro voice"


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
    """Synthesize the narration for a project on a background thread."""

    progress = Signal(str, int)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, text, voice_id, speed, output_path):
        super().__init__()
        self.text = text
        self.voice_id = voice_id
        self.speed = speed
        self.output_path = output_path

    def run(self):
        try:
            service = get_voice_generation_service()
            service.ensure_model_ready(self._report_progress)
            self.progress.emit("Synthesizing narration...", 75)
            service.generate_to_file(
                self.text, self.voice_id, self.speed, self.output_path
            )
            self.progress.emit("Voice generated.", 100)
            self.finished.emit(str(self.output_path))
        except Exception as e:
            self.error.emit(str(e))

    def _report_progress(self, message, percent):
        self.progress.emit(message, percent)


class _ModeOption(QFrame):
    """Clickable source selector used to switch between AI voice / import."""

    clicked = Signal(str)

    def __init__(self, source, title, description, icon_name, parent=None):
        super().__init__(parent)
        self.source = source
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


class _VoiceCard(QFrame):
    """A single voice card: name, description, preview and select buttons."""

    def __init__(self, voice_id, name, description, selected, on_select, on_preview,
                 parent=None):
        super().__init__(parent)
        self.voice_id = voice_id
        self.setObjectName("card")
        self.setAttribute(Qt.WA_StyledBackground, True)

        c = ThemeManager.instance().colors()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(6)
        self.name_label = QLabel(name)
        self.name_label.setStyleSheet(f"{Fonts.body_bold(c.TEXT)}")
        header.addWidget(self.name_label)
        header.addStretch()
        self.selected_badge = QLabel("Selected")
        self.selected_badge.setStyleSheet(
            f"{Fonts.tiny(c.SUCCESS)} padding: 2px 8px; border-radius: 6px; "
            f"background-color: {c.SUCCESS_LIGHT};"
        )
        self.selected_badge.setVisible(False)
        header.addWidget(self.selected_badge)
        layout.addLayout(header)

        self.desc_label = QLabel(description)
        self.desc_label.setStyleSheet(f"{Fonts.caption(c.TEXT_SECONDARY)}")
        self.desc_label.setWordWrap(True)
        layout.addWidget(self.desc_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.preview_btn = ModernButton("Preview", primary=False)
        self.preview_btn.setFixedHeight(30)
        self.preview_btn.clicked.connect(lambda: on_preview(self.voice_id))
        btn_row.addWidget(self.preview_btn)

        self.select_btn = ModernButton("Select", primary=True)
        self.select_btn.setFixedHeight(30)
        self.select_btn.clicked.connect(lambda: on_select(self.voice_id))
        btn_row.addWidget(self.select_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.set_selected(selected)

    def set_selected(self, selected: bool):
        c = ThemeManager.instance().colors()
        if selected:
            self.setStyleSheet(
                f"QFrame#card {{ border: 1px solid {c.PRIMARY}; "
                f"background-color: {c.CARD}; }}"
            )
            self.selected_badge.setVisible(True)
            self.select_btn.setText("Selected")
            self.select_btn.setEnabled(False)
        else:
            self.setStyleSheet("")
            self.selected_badge.setVisible(False)
            self.select_btn.setText("Select")
            self.select_btn.setEnabled(True)


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
        self._saved_text = ""
        self._dirty = False
        self._transcribing = False
        self._auto_advance = False
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
        self._all_voices_expanded = False
        self._voice_cards = {}
        self._preview_cache = {}
        self._preview_loading_id = None
        self._preview_thread = None
        self._preview_worker = None
        self._gen_thread = None
        self._gen_worker = None
        self._media_player = None
        self._audio_output = None
        self._media_buffer = None
        self._installed_voice_ids = _load_installed_voice_ids()
        self._recommended_profiles = self._voice_service.get_available_voices()
        ThemeManager.instance().on_change(lambda _: self._on_theme_changed())
        self._build()

    def _on_theme_changed(self):
        if self.project_name:
            self._load_project_data()

    def cleanup(self):
        """Stop background workers and wait for their threads to finish.

        Workers cannot be interrupted mid-operation (transcription / TTS), so
        the GUI thread waits while processing events. Deleting a running
        QThread would abort the application on exit (Sprint 3.4B / C3).
        """
        self._stop_progress_animation()
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
        self.project_name = name
        self._load_project_data()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self._build_project_header(layout)

        self._build_mode_selector(layout)

        self._build_ai_voice_section(layout)

        self._build_upload_section(layout)

        self.progress_widget = ProgressWidget()
        self.progress_widget.setVisible(False)
        layout.addWidget(self.progress_widget)

        self._build_transcript_section(layout)

        self._build_action_bar(layout)

        layout.addStretch()

        self._set_mode_ui(self._voice_source)
        self._rebuild_voice_library()

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

    def _build_ai_voice_section(self, parent):
        card = ModernCard()
        card.content_layout.setSpacing(10)
        card.content_layout.addWidget(SectionHeader("Built-in AI Voice"))

        self.voice_search = SearchInput("Search voices by name or description...")
        self.voice_search.textChanged.connect(self._on_voice_search)
        card.content_layout.addWidget(self.voice_search)

        rec_header = QHBoxLayout()
        rec_header.setSpacing(8)
        rec_title = QLabel("Recommended")
        rec_title.setStyleSheet(
            f"{Fonts.caption_bold(ThemeManager.instance().colors().TEXT)}"
        )
        rec_header.addWidget(rec_title)
        self.recommended_count = MutedLabel("")
        rec_header.addWidget(self.recommended_count)
        rec_header.addStretch()
        card.content_layout.addLayout(rec_header)

        self.recommended_scroll = QScrollArea()
        self.recommended_scroll.setWidgetResizable(True)
        self.recommended_scroll.setFrameShape(QScrollArea.NoFrame)
        self.recommended_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.recommended_scroll.setMaximumHeight(300)
        self.recommended_container = QWidget()
        self.recommended_grid = QGridLayout(self.recommended_container)
        self.recommended_grid.setContentsMargins(0, 0, 0, 0)
        self.recommended_grid.setSpacing(10)
        self.recommended_scroll.setWidget(self.recommended_container)
        card.content_layout.addWidget(self.recommended_scroll)

        all_header = QHBoxLayout()
        all_header.setSpacing(8)
        all_title = QLabel("All Voices")
        all_title.setStyleSheet(
            f"{Fonts.caption_bold(ThemeManager.instance().colors().TEXT)}"
        )
        all_header.addWidget(all_title)
        self.all_voices_count = MutedLabel("")
        all_header.addWidget(self.all_voices_count)
        all_header.addStretch()
        self.all_voices_toggle = ModernButton("Show All", primary=False)
        self.all_voices_toggle.setFixedHeight(30)
        self.all_voices_toggle.clicked.connect(self._toggle_all_voices)
        all_header.addWidget(self.all_voices_toggle)
        card.content_layout.addLayout(all_header)

        self.all_voices_scroll = QScrollArea()
        self.all_voices_scroll.setWidgetResizable(True)
        self.all_voices_scroll.setFrameShape(QScrollArea.NoFrame)
        self.all_voices_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.all_voices_scroll.setMaximumHeight(240)
        self.all_voices_container = QWidget()
        self.all_voices_grid = QGridLayout(self.all_voices_container)
        self.all_voices_grid.setContentsMargins(0, 0, 0, 0)
        self.all_voices_grid.setSpacing(10)
        self.all_voices_scroll.setWidget(self.all_voices_container)
        card.content_layout.addWidget(self.all_voices_scroll)

        speed_row = QHBoxLayout()
        speed_row.setSpacing(8)
        speed_row.addWidget(MutedLabel("Voice speed:"))
        self.speed_combo = QComboBox()
        for speed in SPEED_OPTIONS:
            self.speed_combo.addItem(f"{speed:.1f}\u00d7", float(speed))
        idx = self.speed_combo.findData(float(DEFAULT_SPEED))
        self.speed_combo.setCurrentIndex(max(idx, 0))
        self.speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        speed_row.addWidget(self.speed_combo)
        self.selected_voice_label = MutedLabel("")
        speed_row.addWidget(self.selected_voice_label)
        speed_row.addStretch()
        card.content_layout.addLayout(speed_row)

        gen_row = QHBoxLayout()
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
        card.content_layout.addLayout(gen_row)

        parent.addWidget(card)
        self._ai_card = card
        self._refresh_tts_status()

    def _build_upload_section(self, parent):
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

        self.transcribe_btn = ModernButton("Generate Transcript", primary=False)
        self.transcribe_btn.clicked.connect(self.transcribe_audio)
        self.transcribe_btn.setEnabled(False)
        btn_row.addWidget(self.transcribe_btn)

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

    def _build_transcript_section(self, parent):
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)

        title_row.addWidget(SectionHeader("Transcript Editor"))

        self.status_label = MutedLabel("")
        title_row.addWidget(self.status_label)

        title_row.addWidget(self._autosave_indicator)
        title_row.addStretch()

        parent.addLayout(title_row)

        self.transcript_box = QPlainTextEdit()
        self.transcript_box.setPlaceholderText("No transcript yet. Upload audio and generate.")
        self.transcript_box.textChanged.connect(self._on_text_edit)
        self.transcript_box.setMinimumHeight(160)
        parent.addWidget(self.transcript_box, 1)

        self.timestamps_label = MutedLabel("")
        parent.addWidget(self.timestamps_label)

    def _build_action_bar(self, parent):
        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(12)

        self.save_btn = ModernButton("Save Transcript", primary=True)
        self.save_btn.clicked.connect(self.save_transcript)
        self.save_btn.setEnabled(False)
        bar.addWidget(self.save_btn)

        self.download_btn = ModernButton("Download TXT", primary=False)
        self.download_btn.clicked.connect(self.download_transcript)
        self.download_btn.setEnabled(False)
        bar.addWidget(self.download_btn)

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
        self._ai_card.setVisible(ai_visible)
        self._upload_card.setVisible(not ai_visible)
        self._refresh_import_ui()

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
    # Voice library
    # ------------------------------------------------------------------

    def _on_voice_search(self, _text):
        self._rebuild_voice_library()

    @staticmethod
    def _voice_matches(name, description, query):
        if not query:
            return True
        return query in name.lower() or query in description.lower()

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

    def _rebuild_voice_library(self):
        query = self.voice_search.text().strip().lower()
        self._clear_layout(self.recommended_grid)
        self._clear_layout(self.all_voices_grid)
        self._voice_cards = {}

        recommended_count = 0
        for profile in self._recommended_profiles:
            if not self._voice_matches(profile.name, profile.description, query):
                continue
            card = self._make_voice_card(
                profile.id, profile.name, profile.description
            )
            self._voice_cards[profile.id] = card
            self._grid_add(self.recommended_grid, card, _VOICE_GRID_COLUMNS)
            recommended_count += 1

        remaining_count = 0
        for voice_id, name, description in self._remaining_voices():
            if not self._voice_matches(name, description, query):
                continue
            card = self._make_voice_card(voice_id, name, description)
            self._voice_cards[voice_id] = card
            self._grid_add(self.all_voices_grid, card, _VOICE_GRID_COLUMNS)
            remaining_count += 1

        self.recommended_count.setText(
            f"{recommended_count} shown \u00b7 "
            f"{len(self._recommended_profiles)} total"
        )
        self.all_voices_count.setText(
            f"{remaining_count} shown \u00b7 "
            f"{len(self._remaining_voices())} available"
        )

        if query:
            self._set_all_voices_expanded(True)
        else:
            self._set_all_voices_expanded(self._all_voices_expanded)

        self._sync_selected()

    def _make_voice_card(self, voice_id, name, description):
        return _VoiceCard(
            voice_id,
            name,
            description,
            selected=(voice_id == self._selected_voice_id),
            on_select=self._select_voice,
            on_preview=self._preview_voice,
        )

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    @staticmethod
    def _grid_add(layout, widget, columns):
        index = layout.count()
        layout.addWidget(widget, index // columns, index % columns)

    def _toggle_all_voices(self):
        self._set_all_voices_expanded(not self._all_voices_expanded)

    def _set_all_voices_expanded(self, expanded):
        self._all_voices_expanded = expanded
        self.all_voices_scroll.setVisible(expanded)
        self.all_voices_toggle.setText("Hide" if expanded else "Show All")

    def _sync_selected(self):
        for voice_id, card in self._voice_cards.items():
            card.set_selected(voice_id == self._selected_voice_id)
        self._update_selected_voice_label()

    def _update_selected_voice_label(self):
        if self.selected_voice_label is not None:
            self.selected_voice_label.setText(
                f"Selected: {self._display_name(self._selected_voice_id)}"
            )

    def _select_voice(self, voice_id):
        self._selected_voice_id = voice_id
        self._sync_selected()
        self._persist_voice_prefs()

    def _on_speed_changed(self, _index):
        self._persist_voice_prefs()

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

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

        card = self._voice_cards.get(voice_id)
        if card:
            card.preview_btn.setText("Generating...")
            card.preview_btn.setEnabled(False)

        self._preview_loading_id = voice_id
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
        self._restore_preview_button(voice_id)
        self._play_wav_bytes(wav_bytes)

    def _on_preview_error(self, voice_id, message):
        self._restore_preview_button(voice_id)
        NotificationService.get().error(f"Preview failed: {message}")

    def _restore_preview_button(self, voice_id):
        card = self._voice_cards.get(voice_id)
        if card:
            card.preview_btn.setText("Preview")
            card.preview_btn.setEnabled(True)

    def _cleanup_preview_thread(self):
        if self._preview_worker:
            self._preview_worker.deleteLater()
            self._preview_worker = None
        if self._preview_thread:
            self._preview_thread.deleteLater()
            self._preview_thread = None

    def _play_wav_bytes(self, data: bytes):
        if self._media_player is None:
            self._media_player = QMediaPlayer(self)
            self._audio_output = QAudioOutput(self)
            self._media_player.setAudioOutput(self._audio_output)
        if self._media_buffer is not None:
            self._media_buffer.close()
            self._media_buffer.deleteLater()
        self._media_buffer = QBuffer(self)
        self._media_buffer.setData(data)
        self._media_buffer.open(QIODevice.ReadOnly)
        self._media_player.setSourceDevice(self._media_buffer)
        self._media_player.play()

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

        self.generate_btn.setEnabled(False)
        self.upload_btn.setEnabled(False)
        self.transcribe_btn.setEnabled(False)
        self.progress_widget.setVisible(True)
        self.progress_widget.reset()
        self.progress_widget.set_progress(2, "Preparing local TTS...")

        self._gen_thread = QThread()
        self._gen_worker = VoiceGenWorker(
            script_text,
            self._selected_voice_id,
            self._current_speed(),
            str(output_path),
        )
        self._gen_worker.moveToThread(self._gen_thread)

        self._gen_thread.started.connect(self._gen_worker.run)
        self._gen_worker.progress.connect(self._on_voice_progress)
        self._gen_worker.finished.connect(self._on_voice_generated)
        self._gen_worker.error.connect(self._on_voice_error)
        self._gen_worker.finished.connect(self._gen_thread.quit)
        self._gen_worker.error.connect(self._gen_thread.quit)
        self._gen_thread.finished.connect(self._cleanup_gen_thread)

        self._gen_thread.start()

    def _on_voice_progress(self, message, percent):
        if percent is None or percent < 0:
            self.progress_widget.set_progress(5, message)
            return
        self.progress_widget.set_progress(min(60, percent), message)

    def _on_voice_generated(self, output_path):
        self._audio_path = output_path
        self.generate_btn.setEnabled(True)
        self.upload_btn.setEnabled(True)
        self._auto_advance = True
        self.transcribe_audio()

    def _on_voice_error(self, message):
        self.generate_btn.setEnabled(True)
        self.upload_btn.setEnabled(True)
        self.transcribe_btn.setEnabled(True)
        self.progress_widget.setVisible(False)
        self._pipeline.mark_stage_failed(self.project_name, "Voice", message)
        NotificationService.get().error(f"Voice generation failed: {message}")

    def _cleanup_gen_thread(self):
        if self._gen_worker:
            self._gen_worker.deleteLater()
            self._gen_worker = None
        if self._gen_thread:
            self._gen_thread.deleteLater()
            self._gen_thread = None

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
        self._rebuild_voice_library()

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
        audio_dir = project_path / "audio"
        if audio_dir.exists():
            audio_files = [f for f in audio_dir.iterdir() if f.is_file()]
            if audio_files:
                self._audio_path = str(audio_files[0])

        self._load_saved_transcript(project_path)

        self._restore_voice_settings()
        self._refresh_import_ui()

        if self._transcript_text and not self._dirty:
            # Never overwrite unsaved user edits (Sprint 3.4B / C2). Pipeline
            # events reload page data; only reload the editor when it is clean.
            self.next_btn.setEnabled(True)
            self.download_btn.setEnabled(True)
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
            self.download_btn.setEnabled(False)
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
        self.transcribe_btn.setEnabled(False)
        self.upload_btn.setEnabled(False)
        self.progress_widget.setVisible(True)
        self.progress_widget.reset()
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

        self.download_btn.setEnabled(True)
        self.next_btn.setEnabled(True)

        if segs_out:
            self.timestamps_label.setText(
                f"{len(segs_out)} segments  |  First: {segs_out[0]['time']}  |  Last: {segs_out[-1]['time']}"
            )

        self._pipeline.mark_stage_completed(self.project_name, "Voice")

        self.transcribe_btn.setEnabled(True)
        self.upload_btn.setEnabled(True)
        self.generate_btn.setEnabled(True)
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
        self._stop_progress_animation()
        self.progress_widget.setVisible(False)
        self.transcribe_btn.setEnabled(True)
        self.upload_btn.setEnabled(True)
        self.generate_btn.setEnabled(True)
        self._pipeline.mark_stage_failed(self.project_name, "Voice", error_msg)
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
