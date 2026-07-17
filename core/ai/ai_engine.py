from core.ai.base_provider import BaseProvider
from core.ai.mock_provider import MockProvider
from core.ai.gemini_provider import GeminiProvider


class AIEngine:
    def __init__(self, provider: BaseProvider | str | None = None):
        self.provider = self._resolve_provider(provider)

    def _resolve_provider(self, provider: BaseProvider | str | None) -> BaseProvider:
        if isinstance(provider, BaseProvider):
            return provider
        if isinstance(provider, str):
            provider_name = provider.lower()
            if provider_name == "gemini":
                return GeminiProvider()
            if provider_name == "mock":
                return MockProvider()
        return MockProvider()

    def generate(self, prompt: str) -> str:
        return self.provider.generate(prompt)
