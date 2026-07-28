# Image Prompt Generation Rules

Use the script and transcript to generate production-ready image prompts.

Each prompt must describe a single frame or scene for an animator to create.

Each prompt must include:
- Subject
- Environment / Background
- Composition
- Lighting
- Camera angle
- Art style
- Color palette
- Negative prompt (what NOT to include)

Match the visual style to the video type (Educational, Documentary, etc.).

Return prompts as a clean JSON array with these exact keys:
- scene_number: integer
- timestamp: "MM:SS" format
- prompt_title: short descriptive title
- full_image_prompt: complete prompt string

Return ONLY valid JSON. No markdown, no explanation, no extra text.