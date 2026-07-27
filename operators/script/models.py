# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScriptRequest:
    """Structured input for building a script generation prompt.

    The caller is responsible for providing all data — this operator
    does not access storage, UI, or workflow state.
    """

    topic: str
    style: str = "Educational"
    length: str = "Medium"
    tone: str = "Friendly"
    keywords: str = ""
    goal: str = ""
    language: str = "English"


class ScriptValidationError(ValueError):
    """Raised when a ScriptRequest fails validation."""


class ScriptGenerationError(RuntimeError):
    """Raised when the AI provider fails to generate script content."""
