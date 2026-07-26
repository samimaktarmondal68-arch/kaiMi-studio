"""Standardized provider exceptions.

Provider implementations catch SDK-specific exceptions and re-raise
as these standardized exceptions. Raw SDK exceptions should never
reach the UI layer.
"""

from __future__ import annotations


class ProviderError(RuntimeError):
    """Base exception for all provider-related errors."""

    def __init__(self, message: str, provider: str = "", cause: Exception | None = None) -> None:
        super().__init__(message)
        self.provider = provider
        self.cause = cause


class InvalidAPIKeyError(ProviderError):
    """Raised when the API key is invalid or rejected by the provider."""


class QuotaExceededError(ProviderError):
    """Raised when the API quota or billing limit has been exceeded."""


class NetworkError(ProviderError):
    """Raised when a network connection fails or times out."""


class RateLimitedError(ProviderError):
    """Raised when the provider rate-limits the request."""


class ModelNotFoundError(ProviderError):
    """Raised when the requested model does not exist or is unavailable."""


class ProviderOfflineError(ProviderError):
    """Raised when the provider service is unreachable or down."""


class ProviderNotConfiguredError(ProviderError):
    """Raised when the provider is missing required configuration (e.g. API key)."""


class GenerationFailedError(ProviderError):
    """Raised when text generation fails for any reason."""
