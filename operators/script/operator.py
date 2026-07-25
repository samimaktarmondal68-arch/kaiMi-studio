from __future__ import annotations

from operators.script.models import (
    ScriptGenerationError,
    ScriptRequest,
    ScriptValidationError,
)
from operators.script.prompt_builder import ScriptPromptBuilder
from providers.base_provider import BaseProvider
from providers.provider_manager import ProviderManager


class ProviderConfigurationError(RuntimeError):
    """Raised when the active AI provider is not properly configured."""


class ScriptOperator:
    """Orchestrates the script generation pipeline.

    Accepts a ScriptRequest, validates it, builds a prompt,
    obtains the active AI provider, and returns generated script text.

    This class contains no AI logic, no UI code, no storage, and
    no direct provider imports. It depends only on abstractions.
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

        provider = self._obtain_provider()
        self._validate_provider(provider)

        return self._generate(provider, prompt)

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

    def _obtain_provider(self) -> BaseProvider:
        try:
            return self._provider_manager.get_active_provider()
        except ValueError as exc:
            raise ProviderConfigurationError(
                f"Failed to obtain active provider: {exc}"
            ) from exc

    def _validate_provider(self, provider: BaseProvider) -> None:
        if not provider.validate_configuration():
            name = provider.get_provider_name()
            raise ProviderConfigurationError(
                f"Provider '{name}' is not configured. "
                "Please set a valid API key in Settings."
            )

    def _generate(self, provider: BaseProvider, prompt: str) -> str:
        name = provider.get_provider_name()
        try:
            result = provider.generate(prompt)
        except NotImplementedError as exc:
            raise ProviderConfigurationError(
                f"Provider '{name}' is not implemented: {exc}"
            ) from exc
        except Exception as exc:
            raise ScriptGenerationError(
                f"Script generation failed with provider '{name}': {exc}"
            ) from exc

        if not result or not result.strip():
            raise ScriptGenerationError(
                f"Provider '{name}' returned empty content."
            )

        return result.strip()
