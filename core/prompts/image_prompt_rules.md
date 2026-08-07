# Image Prompt Generation Rules

Generate one production-ready image prompt per transcript scene.

Every prompt must follow the Production Stage 7 reference format exactly.
Each prompt is a single continuous natural-language description. No headings,
no labels, no metadata, no bullet points, no blank lines inside a prompt.

## Prompt Format (exact ordering)

Each full_image_prompt has exactly two parts:

1. The scene timestamp on its own first line, in [M:SS] format (minutes are
   not zero-padded), matching the transcript scene it illustrates. Example: [0:00]

2. One continuous paragraph that opens with:

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

## Example

The paragraph below is a single line in the actual prompt:

[0:00]
Hand-drawn 2D doodle cartoon animation, soft hand-drawn lines with clean bold outlines and gentle pastel fills, a friendly teacher character standing beside a large chalkboard, inside a bright sunny classroom, the teacher points at a diagram of the water cycle while raindrops fall outside the window, medium shot with a gentle push-in toward the board, Narration focus: "Water is always moving around us.", no text, no labels, no watermark, no realistic shading, no photography, no 3D render, 16:9 aspect ratio, KaiMi educational doodle style

## Style Consistency

Every prompt in a project must preserve the same illustration style, line
quality, brush style, rendering style, color palette, and artistic identity.
When consecutive scenes share a location or character, reuse the same natural
continuity language from the previous prompt (same character description, same
environment description) instead of introducing new phrasing.

## Rules

- One prompt per transcript scene. Never merge or split transcript scenes.
- The timestamp line must match the transcript scene it illustrates.
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
  - timestamp: zero-padded "MM:SS" string, e.g. "00:00" (the in-prompt first
    line uses [M:SS] without padding, e.g. [0:00], for the same scene)
  - prompt_title: short descriptive title
  - full_image_prompt: complete prompt string (reference format above)

Return ONLY valid JSON. No markdown, no explanation, no extra text.
