from __future__ import annotations

from operators.image_prompt.models import ImagePromptRequest
from core.prompts import load_all_system_prompts

#: Production Stage 7 reference template embedded in every generation request.
#: The model must reproduce this exact writing style: timestamp line first,
#: then one continuous natural-language paragraph opening with
#: "Hand-drawn 2D doodle cartoon animation, ..." that flows through style,
#: character, environment, action, camera, narration focus, negative wording,
#: aspect ratio, and the KaiMi style tag — with no labels or metadata.
PROMPT_TEMPLATE = (
    "[0:00]\n"
    "Hand-drawn 2D doodle cartoon animation, soft hand-drawn lines with clean "
    "bold outlines and gentle pastel fills, a friendly teacher character "
    "standing beside a large chalkboard, inside a bright sunny classroom, the "
    "teacher points at a diagram of the water cycle while raindrops fall "
    "outside the window, medium shot with a gentle push-in toward the board, "
    'Narration focus: "Water is always moving around us.", no text, no labels, '
    "no watermark, no realistic shading, no photography, no 3D render, 16:9 "
    "aspect ratio, KaiMi educational doodle style"
)

#: Section labels that must never appear in a generated prompt. Google Flow
#: sometimes renders these labels as visible text inside generated images.
_FORBIDDEN_LABELS = (
    "Master Style Lock:",
    "Character:",
    "Environment:",
    "Lighting:",
    "Camera:",
    "Negative Prompt:",
    "Scene:",
    "Visual Description:",
)


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
            f"Generate one image prompt per transcript scene. "
            f"Return your response as a JSON array of prompt objects.\n\n"
            f"Each object must have exactly these keys (all values must be non-empty):\n"
            f'- "scene_number": integer\n'
            f'- "timestamp": zero-padded "MM:SS" string, e.g. "00:00" (the in-prompt '
            f"first line uses [M:SS] without padding, e.g. [0:00], for the same scene)\n"
            f'- "prompt_title": short descriptive title\n'
            f'- "full_image_prompt": complete production-ready prompt\n\n'
            f"The full_image_prompt must follow the Production Stage 7 reference "
            f"format exactly:\n"
            f"- First line: the scene timestamp in [M:SS] format without zero-padding "
            f"(e.g. [0:00]), matching the transcript scene it illustrates.\n"
            f"- Then one continuous natural-language paragraph that opens with "
            f"'Hand-drawn 2D doodle cartoon animation, ...' and flows through, "
            f"in order: illustration style and line quality, character "
            f"description, environment description, scene action, camera angle, "
            f'Narration focus: "<narration quote verbatim from that transcript '
            f'scene>", negative wording, "16:9 aspect ratio", "KaiMi educational '
            f"doodle style\".\n\n"
            f"Reference template:\n{PROMPT_TEMPLATE}\n\n"
            f"Rules:\n"
            f"- One prompt per transcript scene; never merge or split transcript scenes.\n"
            f"- Write the whole description as one continuous sentence joined "
            f"with commas. No headings, no labels, no metadata, no bullet "
            f"points, no blank lines and no line breaks inside a prompt.\n"
            f"- Never write labels such as: "
            f"{', '.join(_FORBIDDEN_LABELS)}.\n"
            f"- Preserve the same illustration style, line quality, brush style, "
            f"rendering style, color palette, and artistic identity across all "
            f"scenes of the project.\n"
            f"- When consecutive scenes share a location or character, reuse the "
            f"same natural continuity language as the previous prompt.\n"
            f"- The narration focus quote must be the exact narration from that "
            f"transcript scene, quoted verbatim.\n\n"
            f"Return ONLY valid JSON. No markdown, no explanation, no extra text."
        )

        return system, user

    @staticmethod
    def retry_format_reminder() -> str:
        """Strict JSON reminder appended on a bounded parse-failure retry.

        The reminder restates the exact output contract without changing the
        project's visual-style instructions, so a repaired response stays
        consistent with the Production Stage 7 reference format (RC-7).
        """
        return (
            "Your previous response did not match the required format. "
            "Respond with ONLY a valid JSON array where every object has "
            "exactly these keys: scene_number (integer), timestamp "
            "(MM:SS string), prompt_title (string), and full_image_prompt "
            "(string: one continuous natural-language paragraph in the "
            "Production Stage 7 reference format, opening with the hand-drawn "
            "2D doodle cartoon animation style phrase and ending with the "
            "16:9 aspect ratio and the KaiMi educational doodle style tag). "
            "No markdown, no explanations, no extra text."
        )

    @staticmethod
    def _normalize_text(value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()
