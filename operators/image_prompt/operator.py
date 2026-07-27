# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
from __future__ import annotations

from operators.image_prompt.models import (
    ImagePromptGenerationError,
    ImagePromptRequest,
    ImagePromptValidationError,
)
from operators.image_prompt.prompt_builder import ImagePromptBuilder
from providers.exceptions import ProviderError, ProviderNotConfiguredError
from providers.models import GenerationRequest
from providers.provider_manager import ProviderManager


class ProviderConfigurationError(RuntimeError):
    """Raised when the active AI provider is not properly configured."""


class ImagePromptOperator:
    """Orchestrates the image prompt generation pipeline.

    Accepts an ImagePromptRequest, validates it, builds a prompt,
    and returns generated image prompt text via ProviderManager.

    This class contains no AI logic, no UI code, no storage, and
    no direct provider imports. It depends only on ProviderManager.
    """

    def __init__(
        self,
        prompt_builder: ImagePromptBuilder | None = None,
        provider_manager: ProviderManager | None = None,
    ) -> None:
        self._prompt_builder = prompt_builder or ImagePromptBuilder()
        self._provider_manager = provider_manager or ProviderManager()

    def execute(self, request: ImagePromptRequest) -> str:
        """Execute the full image prompt generation pipeline.

        Args:
            request: A structured ImagePromptRequest containing prompt parameters.

        Returns:
            The generated image prompt text from the active AI provider.

        Raises:
            ImagePromptValidationError: If the request is missing required fields.
            ProviderConfigurationError: If the active provider is not configured.
            ImagePromptGenerationError: If the provider fails to generate content.
        """
        self._validate_request(request)

        prompt = self._prompt_builder.build(request)

        return self._generate(prompt)

    def get_prompt_preview(self, request: ImagePromptRequest) -> str:
        """Return the image prompt without calling the AI provider.

        Useful for previewing what would be sent to the AI.
        """
        self._validate_request(request)
        return self._prompt_builder.build(request)

    def _validate_request(self, request: ImagePromptRequest) -> None:
        if not isinstance(request, ImagePromptRequest):
            raise ImagePromptValidationError(
                "Expected an ImagePromptRequest instance."
            )

        storyboard_text = (request.storyboard_text or "").strip()
        if not storyboard_text:
            raise ImagePromptValidationError(
                "Storyboard text must not be empty."
            )

    def _generate(self, prompt: str) -> str:
        try:
            generation_request = GenerationRequest(prompt=prompt)
            response = self._provider_manager.generate(generation_request)
        except ProviderNotConfiguredError as exc:
            raise ProviderConfigurationError(str(exc)) from exc
        except ProviderError as exc:
            raise ImagePromptGenerationError(str(exc)) from exc
        except Exception as exc:
            raise ImagePromptGenerationError(
                f"Image prompt generation failed: {exc}"
            ) from exc

        if not response.text or not response.text.strip():
            raise ImagePromptGenerationError(
                "Provider returned empty content."
            )

        return response.text.strip()
