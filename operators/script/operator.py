from __future__ import annotations

from operators.script.models import (
    ScriptGenerationError,
    ScriptRequest,
    ScriptValidationError,
)
from operators.script.prompt_builder import ScriptPromptBuilder
from providers.exceptions import ProviderError, ProviderNotConfiguredError
from providers.models import GenerationRequest
from providers.provider_manager import ProviderManager


class ProviderConfigurationError(RuntimeError):
    """Raised when the active AI provider is not properly configured."""


class ScriptOperator:
    """Orchestrates the script generation pipeline.

    Accepts a ScriptRequest, validates it, builds a prompt,
    and returns generated script text via ProviderManager.

    This class contains no AI logic, no UI code, no storage, and
    no direct provider imports. It depends only on ProviderManager.
    """

    def __init__(
        self,
        prompt_builder: ScriptPromptBuilder | None = None,
        provider_manager: ProviderManager | None = None,
    ) -> None:
        self._prompt_builder = prompt_builder or ScriptPromptBuilder()
        self._provider_manager = provider_manager or ProviderManager()

    def execute(self, request: ScriptRequest) -> str:
        """Execute the full script generation pipeline.

        Args:
            request: A structured ScriptRequest containing script parameters.

        Returns:
            The generated script text from the active AI provider.

        Raises:
            ScriptValidationError: If the request is missing required fields.
            ProviderConfigurationError: If the active provider is not configured.
            ScriptGenerationError: If the provider fails to generate content.
        """
        self._validate_request(request)

        prompt = self._prompt_builder.build(request)

        return self._generate(prompt)

    def get_prompt_preview(self, request: ScriptRequest) -> str:
        """Return the script prompt without calling the AI provider.

        Useful for previewing what would be sent to the AI.
        """
        self._validate_request(request)
        return self._prompt_builder.build(request)

    def _validate_request(self, request: ScriptRequest) -> None:
        if not isinstance(request, ScriptRequest):
            raise ScriptValidationError(
                "Expected a ScriptRequest instance."
            )

        topic = (request.topic or "").strip()
        if not topic:
            raise ScriptValidationError(
                "Script topic must not be empty."
            )

    def _generate(self, prompt: str) -> str:
        try:
            generation_request = GenerationRequest(prompt=prompt)
            response = self._provider_manager.generate(generation_request)
        except ProviderNotConfiguredError as exc:
            raise ProviderConfigurationError(str(exc)) from exc
        except ProviderError as exc:
            raise ScriptGenerationError(str(exc)) from exc
        except Exception as exc:
            raise ScriptGenerationError(
                f"Script generation failed: {exc}"
            ) from exc

        if not response.text or not response.text.strip():
            raise ScriptGenerationError(
                "Provider returned empty content."
            )

        return response.text.strip()
