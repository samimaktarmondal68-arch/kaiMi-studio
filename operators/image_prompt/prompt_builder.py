from __future__ import annotations

from operators.image_prompt.models import ImagePromptRequest
from core.prompts import load_all_system_prompts

#: Production Stage 7 reference template embedded in every generation request.
#: The model must reproduce this exact writing style: one continuous
#: natural-language paragraph opening with "Hand-drawn 2D doodle cartoon
#: animation, ..." that flows through style, character, environment, action,
#: camera, narration focus, negative wording, aspect ratio, and the KaiMi
#: style tag — with no labels or metadata. The scene timestamp is structured
#: metadata and must NEVER appear inside the prompt text (FIX F).
PROMPT_TEMPLATE = (
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

#: FIX H — deterministic scene-variation cycle. The plan cycles through six
#: distinct visual beats (establishing, character action, close-up, concept
#: metaphor, environment activity, character reaction) keyed by the ABSOLUTE
#: scene number, so the same transcript always produces the same plan and
#: consecutive scenes always receive different composition/camera/focus
#: suggestions. The model is instructed to adapt each beat to the narration:
#: the cycle prevents repetition, it never overrides content.
SCENE_VARIATION_CYCLE = (
    {
        "composition": "wide establishing shot of the environment",
        "camera": "gentle push-in toward the scene",
        "focus": "the full environment and the location of the action",
        "motion": "soft drifting particles in the air and slowly shifting light",
    },
    {
        "composition": "medium shot on the main subject in action",
        "camera": "slow lateral pan following the subject",
        "focus": "the subject's movement and interaction with the environment",
        "motion": "hair or clothing moving gently with the subject's motion",
    },
    {
        "composition": "close-up detail shot",
        "camera": "shallow push-in toward the detail",
        "focus": "one meaningful detail such as the hands, the face or an object",
        "motion": "the detail subtly moving while the background drifts past",
    },
    {
        "composition": "visual concept or metaphor composition",
        "camera": "slow pull-back revealing the concept in context",
        "focus": "a symbolic visual that explains the narration idea",
        "motion": "floating symbolic elements appearing, orbiting or flowing",
    },
    {
        "composition": "environmental activity shot",
        "camera": "low or high angle across the environment",
        "focus": "the environment responding to the subject's presence",
        "motion": (
            "objects entering or leaving the frame, curtains, clouds or "
            "leaves moving"
        ),
    },
    {
        "composition": "character reaction shot",
        "camera": "over-the-shoulder or side-profile framing",
        "focus": "the subject's facial reaction and body language",
        "motion": "the subject turning, looking, reaching or reacting",
    },
)


def scene_visual_direction(scene_number: int) -> dict:
    """Return the deterministic FIX H visual-direction beat for a scene.

    Keyed by the ABSOLUTE scene number so the plan is identical whether the
    scene is generated in a single request or inside a batch (scene 11 always
    plans the same beat either way). Adjacent scenes always receive different
    beats, which is the anti-repetition backbone; the model adapts each beat
    to the narration and never forces variety that contradicts the content.
    """
    return SCENE_VARIATION_CYCLE[(scene_number - 1) % len(SCENE_VARIATION_CYCLE)]


class ImagePromptBuilder:

    def build_batch(
        self,
        request: ImagePromptRequest,
        timestamps: list[dict],
        start_scene: int,
        end_scene: int,
        previous_prompts: list[str] | None = None,
    ) -> tuple[str, str]:
        """Build a generation request for one scene batch of a long transcript.

        Reuses the full style lock, Production Stage 7 reference format and
        output contract from ``build()`` while scoping the scene list to the
        batch (RC-7.3). Every scene line carries its ABSOLUTE scene number and
        exact MM:SS timestamp so the model echoes the identity the aggregation
        layer expects — the LLM is never trusted to invent or normalize
        timestamps or numbering. ``previous_prompts`` pins the project's
        locked visual direction for later batches so chunking never causes
        style drift, and the final anchor prompt doubles as FIX H
        scene-to-scene memory so a batch never reopens with a duplicate shot.

        Returns:
            (system_prompt, user_prompt) ready for a single provider call.
        """
        batch_request = ImagePromptRequest(
            script_text=request.script_text,
            transcript="\n".join(self._scene_lines(timestamps, start_scene)),
            timestamps=[
                {
                    "time": ImagePromptBuilder.format_scene_time(segment),
                    "text": segment.get("text", ""),
                }
                for segment in timestamps
            ],
            topic=request.topic,
            language=request.language,
        )
        system, user = self.build(batch_request, start_scene=start_scene)

        scene_count = len(timestamps)
        user += (
            f"\n\nIMPORTANT BATCH INSTRUCTIONS:\n"
            f"- Generate prompts ONLY for the {scene_count} scenes listed above "
            f"(scene numbers {start_scene} through {end_scene}).\n"
            f'- The "scene_number" field must be the ABSOLUTE scene number shown '
            f"in the 'Scene N' prefix of each transcript line (e.g. {start_scene}), "
            f"never a batch-local index.\n"
            f'- The "timestamp" field must be exactly the MM:SS shown for that '
            f"scene, never an invented time.\n"
            f"- Return EXACTLY {scene_count} prompt objects — one per listed scene, "
            f"in the order the scenes are listed. Do not merge scenes and do not "
            f"invent extra scenes.\n"
        )
        if previous_prompts:
            user += (
                "\nStyle anchor — the following prompt(s) from earlier scenes of "
                "this project show the locked visual direction. Keep the exact "
                "same illustration style, line quality, brush style, color "
                "palette, character design, camera language and rendering style "
                "in every new prompt:\n"
            )
            for index, prompt_text in enumerate(previous_prompts, 1):
                user += f"{index}. {prompt_text}\n"
            # FIX H — scene-to-scene memory across the batch boundary: the
            # final anchor prompt is the previous scene's actual composition,
            # so the batch must not reopen with a duplicate shot.
            user += (
                "\nThe FINAL prompt above is the previous scene's actual "
                "composition. Vary the first scenes of this batch against it "
                "(different framing, camera angle, action and focus) unless the "
                "narration demands the same shot — while keeping the style "
                "identical.\n"
            )

        return system, user

    @staticmethod
    def _scene_lines(timestamps: list[dict], start_scene: int) -> list[str]:
        """Render batch scenes as 'Scene N [MM:SS]: text' lines."""
        lines = []
        for offset, segment in enumerate(timestamps):
            scene_number = start_scene + offset
            time_value = ImagePromptBuilder.format_scene_time(segment)
            text = (segment.get("text") or "").strip()
            lines.append(f"Scene {scene_number} [{time_value}]: {text}")
        return lines

    @staticmethod
    def scene_direction_section(
        timestamps: list[dict], start_scene: int = 1
    ) -> str:
        """Render per-scene FIX H visual-direction suggestions.

        One line per scene, keyed by the scene's ABSOLUTE number so the plan
        stays stable across regeneration and across batch boundaries. Every
        line states the planned composition/camera/focus/motion beat plus the
        beat planned for the previous scene, giving the model the lightweight
        scene-to-scene memory it needs to avoid duplicate shots while keeping
        the narration the source of truth.
        """
        lines = [
            "Scene visual directions — suggested starting points for visual "
            "variety; adapt each one to the narration, which is the source of "
            "truth:"
        ]
        for offset in range(len(timestamps)):
            scene_number = start_scene + offset
            beat = scene_visual_direction(scene_number)
            if scene_number == 1:
                previous = "none — this is the opening shot"
            else:
                previous_beat = scene_visual_direction(scene_number - 1)
                previous = (
                    f"scene {scene_number - 1} planned: "
                    f"{previous_beat['composition']} — choose a clearly "
                    f"different composition, camera angle, action and focus"
                )
            lines.append(
                f"Scene {scene_number}: {beat['composition']}, "
                f"{beat['camera']}, visual focus on {beat['focus']}, "
                f"subtle motion: {beat['motion']}. "
                f"(previous: {previous}.)"
            )
        return "\n".join(lines) + "\n\n"

    @staticmethod
    def format_scene_time(segment: dict) -> str:
        """Return a scene segment's timestamp as a zero-padded MM:SS string.

        Prefers an existing ``time`` field; falls back to computing it from
        ``start`` seconds so batch prompts always carry a valid MM:SS that the
        model can echo back verbatim (RC-7.3).
        """
        time_value = (segment.get("time") or "").strip()
        if (
            len(time_value) == 5
            and time_value[2] == ":"
            and time_value[:2].isdigit()
            and time_value[3:].isdigit()
        ):
            return time_value
        raw = segment.get("start", 0) or 0
        total = int(raw)
        return f"{total // 60:02d}:{total % 60:02d}"

    def build(
        self, request: ImagePromptRequest, start_scene: int = 1
    ) -> tuple[str, str]:
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
            user += self.scene_direction_section(request.timestamps, start_scene)

        user += (
            f"Generate one image prompt per transcript scene. "
            f"Return your response as a JSON array of prompt objects.\n\n"
            f"Each object must have exactly these keys (all values must be non-empty):\n"
            f'- "scene_number": integer\n'
            f'- "timestamp": zero-padded "MM:SS" string, e.g. "00:00" (structured '
            f"metadata — never embed it in the prompt text)\n"
            f'- "prompt_title": short descriptive title\n'
            f'- "full_image_prompt": complete production-ready prompt\n\n'
            f"The full_image_prompt must follow the Production Stage 7 reference "
            f"format exactly:\n"
            f"- One continuous natural-language paragraph that opens with "
            f"'Hand-drawn 2D doodle cartoon animation, ...' and flows through, "
            f"in order: illustration style and line quality, character "
            f"description, environment description, scene action, camera angle, "
            f'Narration focus: "<narration quote verbatim from that transcript '
            f'scene>", negative wording, "16:9 aspect ratio", "KaiMi educational '
            f"doodle style\".\n"
            f"- The scene timestamp is structured metadata ONLY: the prompt text "
            f"must NEVER begin with a timestamp (no [0:00], no [00:00], no bare "
            f"00:00 at the start) and must never repeat metadata.\n\n"
            f"Reference template:\n{PROMPT_TEMPLATE}\n\n"
            f"Rules:\n"
            f"- One prompt per transcript scene; never merge or split transcript scenes.\n"
            f"- Write the whole description as one continuous sentence joined "
            f"with commas. No headings, no labels, no metadata, no bullet "
            f"points, no blank lines and no line breaks inside a prompt.\n"
            f"- Never start the prompt with a timestamp or a 'Scene N:' / "
            f"'Timestamp:' prefix — the scene number and timestamp are the "
            f"structured fields, never part of the prompt text.\n"
            f"- Never write labels such as: "
            f"{', '.join(_FORBIDDEN_LABELS)}.\n"
            f"- Preserve the same illustration style, line quality, brush style, "
            f"rendering style, color palette, and artistic identity across all "
            f"scenes of the project.\n"
            f"- When consecutive scenes share a location or character, reuse the "
            f"same natural continuity language as the previous prompt.\n"
            f"- Dynamic scene variety: consecutive scenes must NOT repeat the "
            f"same camera framing, camera angle, character pose, environment "
            f"composition, visual focus, action, or subject placement. If "
            f"consecutive scenes intentionally continue the same location or "
            f"character, keep the character and environment continuity language "
            f"but change at least some meaningful visual dimensions "
            f"(composition, camera, action, focus, scale).\n"
            f"- The scene visual directions listed above are suggestions only: "
            f"the narration is the source of truth. Never invent visuals that "
            f"contradict the narration just to create variety.\n"
            f"- Prefer subtle motion-friendly language where it fits the "
            f"narration: a gentle camera push-in or pull-back, hair or clothing "
            f"moving softly, curtains moving in airflow, drifting clouds, "
            f"floating particles, changing light, the subject turning, looking, "
            f"reaching, walking or reacting, objects entering or leaving the "
            f"frame, subtle foreground/background parallax. Motion must stay "
            f"natural and subtle — never turn a calm scene into an action "
            f"scene.\n"
            f"- Variety must come from visual storytelling (composition, "
            f"camera, action, focus) — NEVER from changing the art style, "
            f"rendering style, color palette, line quality, brush style or "
            f"character design.\n"
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
            "Your previous response could not be parsed as valid JSON. "
            "Respond with valid JSON only: no Markdown fences, no commentary "
            "before the JSON, and no commentary after the JSON. Return one "
            "JSON array where every requested scene is represented exactly "
            "once and every object has exactly these keys: scene_number "
            "(integer), timestamp (MM:SS string structured metadata), "
            "prompt_title (string), and full_image_prompt (string containing "
            "only the visual prompt). Scene numbers must remain absolute. "
            "Use valid JSON string escaping: escape quotation marks inside "
            "strings, do not use raw newlines inside JSON string values, and "
            "do not use trailing commas. full_image_prompt must be one "
            "continuous natural-language paragraph in the Production Stage 7 "
            "reference format, must not begin with [M:SS], [MM:SS], or a bare "
            "timestamp, and must not include timestamp metadata."
        )

    @staticmethod
    def _normalize_text(value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()
