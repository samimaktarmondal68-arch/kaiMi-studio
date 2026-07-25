from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StoryboardRequest:
    """Structured input for building a storyboard generation prompt.

    The caller is responsible for providing all data — this operator
    does not access storage, UI, or workflow state.
    """

    script_text: str
    topic: str = ""
    length: str = "Medium"
    language: str = "English"


class StoryboardValidationError(ValueError):
    """Raised when a StoryboardRequest fails validation."""


class StoryboardGenerationError(RuntimeError):
    """Raised when the AI provider fails to generate storyboard content."""


class StoryboardParseError(RuntimeError):
    """Raised when the AI response cannot be parsed into valid storyboard scenes."""
