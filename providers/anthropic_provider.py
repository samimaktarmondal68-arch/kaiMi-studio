# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Anthropic Claude provider implementation.

Uses httpx (already installed) to interact with the Anthropic Messages API.
Anthropic uses a different API format than OpenAI, requiring:
    - x-api-key header (not Authorization: Bearer)
    - anthropic-version header
    - POST /v1/messages for generation
    - GET /v1/models for model listing
"""

from __future__ import annotations

import json
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

logger = logging.getLogger("kaimi_studio.providers.anthropic")

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_BASE_URL = "https://api.anthropic.com"
API_VERSION = "2023-06-01"


class AnthropicProvider(BaseProvider):
    """Anthropic Claude text generation provider.

    Uses the Anthropic Messages API with httpx for HTTP communication.
    Supports text generation with Claude models.
    """

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client = None
        self._resolved_model = config.model.strip() or DEFAULT_MODEL

    def _get_base_url(self) -> str:
        return (self._config.base_url.strip() or DEFAULT_BASE_URL).rstrip("/")

    def _get_headers(self) -> dict:
        api_key = self._config.api_key.strip()
        if not api_key:
            raise InvalidAPIKeyError(
                f"No API key configured for {self._config.name}. Set it in Settings.",
                provider=self._config.name,
            )
        return {
            "x-api-key": api_key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        }

    def initialize(self) -> None:
        """Validate the API key by making a lightweight request."""
        api_key = self._config.api_key.strip()
        if not api_key:
            raise InvalidAPIKeyError(
                f"No API key configured for {self._config.name}. Set it in Settings.",
                provider=self._config.name,
            )

        try:
            import httpx
        except ImportError as exc:
            raise ProviderError(
                "httpx is not installed. Run: pip install httpx",
                provider=self._config.name,
                cause=exc,
            ) from exc

        base_url = self._get_base_url()
        logger.info("[Anthropic] Initializing: base_url=%s", base_url)

        try:
            self._client = httpx.Client(
                base_url=base_url,
                headers=self._get_headers(),
                timeout=30.0,
            )
            logger.info("[Anthropic] Client created successfully")
        except Exception as exc:
            logger.error("[Anthropic] Failed to initialize: %s: %s", type(exc).__name__, exc, exc_info=True)
            raise ProviderError(
                f"Failed to initialize Anthropic client: {exc}",
                provider=self._config.name,
                cause=exc,
            ) from exc

        super().initialize()

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate text using the Anthropic Messages API."""
        if not self._initialized:
            self.initialize()

        model = request.model.strip() or self._resolved_model
        if not model:
            raise ModelNotFoundError(
                f"No model specified for provider '{self._config.name}'. Set a model in Settings.",
                provider=self._config.name,
            )

        messages = []
        if request.system_prompt.strip():
            messages.append({"role": "user", "content": request.system_prompt.strip() + "\n\n" + request.prompt})
        else:
            messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model": model,
            "max_tokens": request.max_tokens,
            "messages": messages,
            "temperature": request.temperature,
        }

        try:
            logger.info("[Anthropic] POST /v1/messages model=%s", model)
            response = self._client.post("/v1/messages", json=payload)
            logger.info("[Anthropic] Response status: %d", response.status_code)

            if response.status_code != 200:
                self._handle_error(response.status_code, response.text)

            data = response.json()
        except (InvalidAPIKeyError, QuotaExceededError, RateLimitedError,
                ModelNotFoundError, NetworkError, GenerationFailedError):
            raise
        except Exception as exc:
            logger.error("[Anthropic] generate failed: %s: %s", type(exc).__name__, exc, exc_info=True)
            raise self._translate_error(exc, model) from exc

        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")

        text = text.strip()
        if not text:
            raise GenerationFailedError(
                f"Anthropic returned empty content for model '{model}'.",
                provider=self._config.name,
            )

        usage_data = data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=usage_data.get("input_tokens", 0),
            completion_tokens=usage_data.get("output_tokens", 0),
            total_tokens=usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
        )

        return GenerationResponse(
            text=text,
            usage=usage,
            finish_reason=data.get("stop_reason", "stop"),
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
        """List available Anthropic models via GET /v1/models."""
        if not self._initialized:
            self.initialize()

        base_url = self._get_base_url()
        logger.info("[Anthropic] Listing models: GET %s/v1/models", base_url)

        try:
            response = self._client.get("/v1/models")
            logger.info("[Anthropic] Response status: %d", response.status_code)

            if response.status_code != 200:
                self._handle_error(response.status_code, response.text)

            data = response.json()
            models = []
            for model in data.get("data", []):
                model_id = model.get("id")
                display_name = model.get("display_name", "")
                if model_id:
                    models.append(str(model_id))
                    logger.debug("[Anthropic] Model: id=%s, display=%s", model_id, display_name)

            logger.info("[Anthropic] Found %d models", len(models))
            return sorted(models)
        except (InvalidAPIKeyError, QuotaExceededError, RateLimitedError,
                ModelNotFoundError, NetworkError):
            raise
        except Exception as exc:
            logger.error("[Anthropic] list_models failed: %s: %s", type(exc).__name__, exc, exc_info=True)
            raise ProviderError(
                f"Failed to list Anthropic models: {exc}",
                provider=self._config.name,
                cause=exc,
            ) from exc

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_text=True,
            supports_streaming=False,
            supports_vision=True,
            supports_json=True,
            supports_reasoning=False,
            supports_tool_calling=False,
            supports_image_generation=False,
            supports_model_listing=True,
        )

    def _handle_error(self, status_code: int, body: str) -> None:
        """Translate HTTP status codes into standardized exceptions."""
        logger.error("[Anthropic] HTTP %d: %s", status_code, body[:500])
        try:
            error_data = json.loads(body)
            error_msg = error_data.get("error", {}).get("message", body)
        except (json.JSONDecodeError, AttributeError):
            error_msg = body

        if status_code == 401:
            raise InvalidAPIKeyError(
                f"Anthropic API key is invalid: {error_msg}",
                provider=self._config.name,
            )
        if status_code == 429:
            raise RateLimitedError(
                f"Anthropic rate limited: {error_msg}",
                provider=self._config.name,
            )
        if status_code == 402:
            raise QuotaExceededError(
                f"Anthropic quota exceeded: {error_msg}",
                provider=self._config.name,
            )
        if status_code == 404:
            raise ModelNotFoundError(
                f"Anthropic model not found: {error_msg}",
                provider=self._config.name,
            )
        raise GenerationFailedError(
            f"Anthropic API error {status_code}: {error_msg}",
            provider=self._config.name,
        )

    def _translate_error(self, exc: Exception, model: str) -> ProviderError:
        """Translate an exception into a standardized error."""
        error_str = str(exc).lower()
        if "connect" in error_str or "timeout" in error_str or "network" in error_str:
            return NetworkError(
                f"Anthropic network error: {exc}",
                provider=self._config.name,
                cause=exc,
            )
        return GenerationFailedError(
            f"Anthropic generation failed: {exc}",
            provider=self._config.name,
            cause=exc,
        )
