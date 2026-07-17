from core.ai.base_provider import BaseProvider


class MockProvider(BaseProvider):
    def generate(self, prompt: str) -> str:
        cleaned_prompt = (prompt or "").strip() or "No prompt provided."
        return f"[Mock AI] {cleaned_prompt}"
