from __future__ import annotations

import time

from core.logger import get_logger
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
    pass


class ScriptOperator:

    def __init__(
        self,
        prompt_builder: ScriptPromptBuilder | None = None,
        provider_manager: ProviderManager | None = None,
    ) -> None:
        self._prompt_builder = prompt_builder or ScriptPromptBuilder()
        self._provider_manager = provider_manager or ProviderManager()
        self._log = get_logger()

    def execute(self, request: ScriptRequest) -> str:
        self._log.info("ScriptOperator", f"Starting script generation: topic={request.topic}")
        t0 = time.perf_counter()
        self._validate_request(request)

        system_prompt, user_prompt = self._prompt_builder.build(request)

        result = self._generate(system_prompt, user_prompt)
        elapsed = time.perf_counter() - t0
        self._log.info("ScriptOperator", f"Script generated in {elapsed:.2f}s ({len(result)} chars)")
        return result

    def get_prompt_preview(self, request: ScriptRequest) -> str:
        self._validate_request(request)
        _, user_prompt = self._prompt_builder.build(request)
        return user_prompt

    def _validate_request(self, request: ScriptRequest) -> None:
        if not isinstance(request, ScriptRequest):
            raise ScriptValidationError("Expected a ScriptRequest instance.")
        topic = (request.topic or "").strip()
        if not topic:
            raise ScriptValidationError("Script topic must not be empty.")

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
            raise ScriptGenerationError(str(exc)) from exc
        except Exception as exc:
            raise ScriptGenerationError(f"Script generation failed: {exc}") from exc

        if not response.text or not response.text.strip():
            raise ScriptGenerationError("Provider returned empty content.")

        return response.text.strip()