import json
import shutil
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.autosave import get_autosave_manager
from core.history_manager import HistoryManager
from core.notifications import NotificationService
from core.project_manager import ProjectManager
from core.theme import Fonts, Spacing, Radius
from core.workflow import advance_workflow_state
from ..theme_pyside import ThemeManager
from ..widgets import (
    AutosaveIndicator,
    CardTitle,
    ModernButton,
    ModernCard,
    MutedLabel,
    ProgressWidget,
    SectionHeader,
    StatusBadge,
)

AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a")


class TranscribeWorker(QObject):
    finished = Signal(str, list)
    error = Signal(str)

    def __init__(self, audio_path):
        super().__init__()
        self.audio_path = audio_path

    def run(self):
        try:
            import whisper
            model = whisper.load_model("base")
            result = model.transcribe(self.audio_path)
            transcript = result.get("text", "").strip()
            segments = result.get("segments", [])
            self.finished.emit(transcript, segments)
        except Exception as e:
            self.error.emit(str(e))


class VoicePage(QWidget):
    def __init__(self):
        super().__init__()
        self.manager = ProjectManager()
        self.project_name = None
        self._audio_path = None
        self._transcript_text = ""
        self._segments = []
        self._saved_text = ""
        self._dirty = False
        self._transcribing = False
        self._worker_thread = None
        self._worker = None
        self._history = HistoryManager()
        self._autosave = get_autosave_manager()
        self._autosave.register("voice", self._autosave_save)
        self._autosave_indicator = AutosaveIndicator()
        self._autosave.on_status_change(self._autosave_indicator.set_status)
        ThemeManager.instance().on_change(lambda _: self._on_theme_changed())
        self._build()

    def _on_theme_changed(self):
        if self.project_name:
            self._load_project_data()

    def cleanup(self):
        if self._worker_thread and self._worker_thread.isRunning():
            self._worker_thread.quit()
            self._worker_thread.wait(3000)
        if self._worker:
            self._worker.deleteLater()
            self._worker = None
        if self._worker_thread:
            self._worker_thread.deleteLater()
            self._worker_thread = None

    def set_project(self, name):
        self.project_name = name
        self._load_project_data()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        self._build_project_header(layout)
        layout.addSpacing(8)

        self._build_upload_section(layout)
        layout.addSpacing(8)

        self._build_transcript_section(layout)
        layout.addSpacing(12)

        self._build_action_bar(layout)

        layout.addStretch()

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

    def _build_upload_section(self, parent):
        card = ModernCard()
        card.content_layout.setSpacing(12)

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

        self.progress_widget = ProgressWidget()
        self.progress_widget.setVisible(False)
        card.content_layout.addWidget(self.progress_widget)

        parent.addWidget(card)

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
        self.transcript_box.setMinimumHeight(200)
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
            self.status_label.setText("\u26A0 Unsaved changes")
            self.status_label.setStyleSheet(f"color: {c.WARNING};")
        else:
            self.status_label.setText("\u2713 Saved")
            self.status_label.setStyleSheet(f"color: {c.SUCCESS}; font-weight: bold;")
        self._autosave.mark_dirty("voice")

    def _update_status_clean(self):
        self._dirty = False
        self.save_btn.setEnabled(False)
        c = ThemeManager.instance().colors()
        self.status_label.setText("\u2713 Saved")
        self.status_label.setStyleSheet(f"color: {c.SUCCESS}; font-weight: bold;")

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
                self.file_label.setText(f"Selected: {audio_files[0].name}")
                if not self._transcribing:
                    self.transcribe_btn.setEnabled(True)

        self._load_saved_transcript(project_path)

        if self._transcript_text:
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

    def transcribe_audio(self):
        if not self._audio_path or not self.project_name:
            return

        try:
            import whisper
        except ImportError:
            NotificationService.get().error(
                "Whisper not installed. Run: pip install openai-whisper"
            )
            return

        self._transcribing = True
        self.transcribe_btn.setEnabled(False)
        self.upload_btn.setEnabled(False)
        self.progress_widget.setVisible(True)
        self.progress_widget.reset()
        self.progress_widget.set_progress(0, "Loading speech recognition model...", "Preparing", "")

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

    def _cleanup_thread(self):
        if self._worker:
            self._worker.deleteLater()
            self._worker = None
        if self._worker_thread:
            self._worker_thread.deleteLater()
            self._worker_thread = None

    def _on_transcription_done(self, transcript, segments):
        self._transcribing = False
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

        project_data = self.manager.load_project(self.project_name)
        if project_data:
            workflow = project_data.get("workflow_state", {})
            workflow = advance_workflow_state(workflow, "Voice")
            project_data["workflow_state"] = workflow
            self.manager.update_project(self.project_name, project_data)

        self.transcribe_btn.setEnabled(True)
        self.upload_btn.setEnabled(True)
        self._history.record_action(
            self.project_name, "Transcribed",
            f"Generated transcript from audio ({len(segs_out)} segments)"
        )
        NotificationService.get().success("Transcript generated successfully.")
        self._update_parent_sidebar()

    def _update_parent_sidebar(self):
        main = self.window()
        if main and hasattr(main, '_update_sidebar_project') and self.project_name:
            main._update_sidebar_project(self.project_name)

    def _autosave_save(self):
        if not self.project_name:
            return
        text = self.transcript_box.toPlainText()
        project_path = self.manager.PROJECTS_DIR / self.project_name
        fp = project_path / "transcript.json"
        fp.write_text(json.dumps({"text": text}, indent=4), encoding="utf-8")
        self._saved_text = text
        self._update_status_clean()

    def _on_transcription_error(self, error_msg):
        self._transcribing = False
        self.progress_widget.setVisible(False)
        self.transcribe_btn.setEnabled(True)
        self.upload_btn.setEnabled(True)
        NotificationService.get().error(f"Transcription failed: {error_msg}")

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
