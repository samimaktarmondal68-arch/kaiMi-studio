# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

from providers.models import (
    GenerationRequest,
    GenerationResponse,
    ProviderCapabilities,
    ProviderConfig,
)


class BaseProvider(ABC):
    """Abstract interface for all AI model providers.

    Every provider must implement this interface. The ProviderManager
    interacts only through this abstraction — operators never know
    which concrete provider is active.

    Lifecycle:
        1. Provider is instantiated with a ProviderConfig
        2. initialize() is called once before first use
        3. generate() / stream() are called for text generation
        4. validate_key() checks API key validity
        5. list_models() returns available models
        6. get_capabilities() advertises supported features
    """

    def __init__(self, config: ProviderConfig) -> None:
        self._config = config
        self._initialized = False

    @property
    def name(self) -> str:
        """Return the provider identifier (e.g. 'gemini', 'opencode')."""
        return self._config.name

    @property
    def config(self) -> ProviderConfig:
        return self._config

    @property
    def is_initialized(self) -> bool:
        """Return True if initialize() has been called."""
        return self._initialized

    def initialize(self) -> None:
        """Initialize the provider (create SDK client, validate config).

        Called once before first generation. Subclasses should override
        to perform one-time setup. The base implementation sets the
        initialized flag.
        """
        self._initialized = True

    @abstractmethod
    def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate a text response for the given request.

        Args:
            request: Standard generation request with prompt and parameters.

        Returns:
            Standard generation response with text, usage, and metadata.

        Raises:
            InvalidAPIKeyError: If the API key is invalid.
            QuotaExceededError: If quota is exceeded.
            NetworkError: If a network error occurs.
            RateLimitedError: If rate-limited.
            ModelNotFoundError: If the model is not available.
            GenerationFailedError: If generation fails.
        """
        raise NotImplementedError

    def stream(self, request: GenerationRequest) -> AsyncIterator[str]:
        """Stream text tokens as they are generated.

        Default implementation raises NotImplementedError.
        Providers that support streaming should override this.

        Yields:
            Text chunks as they arrive from the provider.
        """
        raise NotImplementedError(
            f"Streaming is not supported by provider '{self.name}'."
        )

    @abstractmethod
    def validate_key(self) -> bool:
        """Validate the API key by making a lightweight API call.

        Returns:
            True if the key is valid and the provider is accessible.
        """
        raise NotImplementedError

    def list_models(self) -> list[str]:
        """Return a list of available model identifiers.

        Default implementation returns an empty list.
        Providers that support model listing should override this.

        Returns:
            List of model ID strings, or empty list if not supported.
        """
        return []

    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilities:
        """Return the capabilities advertised by this provider.

        Operators should use capability detection instead of
        provider-specific conditionals.
        """
        raise NotImplementedError
