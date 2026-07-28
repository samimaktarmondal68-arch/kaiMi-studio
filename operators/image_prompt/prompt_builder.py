from __future__ import annotations

from operators.image_prompt.models import ImagePromptRequest
from core.prompts import load_all_system_prompts


class ImagePromptBuilder:

    def build(self, request: ImagePromptRequest) -> tuple[str, str]:
        system = load_all_system_prompts()

        script_text = self._normalize_text(request.script_text)
        transcript = self._normalize_text(request.transcript)
        topic = self._normalize_text(request.topic) or "Untitled"
        language = self._normalize_text(request.language) or "English"

        user = (
            f"Generate image prompts for the following educational animation project.\n\n"
            f"Topic: {topic}\n"
            f"Language: {language}\n\n"
            f"Script:\n{script_text}\n\n"
        )

        if transcript:
            user += f"Transcript (with timing):\n{transcript}\n\n"

        if request.timestamps:
            ts_lines = []
            for t in request.timestamps:
                ts_lines.append(f"{t.get('time', '')}: {t.get('text', '')}")
            user += f"Timestamps:\n" + "\n".join(ts_lines) + "\n\n"

        user += (
            f"Generate detailed image prompts for each logical scene or segment. "
            f"Return your response as a JSON array of prompt objects.\n\n"
            f"Each object must have exactly these keys:\n"
            f'- "scene_number": integer\n'
            f'- "timestamp": string in "MM:SS" format\n'
            f'- "prompt_title": short descriptive title\n'
            f'- "full_image_prompt": complete production-ready prompt\n\n'
            f"The full_image_prompt must include:\n"
            f"Subject, Environment, Composition, Lighting, Camera Angle, "
            f"Art Style, Color Palette, Negative Prompt.\n\n"
            f"Return ONLY valid JSON. No markdown, no explanation, no extra text."
        )

        return system, user

    @staticmethod
    def _normalize_text(value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()