from core.ai.ai_engine import AIEngine
from core.research_storage import ResearchStorage


class ScriptService:
    def __init__(self, research_storage: ResearchStorage | None = None, ai_engine: AIEngine | None = None):
        self.research_storage = research_storage or ResearchStorage()
        self.ai_engine = ai_engine or AIEngine(provider="gemini")

    def generate(
        self,
        project_name: str,
        style: str,
        length: str,
        tone: str,
    ) -> str:
        research_data = self.research_storage.load(project_name)
        topic = research_data.get("topic", "Untitled Topic")
        goal = research_data.get("goal", "")
        keywords = research_data.get("keywords", "")

        length_hint = {
            "Short": "a concise script",
            "Medium": "a balanced script",
            "Long": "a detailed script",
        }.get(length, "a script")

        style_label = style or "Educational"
        tone_label = tone or "Friendly"

        prompt = (
            f"Title: {topic}\n\n"
            f"Style: {style_label}\n"
            f"Length: {length}\n"
            f"Tone: {tone_label}\n\n"
            f"Opening:\nIntroduce {topic} in a {tone_label.lower()} and engaging way.\n\n"
            f"Body:\nUse {keywords or 'the key themes'} to support the message and connect it to {goal or 'the project goal'}.\n\n"
            f"Conclusion:\nClose with a strong call to action and a clear takeaway for the audience.\n\n"
            f"This is a simulated {length_hint} for {topic}."
        )
        return self.ai_engine.generate(prompt)
