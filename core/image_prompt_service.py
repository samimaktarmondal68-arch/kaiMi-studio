from core.ai.ai_engine import AIEngine


class ImagePromptService:
    def __init__(self, ai_engine: AIEngine | None = None):
        self.ai_engine = ai_engine or AIEngine(provider="gemini")

    def generate(self, storyboard_data: dict) -> list[dict]:
        scenes = storyboard_data.get("scenes", []) if isinstance(storyboard_data, dict) else []
        prompts: list[dict] = []

        for index, scene in enumerate(scenes, start=1):
            scene_number = scene.get("scene_number", index)
            timestamp = scene.get("timestamp", "00:00")
            narration = scene.get("narration", "") or f"Scene {scene_number}"
            prompt_title = f"Scene {scene_number} Prompt"
            prompt_body = (
                f"Subject: {narration}\n"
                f"Environment: A cinematic production environment that supports the narrative.\n"
                f"Composition: Balanced framing with clear focal emphasis and strong visual hierarchy.\n"
                f"Lighting: Natural yet dramatic lighting with rich contrast and depth.\n"
                f"Camera Angle: Medium shot with a subtle push-in for visual momentum.\n"
                f"Art Style: High-end cinematic, polished, story-driven.\n"
                f"Negative Prompt: Blurry details, distorted anatomy, cluttered composition, low-quality textures."
            )
            prompts.append(
                {
                    "scene_number": scene_number,
                    "timestamp": timestamp,
                    "prompt_title": prompt_title,
                    "full_image_prompt": self.ai_engine.generate(prompt_body),
                }
            )

        return prompts
