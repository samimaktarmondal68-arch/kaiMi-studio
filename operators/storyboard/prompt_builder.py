# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
from __future__ import annotations

from operators.storyboard.models import StoryboardRequest


class StoryboardPromptBuilder:
    """Builds deterministic storyboard prompts from structured request data."""

    SCENE_COUNTS: dict[str, int] = {
        "Short": 8,
        "Medium": 10,
        "Long": 12,
    }

    def build(self, request: StoryboardRequest) -> str:
        script_text = self._normalize_text(request.script_text)
        topic = self._normalize_text(request.topic) or "Untitled"
        length = self._normalize_text(request.length) or "Medium"
        language = self._normalize_text(request.language) or "English"
        scene_count = self.SCENE_COUNTS.get(length, 10)

        return (
            "Storyboard Generation Request\n\n"
            f"Topic:\n{topic}\n\n"
            f"Language:\n{language}\n\n"
            f"Length:\n{length} ({scene_count} scenes)\n\n"
            f"Script:\n{script_text}\n\n"
            f"Instructions:\n"
            f"Create a detailed storyboard outline for the above script.\n"
            f"Return exactly {scene_count} scenes as a JSON array.\n\n"
            f"Each object in the array must have exactly these keys:\n"
            f'- "scene_number": integer (1-based index)\n'
            f'- "timestamp": string in "MM:SS" format (e.g. "00:00", "01:30")\n'
            f'- "narration": string describing the spoken dialogue or narration\n'
            f'- "visual_description": string describing the visual elements\n'
            f'- "camera_direction": string describing camera movement\n'
            f'- "on_screen_text": string for any text displayed on screen\n\n'
            f"Return ONLY the JSON array. No additional text, no markdown, no explanation."
        )

    @staticmethod
    def _normalize_text(value: object) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        return text
