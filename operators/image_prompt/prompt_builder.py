from __future__ import annotations

from operators.image_prompt.models import ImagePromptRequest


class ImagePromptBuilder:
    """Builds deterministic image prompt generation requests from structured data."""

    def build(self, request: ImagePromptRequest) -> str:
        storyboard_text = self._normalize_text(request.storyboard_text)
        topic = self._normalize_text(request.topic) or "Untitled"
        language = self._normalize_text(request.language) or "English"

        return (
            "Image Prompt Generation Request\n\n"
            f"Topic:\n{topic}\n\n"
            f"Language:\n{language}\n\n"
            f"Storyboard:\n{storyboard_text}\n\n"
            f"Instructions:\n"
            f"Generate detailed image prompts for each scene in the storyboard above.\n"
            f"Return your response as a JSON array of prompt objects.\n\n"
            f"Each object in the array must have exactly these keys:\n"
            f'- "scene_number": integer (1-based index)\n'
            f'- "timestamp": string in "MM:SS" format (e.g. "00:00", "01:30")\n'
            f'- "prompt_title": string (e.g. "Scene 1 Prompt")\n'
            f'- "full_image_prompt": string containing the complete image prompt\n\n'
            f"The full_image_prompt should include:\n"
            f"Subject, Environment, Composition, Lighting, Camera Angle, Art Style, "
            f"and Negative Prompt.\n\n"
            f"Return ONLY the JSON array. No additional text, no markdown, no explanation."
        )

    @staticmethod
    def _normalize_text(value: object) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        return text
