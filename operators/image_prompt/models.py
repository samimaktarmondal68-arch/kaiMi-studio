from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImagePromptRequest:
    script_text: str
    transcript: str = ""
    timestamps: list[dict] | None = None
    topic: str = ""
    language: str = "English"


class ImagePromptValidationError(ValueError):
    pass


class ImagePromptGenerationError(RuntimeError):
    pass


class ImagePromptParseError(RuntimeError):
    pass