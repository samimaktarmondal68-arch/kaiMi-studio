# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
from __future__ import annotations

import json
import re
from typing import Any

from operators.image_prompt.models import ImagePromptParseError


_TIMESTAMP_PATTERN = re.compile(r"^\d{2}:\d{2}$")

_REQUIRED_FIELDS = frozenset({
    "scene_number",
    "timestamp",
    "prompt_title",
    "full_image_prompt",
})

_EXPECTED_TYPES: dict[str, type] = {
    "scene_number": int,
    "timestamp": str,
    "prompt_title": str,
    "full_image_prompt": str,
}


class ImagePromptParser:
    """Parses raw AI image prompt response into structured prompt data.

    The parser expects the AI response to contain a JSON array of prompt
    objects. Each object must have the exact required fields with the
    correct types.

    Raises ImagePromptParseError on any validation failure.
    """

    def parse(self, raw_response: str) -> list[dict]:
        """Parse and validate raw AI response into prompt dicts.

        Args:
            raw_response: Raw text from the AI provider.

        Returns:
            Validated list of prompt dicts matching the UI contract.

        Raises:
            ImagePromptParseError: If JSON is malformed, schema is wrong,
                types are incorrect, timestamps are invalid, or required
                fields are empty.
        """
        if not raw_response or not raw_response.strip():
            raise ImagePromptParseError("AI response is empty.")

        json_str = self._extract_json(raw_response)
        data = self._parse_json(json_str)
        prompts = self._validate_schema(data)
        self._validate_types(prompts)
        self._validate_timestamps(prompts)
        self._validate_non_empty(prompts)
        return prompts

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
            raise ImagePromptParseError(
                f"Invalid JSON: {exc.msg} "
                f"(line {exc.lineno}, column {exc.colno})"
            ) from exc

    def _validate_schema(self, data: Any) -> list[dict]:
        """Validate that data is a list of dicts with required fields."""
        if not isinstance(data, list):
            raise ImagePromptParseError(
                f"Expected a JSON array, got {type(data).__name__}."
            )

        if len(data) == 0:
            raise ImagePromptParseError("Prompt array is empty.")

        prompts: list[dict] = []
        for index, item in enumerate(data):
            if not isinstance(item, dict):
                raise ImagePromptParseError(
                    f"Prompt at index {index} is not an object "
                    f"(got {type(item).__name__})."
                )

            missing = _REQUIRED_FIELDS - item.keys()
            if missing:
                raise ImagePromptParseError(
                    f"Prompt at index {index} is missing fields: "
                    f"{', '.join(sorted(missing))}."
                )

            extra = item.keys() - _REQUIRED_FIELDS
            if extra:
                raise ImagePromptParseError(
                    f"Prompt at index {index} has unexpected fields: "
                    f"{', '.join(sorted(extra))}."
                )

            prompts.append(item)

        return prompts

    def _validate_types(self, prompts: list[dict]) -> None:
        """Validate that all fields have the correct types."""
        for index, prompt in enumerate(prompts):
            for field, expected_type in _EXPECTED_TYPES.items():
                value = prompt[field]
                if not isinstance(value, expected_type):
                    raise ImagePromptParseError(
                        f"Prompt at index {index}, field '{field}': "
                        f"expected {expected_type.__name__}, "
                        f"got {type(value).__name__}."
                    )

    def _validate_timestamps(self, prompts: list[dict]) -> None:
        """Validate that all timestamps are in MM:SS format."""
        for index, prompt in enumerate(prompts):
            timestamp = prompt["timestamp"]
            if not _TIMESTAMP_PATTERN.match(timestamp):
                raise ImagePromptParseError(
                    f"Prompt at index {index}, field 'timestamp': "
                    f"invalid format '{timestamp}'. "
                    f"Expected MM:SS (e.g. '00:00', '01:30')."
                )

    def _validate_non_empty(self, prompts: list[dict]) -> None:
        """Validate that prompt_title and full_image_prompt are not empty."""
        for index, prompt in enumerate(prompts):
            prompt_title = prompt["prompt_title"]
            if not prompt_title.strip():
                raise ImagePromptParseError(
                    f"Prompt at index {index}, field 'prompt_title': "
                    f"must not be empty."
                )

            full_image_prompt = prompt["full_image_prompt"]
            if not full_image_prompt.strip():
                raise ImagePromptParseError(
                    f"Prompt at index {index}, field 'full_image_prompt': "
                    f"must not be empty."
                )
