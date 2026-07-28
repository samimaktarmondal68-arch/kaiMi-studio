from __future__ import annotations

from operators.script.models import ScriptRequest
from core.prompts import load_all_system_prompts


class ScriptPromptBuilder:

    def build(self, request: ScriptRequest) -> tuple[str, str]:
        system = load_all_system_prompts()

        topic = self._normalize_text(request.topic)
        platform = self._normalize_text(request.platform) or "Long Form"
        video_type = self._normalize_text(request.video_type) or "Educational"
        language = self._normalize_text(request.language) or "English"
        sources = self._normalize_text(request.research_sources)
        keywords = self._normalize_text(request.keywords)

        target_instruction = ""
        if request.script_mode == "characters":
            target_instruction = (
                f"The final script MUST be between {request.script_min} and {request.script_max} characters. "
                f"Count the characters precisely. If needed, expand or compress the script "
                f"until it falls within this range."
            )
        else:
            dur = request.duration_preset
            if dur:
                target_instruction = (
                    f"The script must fit a target duration of {dur}. "
                    f"Estimate the character count based on speaking rate (~900 characters per minute). "
                    f"Generate the script to match this duration."
                )

        user = (
            f"Generate a {video_type.lower()} script in {language}.\n\n"
            f"Topic: {topic}\n"
            f"Platform: {platform}\n"
            f"Video Type: {video_type}\n\n"
            f"{'Research Sources: ' + sources if sources else ''}\n"
            f"{'Keywords: ' + keywords if keywords else ''}\n\n"
            f"{target_instruction}\n\n"
            f"Return ONLY the script text. No commentary, no explanation, no markdown formatting."
        )

        return system, user

    @staticmethod
    def _normalize_text(value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()