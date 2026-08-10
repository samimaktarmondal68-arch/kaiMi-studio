# Image Prompt Generation Rules

Generate one production-ready image prompt per transcript scene.

Every prompt must follow the Production Stage 7 reference format exactly.
Each prompt is a single continuous natural-language description. No headings,
no labels, no metadata, no bullet points, no blank lines inside a prompt.

## Prompt Format (exact ordering)

Each full_image_prompt is ONE continuous paragraph that opens with:

   Hand-drawn 2D doodle cartoon animation, ...

and continues in a single flowing natural-language sentence that weaves in,
in this order:
   - the illustration style and line / brush / rendering quality
   - the character or subject description
   - the environment or background description
   - the scene action
   - the camera angle
   - Narration focus: "<narration quote taken verbatim from that transcript scene>"
   - the negative wording (what must NOT appear in the image)
   - 16:9 aspect ratio
   - KaiMi educational doodle style

The paragraph is one continuous sentence joined with commas — never a list,
never separate sentences with labels, never wrapped across multiple lines.

The scene timestamp is STRUCTURED METADATA, never part of the prompt text.
The prompt must NOT begin with a timestamp (no "[0:00]", no "[00:00]", no
bare "00:00" at the start) and must NOT contain "Scene N:", "Timestamp:",
or any other duplicated metadata. The timestamp lives only in the separate
"timestamp" field.

## Example

The paragraph below is a single line in the actual prompt:

Hand-drawn 2D doodle cartoon animation, soft hand-drawn lines with clean bold outlines and gentle pastel fills, a friendly teacher character standing beside a large chalkboard, inside a bright sunny classroom, the teacher points at a diagram of the water cycle while raindrops fall outside the window, medium shot with a gentle push-in toward the board, Narration focus: "Water is always moving around us.", no text, no labels, no watermark, no realistic shading, no photography, no 3D render, 16:9 aspect ratio, KaiMi educational doodle style

## Style Consistency

Every prompt in a project must preserve the same illustration style, line
quality, brush style, rendering style, color palette, and artistic identity.
When consecutive scenes share a location or character, reuse the same natural
continuity language from the previous prompt (same character description, same
environment description) instead of introducing new phrasing.

## Dynamic Scene Variety

Every scene must feel like the NEXT SHOT of the same animated production: the
KaiMi art style stays identical, but the visual storytelling changes.

- Consecutive scenes must not repeat the same camera framing, camera angle,
  character pose, environment composition, visual focus, action, or subject
  placement. If consecutive scenes intentionally continue the same location
  or character, keep the continuity language but change at least some
  meaningful visual dimensions (composition, camera, action, focus, scale).
- Prefer subtle motion-friendly language where it fits the narration: a
  gentle camera push-in or pull-back, hair or clothing moving softly,
  curtains moving in airflow, drifting clouds, floating particles, changing
  light, the subject turning, looking, reaching, walking or reacting,
  objects entering or leaving the frame, subtle foreground/background
  parallax. Motion stays natural and subtle — never turn a calm scene into
  an action scene.
- The narration is the source of truth. Scene visual directions are
  suggestions; never invent visuals that contradict the narration merely to
  create variety.
- Variety comes from visual storytelling (composition, camera, action,
  focus), NEVER from changing the art style, rendering style, color
  palette, line quality, brush style, or character design.

## Rules

- One prompt per transcript scene. Never merge or split transcript scenes.
- The timestamp of the scene is structured metadata (the "timestamp" field
  only). Never write it into full_image_prompt and never duplicate any
  metadata — the prompt text must never begin with a timestamp.
- The narration focus quote must be the actual narration from that transcript
  scene, quoted verbatim.
- Never write section labels such as "Master Style Lock:", "Character:",
  "Environment:", "Lighting:", "Camera:", "Negative Prompt:", "Scene:",
  "Visual Description:".
- The prompt sent to the image generator must remain a single continuous
  natural-language description exactly like the reference. Google Flow
  sometimes renders labels as visible text inside generated images.
- Return prompts as a clean JSON array with these exact keys (all values must
  be non-empty):
  - scene_number: integer
  - timestamp: zero-padded "MM:SS" string, e.g. "00:00" (structured metadata)
  - prompt_title: short descriptive title
  - full_image_prompt: complete VISUAL prompt only — one continuous
    natural-language paragraph, never beginning with a timestamp

Return ONLY valid JSON. No markdown, no explanation, no extra text.
