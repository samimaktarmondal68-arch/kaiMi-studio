from __future__ import annotations

from dataclasses import dataclass

from core.script_lengths import DEFAULT_SCRIPT_MAX, DEFAULT_SCRIPT_MIN


@dataclass(frozen=True)
class ScriptRequest:
    topic: str
    platform: str = "Long Form"
    video_type: str = "Educational"
    language: str = "English"
    script_mode: str = "characters"
    script_min: int = DEFAULT_SCRIPT_MIN
    script_max: int = DEFAULT_SCRIPT_MAX
    duration_preset: str = ""
    research_sources: str = ""
    keywords: str = ""


class ScriptValidationError(ValueError):
    pass


class ScriptGenerationError(RuntimeError):
    pass