# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
from __future__ import annotations

import time

from core.logger import get_logger
from operators.research.prompt_builder import ResearchPromptBuilder, ResearchRequest
from providers.exceptions import ProviderError, ProviderNotConfiguredError
from providers.models import GenerationRequest
from providers.provider_manager import ProviderManager


class ResearchValidationError(ValueError):
    """Raised when a ResearchRequest fails validation."""


class ProviderConfigurationError(RuntimeError):
    """Raised when the active AI provider is not properly configured."""


class ResearchGenerationError(RuntimeError):
    """Raised when the AI provider fails to generate research content."""


class ResearchOperator:
    """Orchestrates the research generation pipeline.

    Accepts a ResearchRequest, validates it, builds a prompt,
    and returns generated research via ProviderManager.

    This class contains no AI logic, no UI code, no storage, and
    no direct provider imports. It depends only on ProviderManager.
    """

    def __init__(
        self,
        prompt_builder: ResearchPromptBuilder | None = None,
        provider_manager: ProviderManager | None = None,
    ) -> None:
        self._prompt_builder = prompt_builder or ResearchPromptBuilder()
        self._provider_manager = provider_manager or ProviderManager()
        self._log = get_logger()

    def execute(self, request: ResearchRequest) -> str:
        """Execute the full research pipeline."""
        self._log.info("ResearchOperator", f"Starting research generation: topic={request.topic}")
        t0 = time.perf_counter()
        self._validate_request(request)

        prompt = self._prompt_builder.build(request)

        result = self._generate(prompt)
        elapsed = time.perf_counter() - t0
        self._log.info("ResearchOperator", f"Research generated in {elapsed:.2f}s ({len(result)} chars)")
        return result

    def get_prompt_preview(self, request: ResearchRequest) -> str:
        """Return the research prompt without calling the AI provider.

        Useful for previewing what would be sent to the AI.
        """
        self._validate_request(request)
        return self._prompt_builder.build(request)

    def _validate_request(self, request: ResearchRequest) -> None:
        if not isinstance(request, ResearchRequest):
            raise ResearchValidationError(
                "Expected a ResearchRequest instance."
            )

        topic = (request.topic or "").strip()
        if not topic:
            raise ResearchValidationError(
                "Research topic must not be empty."
            )

    def _generate(self, prompt: str) -> str:
        try:
            generation_request = GenerationRequest(prompt=prompt)
            response = self._provider_manager.generate(generation_request)
        except ProviderNotConfiguredError as exc:
            raise ProviderConfigurationError(str(exc)) from exc
        except ProviderError as exc:
            raise ResearchGenerationError(str(exc)) from exc
        except Exception as exc:
            raise ResearchGenerationError(
                f"Research generation failed: {exc}"
            ) from exc

        if not response.text or not response.text.strip():
            raise ResearchGenerationError(
                "Provider returned empty content."
            )

        return response.text.strip()
