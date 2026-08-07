# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Validated script length presets (Sprint 3.4D).

Only the predefined presets below may drive script generation; users never
type arbitrary character counts. Projects persist ``script_min_characters``
and ``script_max_characters``; older projects without them automatically use
the legacy 4500-5000 range.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScriptLengthPreset:
    """A validated script length configuration."""

    name: str
    min_characters: int
    max_characters: int
    estimated_duration: str


SCRIPT_LENGTH_PRESETS: list[ScriptLengthPreset] = [
    ScriptLengthPreset("Short Video", 4500, 5000, "Approx. 3\u20134 minutes"),
    ScriptLengthPreset("Medium Video", 6500, 7000, "Approx. 4\u20135 minutes"),
    ScriptLengthPreset("Long Video", 9500, 10000, "Approx. 6\u20137 minutes"),
    ScriptLengthPreset("Extended Video", 12500, 13000, "Approx. 8\u20139 minutes"),
    ScriptLengthPreset("Very Long Video", 15500, 16000, "Approx. 10\u201311 minutes"),
    ScriptLengthPreset("Documentary Video", 19500, 20000, "Approx. 13\u201314 minutes"),
    ScriptLengthPreset("Deep Dive Video", 24500, 25000, "Approx. 16\u201318 minutes"),
    ScriptLengthPreset("Maximum Video", 39500, 40000, "Approx. 28\u201330 minutes"),
]


DEFAULT_SCRIPT_MIN = 4500
DEFAULT_SCRIPT_MAX = 5000

# Maximum number of model continuation requests used to bring an
# under-length script up to its selected range (Sprint 3.4E).
MAX_SCRIPT_CONTINUATIONS = 4


def find_preset(min_characters: int, max_characters: int) -> ScriptLengthPreset | None:
    """Return the preset matching an exact character range, if any."""
    for preset in SCRIPT_LENGTH_PRESETS:
        if preset.min_characters == min_characters and preset.max_characters == max_characters:
            return preset
    return None


def get_preset(name: str) -> ScriptLengthPreset | None:
    """Return the preset with the given name, if any."""
    for preset in SCRIPT_LENGTH_PRESETS:
        if preset.name == name:
            return preset
    return None


def project_script_bounds(project_data: dict | None) -> tuple[int, int]:
    """Return the stored script bounds for a project.

    Backward compatible: projects without ``script_min_characters`` /
    ``script_max_characters`` default to 4500-5000.
    """
    data = project_data or {}
    min_characters = data.get("script_min_characters")
    max_characters = data.get("script_max_characters")
    if (
        isinstance(min_characters, int)
        and isinstance(max_characters, int)
        and 0 < min_characters <= max_characters
    ):
        return min_characters, max_characters
    return DEFAULT_SCRIPT_MIN, DEFAULT_SCRIPT_MAX


def resolve_preset_bounds(script_min: int, script_max: int) -> tuple[int, int]:
    """Resolve creation-time bounds for a new project.

    An exact preset match is preserved; any other range falls back to the
    default preset so only validated ranges are ever stored.
    """
    preset = find_preset(script_min, script_max)
    if preset is not None:
        return preset.min_characters, preset.max_characters
    return DEFAULT_SCRIPT_MIN, DEFAULT_SCRIPT_MAX


def estimate_duration(min_characters: int, max_characters: int) -> str:
    """Rough duration estimate for ranges that do not match a preset."""
    low = max(1, round(min_characters / 1500))
    high = max(low, round(max_characters / 1500))
    return f"Approx. {low}\u2013{high} minutes"
