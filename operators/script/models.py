from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScriptRequest:
    topic: str
    platform: str = "Long Form"
    video_type: str = "Educational"
    language: str = "English"
    script_mode: str = "characters"
    script_min: int = 4500
    script_max: int = 5000
    duration_preset: str = ""
    research_sources: str = ""
    keywords: str = ""


class ScriptValidationError(ValueError):
    pass


class ScriptGenerationError(RuntimeError):
    pass