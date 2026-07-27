# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
from __future__ import annotations

import json
import re
from typing import Any

from operators.storyboard.models import StoryboardParseError


_TIMESTAMP_PATTERN = re.compile(r"^\d{2}:\d{2}$")

_REQUIRED_FIELDS = frozenset({
    "scene_number",
    "timestamp",
    "narration",
    "visual_description",
    "camera_direction",
    "on_screen_text",
})

_EXPECTED_TYPES: dict[str, type] = {
    "scene_number": int,
    "timestamp": str,
    "narration": str,
    "visual_description": str,
    "camera_direction": str,
    "on_screen_text": str,
}


class StoryboardParser:
    """Parses raw AI storyboard response into structured scene data.

    The parser expects the AI response to contain a JSON array of scene
    objects. Each object must have the exact required fields with the
    correct types.

    Raises StoryboardParseError on any validation failure.
    """

    def parse(self, raw_response: str) -> list[dict]:
        """Parse and validate raw AI response into scene dicts.

        Args:
            raw_response: Raw text from the AI provider.

        Returns:
            Validated list of scene dicts matching the UI contract.

        Raises:
            StoryboardParseError: If JSON is malformed, schema is wrong,
                types are incorrect, or timestamps are invalid.
        """
        if not raw_response or not raw_response.strip():
            raise StoryboardParseError("AI response is empty.")

        json_str = self._extract_json(raw_response)
        data = self._parse_json(json_str)
        scenes = self._validate_schema(data)
        self._validate_types(scenes)
        self._validate_timestamps(scenes)
        return scenes

    def _extract_json(self, text: str) -> str:
        """Extract JSON array from text.

        Handles cases where the AI includes text before or after the JSON.
        """
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            return match.group(0)
        return text.strip()

    def _parse_json(self, json_str: str) -> Any:
        """Parse JSON string into Python object."""
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise StoryboardParseError(
                f"Invalid JSON: {exc.msg} "
                f"(line {exc.lineno}, column {exc.colno})"
            ) from exc

    def _validate_schema(self, data: Any) -> list[dict]:
        """Validate that data is a list of dicts with required fields."""
        if not isinstance(data, list):
            raise StoryboardParseError(
                f"Expected a JSON array, got {type(data).__name__}."
            )

        if len(data) == 0:
            raise StoryboardParseError("Scene array is empty.")

        scenes: list[dict] = []
        for index, item in enumerate(data):
            if not isinstance(item, dict):
                raise StoryboardParseError(
                    f"Scene at index {index} is not an object "
                    f"(got {type(item).__name__})."
                )

            missing = _REQUIRED_FIELDS - item.keys()
            if missing:
                raise StoryboardParseError(
                    f"Scene at index {index} is missing fields: "
                    f"{', '.join(sorted(missing))}."
                )

            extra = item.keys() - _REQUIRED_FIELDS
            if extra:
                raise StoryboardParseError(
                    f"Scene at index {index} has unexpected fields: "
                    f"{', '.join(sorted(extra))}."
                )

            scenes.append(item)

        return scenes

    def _validate_types(self, scenes: list[dict]) -> None:
        """Validate that all fields have the correct types."""
        for index, scene in enumerate(scenes):
            for field, expected_type in _EXPECTED_TYPES.items():
                value = scene[field]
                if not isinstance(value, expected_type):
                    raise StoryboardParseError(
                        f"Scene at index {index}, field '{field}': "
                        f"expected {expected_type.__name__}, "
                        f"got {type(value).__name__}."
                    )

    def _validate_timestamps(self, scenes: list[dict]) -> None:
        """Validate that all timestamps are in MM:SS format."""
        for index, scene in enumerate(scenes):
            timestamp = scene["timestamp"]
            if not _TIMESTAMP_PATTERN.match(timestamp):
                raise StoryboardParseError(
                    f"Scene at index {index}, field 'timestamp': "
                    f"invalid format '{timestamp}'. "
                    f"Expected MM:SS (e.g. '00:00', '01:30')."
                )
