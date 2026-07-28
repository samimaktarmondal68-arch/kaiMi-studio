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
    pass


class ImagePromptOperator:

    def __init__(
        self,
        prompt_builder: ImagePromptBuilder | None = None,
        provider_manager: ProviderManager | None = None,
    ) -> None:
        self._prompt_builder = prompt_builder or ImagePromptBuilder()
        self._provider_manager = provider_manager or ProviderManager()

    def execute(self, request: ImagePromptRequest) -> str:
        self._validate_request(request)

        system_prompt, user_prompt = self._prompt_builder.build(request)

        return self._generate(system_prompt, user_prompt)

    def get_prompt_preview(self, request: ImagePromptRequest) -> str:
        self._validate_request(request)
        _, user_prompt = self._prompt_builder.build(request)
        return user_prompt

    def _validate_request(self, request: ImagePromptRequest) -> None:
        if not isinstance(request, ImagePromptRequest):
            raise ImagePromptValidationError("Expected an ImagePromptRequest instance.")
        script_text = (request.script_text or "").strip()
        if not script_text:
            raise ImagePromptValidationError("Script text must not be empty.")

    def _generate(self, system_prompt: str, user_prompt: str) -> str:
        try:
            generation_request = GenerationRequest(
                prompt=user_prompt,
                system_prompt=system_prompt,
            )
            response = self._provider_manager.generate(generation_request)
        except ProviderNotConfiguredError as exc:
            raise ProviderConfigurationError(str(exc)) from exc
        except ProviderError as exc:
            raise ImagePromptGenerationError(str(exc)) from exc
        except Exception as exc:
            raise ImagePromptGenerationError(f"Image prompt generation failed: {exc}") from exc

        if not response.text or not response.text.strip():
            raise ImagePromptGenerationError("Provider returned empty content.")

        return response.text.strip()