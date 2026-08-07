# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Local Whisper transcription service (Version 1).

Runs faster-whisper fully on-device. The Whisper model is loaded once and
reused across transcriptions; it is never reloaded per audio file.

The service never falls back to a hosted transcription API. If local Whisper
cannot be initialized, the caller receives a clear error explaining why.
"""

from __future__ import annotations

import importlib.util
import threading

from core.logger import get_logger
from core.settings import AppSettings
from core.transcript_formatter import TranscriptFormatter

#: Model sizes faster-whisper supports directly.
WHISPER_MODELS = ("tiny", "base", "small", "medium", "large-v3")

#: Default model used when no model is configured.
DEFAULT_MODEL = "small"

#: AppSettings key that stores the configured model name.
MODEL_SETTINGS_KEY = "whisper_model"

#: Package required to run local transcription (pip distribution name).
PACKAGE_NAME = "faster-whisper"

#: Importable module name (pip name has a hyphen, the module does not).
IMPORT_NAME = "faster_whisper"


def _collapse_whitespace(text: str) -> str:
    """Collapse all whitespace runs to single spaces and strip edges."""
    return " ".join(str(text).split())


def format_transcript(segments: list[dict]) -> str:
    """Format raw Whisper segments into the canonical [M:SS] block transcript.

    Delegates to :class:`~core.transcript_formatter.TranscriptFormatter`.
    Each segment becomes one ``[M:SS] narration`` block; blocks are separated
    by exactly one blank line. Light cleanup only — the narration is never
    summarised or rewritten.
    """
    return TranscriptFormatter().format(segments)


class TranscriptionService:
    """Transcribe audio locally with faster-whisper, reusing the loaded model."""

    # Class-level cache so the model is shared across page instances and
    # background workers for the lifetime of the application.
    _model = None
    _model_name: str | None = None
    _model_lock = threading.Lock()

    def __init__(self) -> None:
        self._log = get_logger()

    @staticmethod
    def is_available() -> bool:
        """Return True when the faster-whisper package is importable."""
        return importlib.util.find_spec(IMPORT_NAME) is not None

    @staticmethod
    def install_instruction() -> str:
        """Return the message shown when faster-whisper is not installed."""
        return (
            f"The local Whisper engine ({PACKAGE_NAME}) is not installed, so "
            f"audio transcription is unavailable.\n\n"
            f"Install it with:\n\n"
            f"    pip install {PACKAGE_NAME}\n\n"
            f"Then restart KaiMi Studio. No audio is ever sent to a remote "
            f"service; transcription runs entirely on this computer."
        )

    def get_configured_model(self) -> str:
        """Return the configured model name, falling back to the default."""
        configured = AppSettings().get(MODEL_SETTINGS_KEY, DEFAULT_MODEL)
        name = str(configured or DEFAULT_MODEL).strip().lower()
        return name if name in WHISPER_MODELS else DEFAULT_MODEL

    def set_model(self, model_name: str) -> None:
        """Persist a configured model name, validating it against known sizes."""
        name = str(model_name or "").strip().lower()
        if name not in WHISPER_MODELS:
            raise ValueError(
                f"Unknown Whisper model '{model_name}'. "
                f"Choose from: {', '.join(WHISPER_MODELS)}."
            )
        AppSettings().set(MODEL_SETTINGS_KEY, name)

    def _load_model(self, model_name: str):
        """Import faster-whisper and load the requested model once.

        The loaded model is stored on the class so every service instance and
        background worker shares it for the lifetime of the application.
        """
        cls = type(self)
        with cls._model_lock:
            if cls._model is not None and cls._model_name == model_name:
                return cls._model
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise RuntimeError(self.install_instruction()) from exc

            self._log.info("Voice", f"Loading local Whisper model '{model_name}'...")
            try:
                model = WhisperModel(model_name, device="auto", compute_type="int8")
            except Exception as exc:
                self._log.error("Voice", f"Failed to initialize Whisper model: {exc}", exc)
                raise RuntimeError(
                    f"Local Whisper could not be initialized with model "
                    f"'{model_name}'. Error: {exc}"
                ) from exc
            cls._model = model
            cls._model_name = model_name
            self._log.info("Voice", f"Local Whisper model '{model_name}' ready.")
            return cls._model

    def transcribe(self, audio_path: str, model_name: str | None = None) -> tuple[str, list[dict]]:
        """Transcribe an audio file with local Whisper.

        Args:
            audio_path: Path to an audio file (mp3/wav/m4a).
            model_name: Optional override; defaults to the configured model.

        Returns:
            (transcript_text, segments) where transcript_text is the formatted
            narration and each segment is {"start", "end", "text", "time"}.

        Raises:
            RuntimeError: When faster-whisper is missing, the model cannot be
                initialized, or no speech was detected. There is no fallback.
        """
        if not self.is_available():
            raise RuntimeError(self.install_instruction())

        name = model_name or self.get_configured_model()
        model = self._load_model(name)

        try:
            with type(self)._model_lock:
                segment_iter, _info = model.transcribe(
                    audio_path,
                    vad_filter=True,
                    beam_size=5,
                )
                raw_segments = list(segment_iter)
        except Exception as exc:
            self._log.error("Voice", f"Transcription failed: {exc}", exc)
            raise RuntimeError(f"Local transcription failed: {exc}") from exc

        if not raw_segments:
            raise RuntimeError(
                "No speech was detected in the audio file. Use a file that "
                "contains clear spoken narration."
            )

        cleaned = [
            {"start": float(seg.start or 0.0), "end": float(seg.end or 0.0),
             "text": _collapse_whitespace(seg.text)}
            for seg in raw_segments
        ]
        transcript = format_transcript(cleaned)

        segments_out = []
        for seg in cleaned:
            start = seg["start"]
            total = int(start)
            segments_out.append({
                "start": start,
                "end": seg["end"],
                "text": seg["text"],
                "time": f"{total // 60:02d}:{total % 60:02d}",
            })

        self._log.info("Voice", f"Transcribed {len(segments_out)} segments "
                                f"({len(transcript)} chars) with model '{name}'.")
        return transcript, segments_out


_service_instance: TranscriptionService | None = None


def get_transcription_service() -> TranscriptionService:
    """Return the shared transcription service singleton."""
    global _service_instance
    if _service_instance is None:
        _service_instance = TranscriptionService()
    return _service_instance
