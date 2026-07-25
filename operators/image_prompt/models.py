from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImagePromptRequest:
    """Structured input for building an image prompt generation request.

    The caller is responsible for providing all data — this operator
    does not access storage, UI, or workflow state.
    """

    storyboard_text: str
    topic: str = ""
    language: str = "English"


class ImagePromptValidationError(ValueError):
    """Raised when an ImagePromptRequest fails validation."""


class ImagePromptGenerationError(RuntimeError):
    """Raised when the AI provider fails to generate image prompt content."""


class ImagePromptParseError(RuntimeError):
    """Raised when the AI response cannot be parsed into valid image prompts."""
