# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Local TTS service using Kokoro-ONNX (Sprint 3.3A).

Engine selection — Kokoro-ONNX over alternatives:

  Kokoro (hexgrad/kokoro, PyTorch)
    Disqualified: PyTorch pulls in ~2 GB of binaries. Most users do not
    have it and a silent install at runtime would be unacceptable.

  Piper TTS (rhasspy/piper-tts)
    Acceptable quality, but noticeably lower fidelity than Kokoro-82M on
    English narration. Voice model management is also more complex.

  Kokoro-ONNX (thewh1teagle/kokoro-onnx)  ← SELECTED
    Identical Kokoro-82M model quality; ONNX Runtime replaces PyTorch.
    - onnxruntime is already a transitive dep of faster-whisper, so no new
      heavy dependency is introduced.
    - ~300 MB one-time model download instead of ~2 GB for a torch stack.
    - ONNX Runtime is heavily optimised for CPU; suitable for 3-5 min
      educational narration without a GPU.
    - pip install kokoro-onnx adds only lightweight deps (onnxruntime,
      numpy, phonemizer).  No API, no network calls after first download.
    - Cross-platform: Windows, macOS, Linux.

Voice profiles are eight curated speakers mapped to Kokoro native IDs
selected for natural English educational narration.
"""

from __future__ import annotations

import importlib.util
import io
import threading
import time
import urllib.request
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from core.logger import get_logger

# ---------------------------------------------------------------------------
# Preview text
# ---------------------------------------------------------------------------

PREVIEW_TEXT = (
    "Hello! This is a preview of the selected voice. Welcome to KaiMi Studio."
)

# ---------------------------------------------------------------------------
# Package constants
# ---------------------------------------------------------------------------

PACKAGE_NAME = "kokoro-onnx"
IMPORT_NAME = "kokoro_onnx"

# Model files — v1.0 release (compatible with kokoro-onnx 0.4.x).
# INT8 quantisation is used for the ONNX model: it runs on CPU without a GPU,
# reduces the download to ~83 MB (vs ~310 MB for fp32), and is perceptually
# indistinguishable from full-precision for speech synthesis.
_MODEL_BASE_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
)
_MODEL_FILE_NAME = "kokoro-v1.0.int8.onnx"
_VOICES_FILE_NAME = "voices-v1.0.bin"

# Local cache mirrors how faster-whisper stores its ONNX weights.
_CACHE_DIR = Path.home() / ".cache" / "kaimi" / "kokoro"

# ---------------------------------------------------------------------------
# Voice profiles
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VoiceProfile:
    id: str           # Kokoro native speaker ID passed to kokoro.create()
    name: str         # Display name shown on the voice card
    description: str  # One-line description shown on the voice card


#: Exactly eight curated voices — do not add more without a UI change.
VOICE_PROFILES: tuple[VoiceProfile, ...] = (
    VoiceProfile("af_heart",    "Emma",   "Calm Documentary Narrator"),
    VoiceProfile("am_michael",  "James",  "Deep Educational Voice"),
    VoiceProfile("af_bella",    "Sophia", "Warm Storytelling"),
    VoiceProfile("am_adam",     "Alex",   "Energetic Explainer"),
    VoiceProfile("bm_george",   "Daniel", "Professional Presenter"),
    VoiceProfile("af_sarah",    "Olivia", "Soft Educational Narration"),
    VoiceProfile("bm_lewis",    "Ethan",  "Confident Documentary Voice"),
    VoiceProfile("bf_isabella", "Mia",    "Friendly Conversational Narrator"),
)

DEFAULT_VOICE_ID = "af_heart"
DEFAULT_SPEED = 1.0

# ---------------------------------------------------------------------------
# Generation diagnostics (RC-6)
# ---------------------------------------------------------------------------

#: Pipeline stage keys reported through the generation progress callback.
STAGE_MODEL_INIT = "model_init"
STAGE_TEXT_PREP = "text_prep"
STAGE_SYNTHESIS = "synthesis"
STAGE_WAV_ENCODE = "wav_encode"
STAGE_FILE_SAVE = "file_save"

#: Human-readable label shown in the UI for each pipeline stage.
STAGE_MESSAGES: dict[str, str] = {
    STAGE_MODEL_INIT: "Loading Voice Model...",
    STAGE_TEXT_PREP: "Preparing Script...",
    STAGE_SYNTHESIS: "Synthesizing Narration...",
    STAGE_WAV_ENCODE: "Encoding WAV...",
    STAGE_FILE_SAVE: "Saving Audio...",
}

#: Fraction of overall progress attributed to each completed stage. These are
#: real pipeline positions, not estimates — the progress bar lands on the
#: current stage and stays there (with the elapsed timer ticking) until the
#: stage finishes.
STAGE_FRACTIONS: dict[str, float] = {
    STAGE_MODEL_INIT: 0.05,
    STAGE_TEXT_PREP: 0.15,
    STAGE_SYNTHESIS: 0.35,
    STAGE_WAV_ENCODE: 0.90,
    STAGE_FILE_SAVE: 0.97,
}


class VoiceGenerationCancelled(Exception):
    """Raised when a running voice generation is cancelled by the user.

    The worker checks the shared cancel event between pipeline stages and
    raises this so the caller can distinguish an intentional stop from a
    real failure. The project (script, voice prefs, existing transcript) is
    left untouched.
    """


class _StageClock:
    """Measure named pipeline stages and render a timing summary.

    Marks are cumulative timestamps; the summary renders per-stage deltas so
    each line is the real duration of that stage.
    """

    def __init__(self) -> None:
        self._t0 = time.perf_counter()
        self._stages: list[tuple[str, float]] = []

    def mark(self, name: str) -> None:
        """Record the cumulative elapsed time under *name*."""
        self._stages.append((name, time.perf_counter() - self._t0))

    def summary(self, header: str = "") -> str:
        """Render one line per stage with the real per-stage duration."""
        lines: list[str] = []
        previous = 0.0
        for name, cumulative in self._stages:
            lines.append(f"{name:<24} {cumulative - previous:8.2f}s")
            previous = cumulative
        total = self._stages[-1][1] if self._stages else 0.0
        lines.append(f"{'Total':<24} {total:8.2f}s")
        body = "\n".join(lines)
        return f"{header}\n{body}" if header else body


def _normalize_text(text: str) -> str:
    """Collapse whitespace runs to single spaces (TTS-friendly prep).

    This is the measurable "text preprocessing" stage. It never rewrites or
    summarises narration — only normalises whitespace for the engine.
    """
    return " ".join(str(text).split())


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class VoiceGenerationService:
    """Generate speech locally with Kokoro-ONNX.

    The ONNX model is loaded once at class level and reused for the lifetime
    of the application, mirroring how TranscriptionService handles Whisper.
    All public methods are safe to call from background threads.
    """

    # Class-level singleton — shared across all instances and worker threads.
    _kokoro = None
    _model_lock = threading.Lock()

    def __init__(self) -> None:
        self._log = get_logger()

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    @staticmethod
    def is_available() -> bool:
        """Return True when the kokoro-onnx package is importable."""
        return importlib.util.find_spec(IMPORT_NAME) is not None

    @staticmethod
    def install_instruction() -> str:
        """Return the message shown when kokoro-onnx is not installed."""
        return (
            f"The local TTS engine ({PACKAGE_NAME}) is not installed, so "
            f"voice generation is unavailable.\n\n"
            f"Install it with:\n\n"
            f"    pip install {PACKAGE_NAME}\n\n"
            f"Then restart KaiMi Studio. Voice generation runs entirely on "
            f"this computer — no API key or internet connection is required "
            f"after the one-time model download (~300 MB)."
        )

    def is_model_ready(self) -> bool:
        """Return True when the ONNX model files are present in the cache."""
        return (
            (_CACHE_DIR / _MODEL_FILE_NAME).exists()
            and (_CACHE_DIR / _VOICES_FILE_NAME).exists()
        )

    # ------------------------------------------------------------------
    # Voice catalogue
    # ------------------------------------------------------------------

    def get_available_voices(self) -> list[VoiceProfile]:
        """Return the eight curated voice profiles."""
        return list(VOICE_PROFILES)

    def get_voice_by_id(self, voice_id: str) -> VoiceProfile | None:
        """Look up a voice profile by its Kokoro speaker ID."""
        for v in VOICE_PROFILES:
            if v.id == voice_id:
                return v
        return None

    # ------------------------------------------------------------------
    # Model management
    # ------------------------------------------------------------------

    def ensure_model_ready(
        self,
        progress_callback: Callable[[str, int], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        """Download the ONNX model files if they are not already cached.

        Safe to call multiple times; files that already exist are skipped.

        Args:
            progress_callback: Optional ``(message, percent)`` callable fired
                during each download so callers can update a progress UI.
                ``percent`` is -1 when the total size is unknown.
            cancel_event: Optional shared ``threading.Event``; when set the
                download stops early and ``VoiceGenerationCancelled`` is
                raised.

        Raises:
            RuntimeError: If kokoro-onnx is not installed or the download fails.
            VoiceGenerationCancelled: If *cancel_event* was set mid-download.
        """
        if not self.is_available():
            raise RuntimeError(self.install_instruction())

        _CACHE_DIR.mkdir(parents=True, exist_ok=True)

        for filename, label in (
            (_MODEL_FILE_NAME, "Kokoro ONNX model"),
            (_VOICES_FILE_NAME, "voice data"),
        ):
            self._raise_if_cancelled(cancel_event)
            dest = _CACHE_DIR / filename
            if dest.exists():
                self._log.info("Voice", f"{label} already cached at {dest}.")
                continue
            url = f"{_MODEL_BASE_URL}/{filename}"
            self._log.info("Voice", f"Downloading {label} from {url} …")
            if progress_callback:
                progress_callback(f"Downloading {label}…", -1)
            self._download_file(url, dest, label, progress_callback, cancel_event)
            self._log.info("Voice", f"{label} saved to {dest}.")

    def _download_file(
        self,
        url: str,
        dest: Path,
        label: str,
        progress_callback: Callable[[str, int], None] | None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        """Download *url* to *dest*, writing via a .tmp file for atomicity."""
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "KaiMi-Studio/1.0"},
            )
            with urllib.request.urlopen(req, timeout=120) as response:
                total = int(response.headers.get("Content-Length") or 0)
                chunk_size = 65_536  # 64 KB
                downloaded = 0
                with tmp.open("wb") as out:
                    while True:
                        self._raise_if_cancelled(cancel_event)
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        out.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total > 0:
                            pct = int(downloaded * 100 / total)
                            progress_callback(
                                f"Downloading {label}… {pct}%", pct
                            )
            tmp.rename(dest)
        except VoiceGenerationCancelled:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            raise
        except Exception as exc:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            raise RuntimeError(
                f"Failed to download {label} from {url}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate_preview(
        self,
        voice_id: str = DEFAULT_VOICE_ID,
        speed: float = DEFAULT_SPEED,
    ) -> bytes:
        """Generate a short preview clip in memory.

        Uses a fixed sentence so the preview is fast and reproducible.

        Returns:
            Raw WAV bytes (16-bit PCM, mono, 24 kHz) ready for playback or
            writing to disk.

        Raises:
            RuntimeError: If the package is missing, the model is not
                downloaded, or synthesis fails.
        """
        return self._synthesize(PREVIEW_TEXT, voice_id, speed)

    def generate_to_file(
        self,
        text: str,
        voice_id: str,
        speed: float,
        output_path: str | Path,
        progress_callback: Callable[[str, str, float], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        """Synthesize *text* and write a WAV file to *output_path*.

        Args:
            text:        The narration to synthesize.
            voice_id:    A Kokoro speaker ID (e.g. ``"af_heart"``).
            speed:       Playback-speed multiplier; 1.0 is natural rate.
            output_path: Destination path; parent directories are created.
            progress_callback: Optional ``(stage, message, fraction)`` callable
                fired when each pipeline stage completes (model init, text
                prep, synthesis, WAV encoding, file save) so the UI can show
                the real current stage and its progress fraction.
            cancel_event: Optional shared ``threading.Event``; when set the
                generation stops at the next stage boundary and
                ``VoiceGenerationCancelled`` is raised.

        Raises:
            RuntimeError: If the package is missing, the model is not
                downloaded, or synthesis fails.
            VoiceGenerationCancelled: If *cancel_event* was set mid-run.
        """
        self._raise_if_cancelled(cancel_event)
        wav_bytes, clock = self._synthesize_instrumented(
            text, voice_id, speed, progress_callback, cancel_event
        )
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        self._raise_if_cancelled(cancel_event)
        out.write_bytes(wav_bytes)
        clock.mark(STAGE_FILE_SAVE)  # measure after the actual write
        if progress_callback:
            progress_callback(
                STAGE_FILE_SAVE,
                STAGE_MESSAGES[STAGE_FILE_SAVE],
                STAGE_FRACTIONS[STAGE_FILE_SAVE],
            )
        self._log.info(
            "Voice",
            f"Generated {len(wav_bytes):,} B WAV → {out.name} "
            f"(voice={voice_id}, speed={speed:.2f})",
        )
        self._log.info(
            "Voice",
            clock.summary(
                f"Stage timings — voice={voice_id}, speed={speed:.2f}, "
                f"chars={len(text)}, output={out.name}"
            ),
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_kokoro(self):
        """Lazy-load the Kokoro ONNX model (class-level singleton, thread-safe)."""
        cls = type(self)
        with cls._model_lock:
            if cls._kokoro is not None:
                return cls._kokoro
            if not self.is_available():
                raise RuntimeError(self.install_instruction())
            if not self.is_model_ready():
                raise RuntimeError(
                    "Kokoro model files are not downloaded yet. "
                    "Call ensure_model_ready() first, then retry."
                )
            try:
                from kokoro_onnx import Kokoro  # type: ignore[import]

                model_path = str(_CACHE_DIR / _MODEL_FILE_NAME)
                voices_path = str(_CACHE_DIR / _VOICES_FILE_NAME)
                self._log.info("Voice", "Loading Kokoro ONNX model…")
                cls._kokoro = Kokoro(model_path, voices_path)
                self._log.info("Voice", "Kokoro ONNX model ready.")
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to load Kokoro ONNX model: {exc}"
                ) from exc
            return cls._kokoro

    def _synthesize(
        self,
        text: str,
        voice_id: str,
        speed: float,
        progress_callback: Callable[[str, str, float], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> bytes:
        """Synthesize *text* and return raw WAV bytes.

        Thin wrapper for previews; ``generate_to_file`` uses the instrumented
        variant so it can also time the file-save stage.
        """
        wav_bytes, _clock = self._synthesize_instrumented(
            text, voice_id, speed, progress_callback, cancel_event
        )
        return wav_bytes

    def _synthesize_instrumented(
        self,
        text: str,
        voice_id: str,
        speed: float,
        progress_callback: Callable[[str, str, float], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> tuple[bytes, _StageClock]:
        """Synthesize *text*, timing and reporting every real pipeline stage.

        Stages measured: model initialization, text preprocessing, audio
        synthesis (which internally includes phonemisation + tokenisation,
        not separately reachable through the Kokoro public API), and WAV
        encoding. Durations are actual wall-clock measurements.

        Returns:
            (wav_bytes, clock) where *clock* holds the measured stage timings.
        """
        clock = _StageClock()

        def _run_stage(stage: str, work: Callable[[], object]):
            self._raise_if_cancelled(cancel_event)
            result = work()
            clock.mark(stage)
            if progress_callback:
                progress_callback(
                    stage, STAGE_MESSAGES[stage], STAGE_FRACTIONS[stage]
                )
            return result

        kokoro = _run_stage(STAGE_MODEL_INIT, self._get_kokoro)
        prepared = _run_stage(STAGE_TEXT_PREP, lambda: _normalize_text(text))
        samples, sample_rate = _run_stage(
            STAGE_SYNTHESIS,
            lambda: self._create(kokoro, prepared, voice_id, speed),
        )
        wav_bytes = _run_stage(
            STAGE_WAV_ENCODE,
            lambda: _float32_to_wav_bytes(samples, sample_rate),
        )
        return wav_bytes, clock

    @staticmethod
    def _create(kokoro, text: str, voice_id: str, speed: float):
        """Call the Kokoro engine, wrapping failures in a clear RuntimeError."""
        try:
            return kokoro.create(
                text,
                voice=voice_id,
                speed=speed,
                lang="en-us",
            )
        except Exception as exc:
            raise RuntimeError(
                f"Kokoro synthesis failed (voice={voice_id}): {exc}"
            ) from exc

    @staticmethod
    def _raise_if_cancelled(cancel_event: threading.Event | None) -> None:
        """Raise VoiceGenerationCancelled when the shared event is set."""
        if cancel_event is not None and cancel_event.is_set():
            raise VoiceGenerationCancelled(
                "Voice generation cancelled by the user."
            )


# ---------------------------------------------------------------------------
# WAV encoding helper (stdlib only — no soundfile dependency)
# ---------------------------------------------------------------------------


def _float32_to_wav_bytes(samples, sample_rate: int) -> bytes:
    """Convert a float32 numpy array to in-memory 16-bit PCM WAV bytes.

    Uses only the Python standard library so no extra packages are needed.
    """
    import numpy as np

    pcm = (np.clip(samples, -1.0, 1.0) * 32_767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)          # 16-bit → 2 bytes per sample
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Module-level singleton (matches pattern used by TranscriptionService)
# ---------------------------------------------------------------------------

_service_instance: VoiceGenerationService | None = None


def get_voice_generation_service() -> VoiceGenerationService:
    """Return the shared VoiceGenerationService singleton."""
    global _service_instance
    if _service_instance is None:
        _service_instance = VoiceGenerationService()
    return _service_instance
