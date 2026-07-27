# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""OpenAI-compatible provider implementation.

Supports any OpenAI-compatible API endpoint including:
- OpenCode Zen (https://opencode.ai/zen)
- OpenAI (https://api.openai.com)
- OpenRouter (https://openrouter.ai/api)
- Any custom endpoint

Uses the openai SDK which is already in requirements.txt.
"""

from __future__ import annotations

import logging

from providers.base_provider import BaseProvider
from providers.exceptions import (
    GenerationFailedError,
    InvalidAPIKeyError,
    ModelNotFoundError,
    NetworkError,
    ProviderError,
    QuotaExceededError,
    RateLimitedError,
)
from providers.models import (
    GenerationRequest,
    GenerationResponse,
    ProviderCapabilities,
    ProviderConfig,
    TokenUsage,
)

logger = logging.getLogger("kaimi_studio.providers.opencode")


class OpenAICompatibleProvider(BaseProvider):
    """OpenAI-compatible text generation provider.

    Works with any API endpoint that implements the OpenAI Chat Completions
    API or Responses API. Configurable via ProviderConfig:
        - api_key: API key for authentication
        - base_url: Base URL of the API endpoint
        - model: Default model identifier
    """

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client = None
        self._resolved_model = config.model.strip()

    def initialize(self) -> None:
        """Create the OpenAI SDK client."""
        api_key = self._config.api_key.strip()
        if not api_key:
            raise InvalidAPIKeyError(
                f"No API key configured for {self._config.name}. "
                "Set it in Settings.",
                provider=self._config.name,
            )

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderError(
                "OpenAI SDK is not installed. Run: pip install openai",
                provider=self._config.name,
                cause=exc,
            ) from exc

        try:
            kwargs = {"api_key": api_key}
            base_url = self._config.base_url.strip()
            if base_url:
                kwargs["base_url"] = base_url

            logger.info("[OpenAI-Compatible] Initializing client: base_url=%s", base_url or "(default)")
            self._client = OpenAI(**kwargs)
            actual_base = getattr(self._client, "base_url", None)
            logger.info("[OpenAI-Compatible] Client base_url: %s", actual_base)
        except Exception as exc:
            logger.error("[OpenAI-Compatible] Failed to initialize: %s: %s", type(exc).__name__, exc, exc_info=True)
            raise ProviderError(
                f"Failed to initialize OpenAI client: {exc}",
                provider=self._config.name,
                cause=exc,
            ) from exc

        super().initialize()

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate text using the Chat Completions API."""
        if not self._initialized:
            self.initialize()

        model = request.model.strip() or self._resolved_model
        if not model:
            raise ModelNotFoundError(
                f"No model specified for provider '{self._config.name}'. "
                "Set a model in Settings.",
                provider=self._config.name,
            )

        messages = self._build_messages(request)

        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
        except Exception as exc:
            raise self._translate_error(exc, model) from exc

        text = self._extract_text(response)
        if not text:
            raise GenerationFailedError(
                f"Provider '{self._config.name}' returned empty content for model '{model}'.",
                provider=self._config.name,
            )

        usage = self._extract_usage(response)
        finish_reason = self._extract_finish_reason(response)

        return GenerationResponse(
            text=text,
            usage=usage,
            finish_reason=finish_reason,
            provider=self._config.name,
            model=model,
        )

    def validate_key(self) -> bool:
        """Validate the API key by listing models."""
        if not self._initialized:
            try:
                self.initialize()
            except (InvalidAPIKeyError, ProviderError):
                return False

        try:
            models = self.list_models()
            return len(models) > 0
        except Exception:
            return False

    def list_models(self) -> list[str]:
        """List available models from the API endpoint."""
        if not self._initialized:
            self.initialize()

        base_url = self._config.base_url.strip() or "(default OpenAI)"
        logger.info(
            "[OpenAI-Compatible] Listing models: provider=%s, base_url=%s",
            self._config.name, base_url,
        )

        try:
            logger.info("[OpenAI-Compatible] Sending GET %s/v1/models", base_url)
            response = self._client.models.list()
            logger.info(
                "[OpenAI-Compatible] Response type: %s, has_data: %s",
                type(response).__name__,
                hasattr(response, "data"),
            )

            models = []

            if hasattr(response, "data"):
                items = response.data
            else:
                items = response

            for model in items:
                model_id = getattr(model, "id", None)
                owned_by = getattr(model, "owned_by", None)
                created = getattr(model, "created", None)
                if model_id:
                    models.append(str(model_id))
                    logger.debug(
                        "[OpenAI-Compatible] Model: id=%s, owned_by=%s, created=%s",
                        model_id, owned_by, created,
                    )

            logger.info("[OpenAI-Compatible] Found %d models", len(models))
            return sorted(models)
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            response_body = getattr(exc, "response", None)
            logger.error(
                "[OpenAI-Compatible] list_models failed: %s: %s (status=%s, response=%s)",
                type(exc).__name__, exc, status_code, response_body,
                exc_info=True,
            )
            return [self._resolved_model] if self._resolved_model else []

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_text=True,
            supports_streaming=True,
            supports_vision=False,
            supports_json=True,
            supports_reasoning=False,
            supports_tool_calling=False,
            supports_image_generation=False,
            supports_model_listing=True,
        )

    def _build_messages(self, request: GenerationRequest) -> list[dict]:
        """Build the messages array for the Chat Completions API."""
        messages = []

        system_prompt = request.system_prompt.strip()
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": request.prompt})

        return messages

    def _extract_text(self, response) -> str:
        """Extract text from an OpenAI Chat Completions response."""
        try:
            choice = response.choices[0]
            message = choice.message
            return (message.content or "").strip()
        except (AttributeError, IndexError):
            return ""

    def _extract_usage(self, response) -> TokenUsage:
        """Extract token usage from an OpenAI response."""
        usage = getattr(response, "usage", None)
        if not usage:
            return TokenUsage()

        return TokenUsage(
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            total_tokens=getattr(usage, "total_tokens", 0) or 0,
        )

    def _extract_finish_reason(self, response) -> str:
        """Extract finish reason from an OpenAI response."""
        try:
            return response.choices[0].finish_reason or "stop"
        except (AttributeError, IndexError):
            return "stop"

    def _translate_error(self, exc: Exception, model: str) -> ProviderError:
        """Translate an OpenAI SDK exception into a standardized error."""
        error_str = str(exc).lower()
        status_code = getattr(exc, "status_code", None)

        if status_code == 401 or "invalid" in error_str and "key" in error_str:
            return InvalidAPIKeyError(
                f"API key is invalid: {exc}",
                provider=self._config.name,
                cause=exc,
            )
        if status_code == 429 or "rate" in error_str:
            return RateLimitedError(
                f"Rate limited by provider: {exc}",
                provider=self._config.name,
                cause=exc,
            )
        if status_code == 402 or "quota" in error_str or "billing" in error_str:
            return QuotaExceededError(
                f"Quota exceeded: {exc}",
                provider=self._config.name,
                cause=exc,
            )
        if status_code == 404 or "not found" in error_str:
            return ModelNotFoundError(
                f"Model '{model}' not found: {exc}",
                provider=self._config.name,
                cause=exc,
            )
        if "connect" in error_str or "timeout" in error_str or "network" in error_str:
            return NetworkError(
                f"Network error: {exc}",
                provider=self._config.name,
                cause=exc,
            )

        return GenerationFailedError(
            f"Generation failed: {exc}",
            provider=self._config.name,
            cause=exc,
        )
