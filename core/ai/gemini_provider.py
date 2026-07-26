from __future__ import annotations

import os

from core.ai.base_provider import BaseProvider


class GeminiProvider(BaseProvider):
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable is not set.")

    def generate(self, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable is not set.")

        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError(
                "Gemini SDK is not installed.\n\n"
                "Run:\n\npip install google-genai"
            ) from exc

        try:
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
        except Exception as exc:
            raise RuntimeError(f"Gemini generation failed: {exc}") from exc

        text = getattr(response, "text", None)
        if text:
            return str(text).strip()

        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            collected: list[str] = []
            for part in parts:
                part_text = getattr(part, "text", None)
                if part_text:
                    collected.append(str(part_text))
            if collected:
                return "\n".join(collected).strip()

        return str(response)
