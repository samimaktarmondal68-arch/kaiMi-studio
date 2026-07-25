from __future__ import annotations

from operators.script.models import ScriptRequest


class ScriptPromptBuilder:
    """Builds deterministic script prompts from structured request data."""

    LENGTH_HINTS: dict[str, str] = {
        "Short": "a concise script",
        "Medium": "a balanced script",
        "Long": "a detailed script",
    }

    def build(self, request: ScriptRequest) -> str:
        topic = self._normalize_text(request.topic)
        style = self._normalize_text(request.style) or "Educational"
        length = self._normalize_text(request.length) or "Medium"
        tone = self._normalize_text(request.tone) or "Friendly"
        keywords = self._normalize_text(request.keywords) or "the key themes"
        goal = self._normalize_text(request.goal) or "the project goal"
        language = self._normalize_text(request.language) or "English"
        length_hint = self.LENGTH_HINTS.get(length, "a script")

        return (
            "Script Generation Request\n\n"
            f"Title:\n{topic}\n\n"
            f"Style:\n{style}\n\n"
            f"Length:\n{length}\n\n"
            f"Tone:\n{tone}\n\n"
            f"Language:\n{language}\n\n"
            f"Opening:\n"
            f"Introduce {topic} in a {tone.lower()} and engaging way.\n\n"
            f"Body:\n"
            f"Use {keywords} to support the message "
            f"and connect it to {goal}.\n\n"
            f"Conclusion:\n"
            f"Close with a strong call to action "
            f"and a clear takeaway for the audience.\n\n"
            f"Generate {length_hint} for {topic}."
        )

    @staticmethod
    def _normalize_text(value: object) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        return text
