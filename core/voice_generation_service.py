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
    ) -> None:
        """Download the ONNX model files if they are not already cached.

        Safe to call multiple times; files that already exist are skipped.

        Args:
            progress_callback: Optional ``(message, percent)`` callable fired
                during each download so callers can update a progress UI.
                ``percent`` is -1 when the total size is unknown.

        Raises:
            RuntimeError: If kokoro-onnx is not installed or the download fails.
        """
        if not self.is_available():
            raise RuntimeError(self.install_instruction())

        _CACHE_DIR.mkdir(parents=True, exist_ok=True)

        for filename, label in (
            (_MODEL_FILE_NAME, "Kokoro ONNX model"),
            (_VOICES_FILE_NAME, "voice data"),
        ):
            dest = _CACHE_DIR / filename
            if dest.exists():
                self._log.info("Voice", f"{label} already cached at {dest}.")
                continue
            url = f"{_MODEL_BASE_URL}/{filename}"
            self._log.info("Voice", f"Downloading {label} from {url} …")
            if progress_callback:
                progress_callback(f"Downloading {label}…", -1)
            self._download_file(url, dest, label, progress_callback)
            self._log.info("Voice", f"{label} saved to {dest}.")

    def _download_file(
        self,
        url: str,
        dest: Path,
        label: str,
        progress_callback: Callable[[str, int], None] | None,
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
    ) -> None:
        """Synthesize *text* and write a WAV file to *output_path*.

        Args:
            text:        The narration to synthesize.
            voice_id:    A Kokoro speaker ID (e.g. ``"af_heart"``).
            speed:       Playback-speed multiplier; 1.0 is natural rate.
            output_path: Destination path; parent directories are created.

        Raises:
            RuntimeError: If the package is missing, the model is not
                downloaded, or synthesis fails.
        """
        wav_bytes = self._synthesize(text, voice_id, speed)
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(wav_bytes)
        self._log.info(
            "Voice",
            f"Generated {len(wav_bytes):,} B WAV → {out.name} "
            f"(voice={voice_id}, speed={speed:.2f})",
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

    def _synthesize(self, text: str, voice_id: str, speed: float) -> bytes:
        """Synthesize *text* and return raw WAV bytes."""
        kokoro = self._get_kokoro()
        try:
            samples, sample_rate = kokoro.create(
                text,
                voice=voice_id,
                speed=speed,
                lang="en-us",
            )
        except Exception as exc:
            raise RuntimeError(
                f"Kokoro synthesis failed (voice={voice_id}): {exc}"
            ) from exc

        return _float32_to_wav_bytes(samples, sample_rate)


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
