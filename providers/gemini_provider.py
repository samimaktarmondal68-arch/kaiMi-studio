# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Google Gemini provider implementation.

Uses the google-genai SDK for text generation.
Migrates and extends the logic from core/ai/gemini_provider.py
while conforming to the new BaseProvider interface.
"""

from __future__ import annotations

import logging
import os

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

logger = logging.getLogger("kaimi_studio.providers.gemini")

DEFAULT_MODEL = "gemini-2.0-flash"


class GeminiProvider(BaseProvider):
    """Google Gemini text generation provider.

    Supports text generation using the google-genai SDK.
    Model is configurable via ProviderConfig.model.
    """

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client = None
        self._resolved_model = config.model.strip() or DEFAULT_MODEL

    def initialize(self) -> None:
        """Create the Gemini SDK client."""
        api_key = self._config.api_key.strip()
        if not api_key:
            api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise InvalidAPIKeyError(
                "No API key configured for Gemini. "
                "Set it in Settings or via GEMINI_API_KEY environment variable.",
                provider="gemini",
            )

        try:
            from google import genai
        except ImportError as exc:
            raise ProviderError(
                "Gemini SDK is not installed. Run: pip install google-genai",
                provider="gemini",
                cause=exc,
            ) from exc

        try:
            logger.info("[Gemini] Initializing client with google-genai SDK")
            self._client = genai.Client(api_key=api_key)
            logger.info("[Gemini] Client created successfully")
        except Exception as exc:
            logger.error("[Gemini] Failed to initialize client: %s: %s", type(exc).__name__, exc, exc_info=True)
            raise ProviderError(
                f"Failed to initialize Gemini client: {exc}",
                provider="gemini",
                cause=exc,
            ) from exc

        super().initialize()

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate text using the Gemini API."""
        if not self._initialized:
            self.initialize()

        model = request.model.strip() or self._resolved_model
        prompt = request.prompt
        config = None
        if request.response_format == "json_array":
            config = {"response_mime_type": "application/json"}

        try:
            kwargs = {"model": model, "contents": prompt}
            if config is not None:
                kwargs["config"] = config
            response = self._client.models.generate_content(**kwargs)
        except Exception as exc:
            raise self._translate_error(exc, model) from exc

        text = self._extract_text(response)
        if not text:
            raise GenerationFailedError(
                f"Gemini returned empty content for model '{model}'.",
                provider="gemini",
            )

        usage = self._extract_usage(response)

        return GenerationResponse(
            text=text,
            usage=usage,
            finish_reason="stop",
            provider="gemini",
            model=model,
        )

    def validate_key(self) -> bool:
        """Validate the Gemini API key with a real API request.

        Performs a lightweight models.list() call. Auth problems (401/403, or
        400 with an API-key message) report failure; endpoints that answer but
        do not expose model listing are treated as connected.
        """
        if not self._initialized:
            try:
                self.initialize()
            except (InvalidAPIKeyError, ProviderError):
                return False

        try:
            self._client.models.list()
            return True
        except Exception as exc:
            status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
            error_str = str(exc).lower()
            if status_code in (404, 405):
                return True
            if status_code in (401, 403):
                return False
            if status_code == 400 and "api key" in error_str:
                return False
            logger.error("[Gemini] validate_key failed: %s: %s", type(exc).__name__, exc)
            return False

    def list_models(self) -> list[str]:
        """List available Gemini models."""
        if not self._initialized:
            self.initialize()

        try:
            logger.info("[Gemini] Listing models via SDK models.list()")
            response = self._client.models.list()
            logger.info("[Gemini] Response type: %s", type(response).__name__)

            models = []
            for model in response:
                name = getattr(model, "name", None)
                display_name = getattr(model, "display_name", None)
                if name:
                    short_name = str(name).split("/")[-1]
                    models.append(short_name)
                    logger.debug("[Gemini] Model: name=%s -> %s, display=%s", name, short_name, display_name)

            logger.info("[Gemini] Found %d models", len(models))
            return sorted(models)
        except Exception as exc:
            logger.error("[Gemini] list_models failed: %s: %s", type(exc).__name__, exc, exc_info=True)
            return [DEFAULT_MODEL]

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

    def _extract_text(self, response) -> str:
        """Extract text from a Gemini response object."""
        text = getattr(response, "text", None)
        if text:
            return str(text).strip()

        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            collected: list[str] = []
            for part in parts:
                part_text = getattr(part, "text", None)
                if part_text:
                    collected.append(str(part_text))
            if collected:
                return "\n".join(collected).strip()

        return ""

    def _extract_usage(self, response) -> TokenUsage:
        """Extract token usage from a Gemini response object."""
        usage_metadata = getattr(response, "usage_metadata", None)
        if not usage_metadata:
            return TokenUsage()

        return TokenUsage(
            prompt_tokens=getattr(usage_metadata, "prompt_token_count", 0) or 0,
            completion_tokens=getattr(usage_metadata, "candidates_token_count", 0) or 0,
            total_tokens=getattr(usage_metadata, "total_token_count", 0) or 0,
        )

    def _translate_error(self, exc: Exception, model: str) -> ProviderError:
        """Translate a Gemini SDK exception into a standardized error."""
        error_str = str(exc).lower()

        if "api_key" in error_str or "invalid key" in error_str or "permission" in error_str:
            return InvalidAPIKeyError(
                f"Gemini API key is invalid: {exc}",
                provider="gemini",
                cause=exc,
            )
        if "quota" in error_str or "billing" in error_str or "limit" in error_str:
            return QuotaExceededError(
                f"Gemini quota exceeded: {exc}",
                provider="gemini",
                cause=exc,
            )
        if "rate" in error_str and "limit" in error_str:
            return RateLimitedError(
                f"Gemini rate limited: {exc}",
                provider="gemini",
                cause=exc,
            )
        if "not found" in error_str or "404" in error_str:
            return ModelNotFoundError(
                f"Gemini model '{model}' not found: {exc}",
                provider="gemini",
                cause=exc,
            )
        if "connect" in error_str or "timeout" in error_str or "network" in error_str:
            return NetworkError(
                f"Gemini network error: {exc}",
                provider="gemini",
                cause=exc,
            )

        return GenerationFailedError(
            f"Gemini generation failed: {exc}",
            provider="gemini",
            cause=exc,
        )
