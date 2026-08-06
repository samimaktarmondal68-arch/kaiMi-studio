# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
from __future__ import annotations

from operators.storyboard.models import (
    StoryboardGenerationError,
    StoryboardRequest,
    StoryboardValidationError,
)
from operators.storyboard.prompt_builder import StoryboardPromptBuilder
from providers.exceptions import ProviderError, ProviderNotConfiguredError
from providers.models import GenerationRequest
from providers.provider_manager import ProviderManager, get_provider_manager


class ProviderConfigurationError(RuntimeError):
    """Raised when the active AI provider is not properly configured."""


class StoryboardOperator:
    """Orchestrates the storyboard generation pipeline.

    Accepts a StoryboardRequest, validates it, builds a prompt,
    and returns generated storyboard text via ProviderManager.

    This class contains no AI logic, no UI code, no storage, and
    no direct provider imports. It depends only on ProviderManager.
    """

    def __init__(
        self,
        prompt_builder: StoryboardPromptBuilder | None = None,
        provider_manager: ProviderManager | None = None,
    ) -> None:
        self._prompt_builder = prompt_builder or StoryboardPromptBuilder()
        # Store an injected manager (used in tests); None means create fresh per call.
        self._provider_manager = provider_manager

    def _get_provider_manager(self) -> ProviderManager:
        """Return the injected ProviderManager or a fresh one.

        A fresh instance is created on every generation call so that any
        provider change saved via Settings takes effect immediately without
        requiring an application restart.
        """
        return self._provider_manager or get_provider_manager()

    def execute(self, request: StoryboardRequest) -> str:
        """Execute the full storyboard generation pipeline.

        Args:
            request: A structured StoryboardRequest containing storyboard parameters.

        Returns:
            The generated storyboard text from the active AI provider.

        Raises:
            StoryboardValidationError: If the request is missing required fields.
            ProviderConfigurationError: If the active provider is not configured.
            StoryboardGenerationError: If the provider fails to generate content.
        """
        self._validate_request(request)

        prompt = self._prompt_builder.build(request)

        return self._generate(prompt)

    def get_prompt_preview(self, request: StoryboardRequest) -> str:
        """Return the storyboard prompt without calling the AI provider.

        Useful for previewing what would be sent to the AI.
        """
        self._validate_request(request)
        return self._prompt_builder.build(request)

    def _validate_request(self, request: StoryboardRequest) -> None:
        if not isinstance(request, StoryboardRequest):
            raise StoryboardValidationError(
                "Expected a StoryboardRequest instance."
            )

        script_text = (request.script_text or "").strip()
        if not script_text:
            raise StoryboardValidationError(
                "Script text must not be empty."
            )

    def _generate(self, prompt: str) -> str:
        try:
            generation_request = GenerationRequest(prompt=prompt)
            response = self._get_provider_manager().generate(generation_request)
        except ProviderNotConfiguredError as exc:
            raise ProviderConfigurationError(str(exc)) from exc
        except ProviderError as exc:
            raise StoryboardGenerationError(str(exc)) from exc
        except Exception as exc:
            raise StoryboardGenerationError(
                f"Storyboard generation failed: {exc}"
            ) from exc

        if not response.text or not response.text.strip():
            raise StoryboardGenerationError(
                "Provider returned empty content."
            )

        return response.text.strip()
