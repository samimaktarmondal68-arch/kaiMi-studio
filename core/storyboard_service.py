from core.ai.ai_engine import AIEngine


class StoryboardService:
    def __init__(self, ai_engine: AIEngine | None = None):
        self.ai_engine = ai_engine or AIEngine(provider="gemini")

    def generate(self, script_data: dict) -> list[dict]:
        script_text = (script_data.get("script_output") or "").strip()
        length = (script_data.get("length") or "Medium").strip()
        scene_count = 8 if length == "Short" else 10 if length == "Medium" else 12
        topic = script_text.splitlines()[0].replace("Title:", "").strip() if script_text else "Untitled"

        prompt = (
            f"Create a storyboard outline for the following script. "
            f"Return a concise simulated storyboard with {scene_count} scenes.\n\nScript:\n{script_text}\n"
        )
        self.ai_engine.generate(prompt)

        scenes: list[dict] = []
        for index in range(1, scene_count + 1):
            start_time = (index - 1) * 10
            scenes.append(
                {
                    "scene_number": index,
                    "timestamp": f"{start_time:02d}:00",
                    "narration": f"{topic} scene {index}: introduce the next beat of the story in a clear and cinematic way.",
                    "visual_description": f"A polished visual frame that supports the narrative progression of scene {index}.",
                    "camera_direction": "Slow push-in or steady tracking shot to keep the focus on the action.",
                    "on_screen_text": f"{topic} • Scene {index}",
                }
            )

        return scenes
