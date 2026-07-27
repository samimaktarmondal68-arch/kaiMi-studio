# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Cohere provider implementation.

Uses httpx (already installed) to interact with the Cohere API.
Cohere uses its own API format:
    - Authorization: Bearer <key>
    - POST /v2/chat for generation (v2 Chat API)
    - GET /v1/models for model listing
    - Response: {"models": [{"name": "command-r", ...}]}
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

logger = logging.getLogger("kaimi_studio.providers.cohere")

DEFAULT_MODEL = "command-r-plus"
DEFAULT_BASE_URL = "https://api.cohere.com"


class CohereProvider(BaseProvider):
    """Cohere text generation provider.

    Uses the Cohere v2 Chat API with httpx for HTTP communication.
    Supports text generation with Cohere Command models.
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
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def initialize(self) -> None:
        """Initialize the Cohere HTTP client."""
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
        logger.info("[Cohere] Initializing: base_url=%s", base_url)

        try:
            self._client = httpx.Client(
                base_url=base_url,
                headers=self._get_headers(),
                timeout=30.0,
            )
            logger.info("[Cohere] Client created successfully")
        except Exception as exc:
            logger.error("[Cohere] Failed to initialize: %s: %s", type(exc).__name__, exc, exc_info=True)
            raise ProviderError(
                f"Failed to initialize Cohere client: {exc}",
                provider=self._config.name,
                cause=exc,
            ) from exc

        super().initialize()

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate text using the Cohere v2 Chat API."""
        if not self._initialized:
            self.initialize()

        model = request.model.strip() or self._resolved_model
        if not model:
            raise ModelNotFoundError(
                f"No model specified for provider '{self._config.name}'. Set a model in Settings.",
                provider=self._config.name,
            )

        messages = []
        preamble = ""
        if request.system_prompt.strip():
            preamble = request.system_prompt.strip()
        messages.append({"role": "user", "message": request.prompt})

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if preamble:
            payload["preamble"] = preamble

        try:
            logger.info("[Cohere] POST /v2/chat model=%s", model)
            response = self._client.post("/v2/chat", json=payload)
            logger.info("[Cohere] Response status: %d", response.status_code)

            if response.status_code != 200:
                self._handle_error(response.status_code, response.text)

            data = response.json()
        except (InvalidAPIKeyError, QuotaExceededError, RateLimitedError,
                ModelNotFoundError, NetworkError, GenerationFailedError):
            raise
        except Exception as exc:
            logger.error("[Cohere] generate failed: %s: %s", type(exc).__name__, exc, exc_info=True)
            raise self._translate_error(exc, model) from exc

        text = ""
        message = data.get("message", {})
        for block in message.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")

        text = text.strip()
        if not text:
            raise GenerationFailedError(
                f"Cohere returned empty content for model '{model}'.",
                provider=self._config.name,
            )

        usage_data = data.get("usage", {})
        tokens = usage_data.get("tokens", {})
        usage = TokenUsage(
            prompt_tokens=tokens.get("input_tokens", 0),
            completion_tokens=tokens.get("output_tokens", 0),
            total_tokens=tokens.get("input_tokens", 0) + tokens.get("output_tokens", 0),
        )

        finish_reason = data.get("finish_reason", "stop")

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
        """List available Cohere models via GET /v1/models."""
        if not self._initialized:
            self.initialize()

        base_url = self._get_base_url()
        logger.info("[Cohere] Listing models: GET %s/v1/models", base_url)

        try:
            response = self._client.get("/v1/models")
            logger.info("[Cohere] Response status: %d", response.status_code)

            if response.status_code != 200:
                self._handle_error(response.status_code, response.text)

            data = response.json()
            models = []
            for model in data.get("models", []):
                model_name = model.get("name")
                if model_name:
                    models.append(str(model_name))
                    logger.debug("[Cohere] Model: %s", model_name)

            logger.info("[Cohere] Found %d models", len(models))
            return sorted(models)
        except (InvalidAPIKeyError, QuotaExceededError, RateLimitedError,
                ModelNotFoundError, NetworkError):
            raise
        except Exception as exc:
            logger.error("[Cohere] list_models failed: %s: %s", type(exc).__name__, exc, exc_info=True)
            raise ProviderError(
                f"Failed to list Cohere models: {exc}",
                provider=self._config.name,
                cause=exc,
            ) from exc

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_text=True,
            supports_streaming=False,
            supports_vision=False,
            supports_json=True,
            supports_reasoning=False,
            supports_tool_calling=False,
            supports_image_generation=False,
            supports_model_listing=True,
        )

    def _handle_error(self, status_code: int, body: str) -> None:
        """Translate HTTP status codes into standardized exceptions."""
        logger.error("[Cohere] HTTP %d: %s", status_code, body[:500])
        try:
            error_data = json.loads(body)
            error_msg = error_data.get("message", body)
        except (json.JSONDecodeError, AttributeError):
            error_msg = body

        if status_code == 401:
            raise InvalidAPIKeyError(
                f"Cohere API key is invalid: {error_msg}",
                provider=self._config.name,
            )
        if status_code == 429:
            raise RateLimitedError(
                f"Cohere rate limited: {error_msg}",
                provider=self._config.name,
            )
        if status_code == 402:
            raise QuotaExceededError(
                f"Cohere quota exceeded: {error_msg}",
                provider=self._config.name,
            )
        if status_code == 404:
            raise ModelNotFoundError(
                f"Cohere model not found: {error_msg}",
                provider=self._config.name,
            )
        raise GenerationFailedError(
            f"Cohere API error {status_code}: {error_msg}",
            provider=self._config.name,
        )

    def _translate_error(self, exc: Exception, model: str) -> ProviderError:
        """Translate an exception into a standardized error."""
        error_str = str(exc).lower()
        if "connect" in error_str or "timeout" in error_str or "network" in error_str:
            return NetworkError(
                f"Cohere network error: {exc}",
                provider=self._config.name,
                cause=exc,
            )
        return GenerationFailedError(
            f"Cohere generation failed: {exc}",
            provider=self._config.name,
            cause=exc,
        )
