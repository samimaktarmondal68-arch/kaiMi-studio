# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Provider registry for managing provider factories.

The registry allows registering provider classes by name. When a new
provider is needed, the registry creates an instance from the registered
factory. Adding a new provider requires only registration — no operator
changes.
"""

from __future__ import annotations

from providers.base_provider import BaseProvider
from providers.models import ProviderConfig


class ProviderRegistry:
    """Registry of provider factories keyed by provider name.

    Usage:
        registry = ProviderRegistry()
        registry.register("gemini", GeminiProvider)
        registry.register("opencode", OpenAICompatibleProvider)

        provider = registry.create("gemini", config)
    """

    def __init__(self) -> None:
        self._factories: dict[str, type[BaseProvider]] = {}

    def register(self, name: str, provider_class: type[BaseProvider]) -> None:
        """Register a provider class under the given name.

        Args:
            name: Lowercase provider identifier (e.g. 'gemini', 'opencode').
            provider_class: A class that inherits from BaseProvider.
        """
        key = name.strip().lower()
        if not issubclass(provider_class, BaseProvider):
            raise TypeError(
                f"Provider class must inherit from BaseProvider. "
                f"Got {provider_class.__name__}."
            )
        self._factories[key] = provider_class

    def create(self, name: str, config: ProviderConfig) -> BaseProvider:
        """Create a new provider instance from the registered factory.

        Args:
            name: Lowercase provider identifier.
            config: Configuration for the provider instance.

        Returns:
            A new BaseProvider instance.

        Raises:
            ValueError: If no provider is registered under the given name.
        """
        key = name.strip().lower()
        if key not in self._factories:
            raise ValueError(
                f"No provider registered with name '{key}'. "
                f"Available: {self.get_registered_names()}"
            )
        return self._factories[key](config)

    def get_registered_names(self) -> list[str]:
        """Return sorted list of registered provider names."""
        return sorted(self._factories.keys())

    def is_registered(self, name: str) -> bool:
        """Check if a provider is registered under the given name."""
        return name.strip().lower() in self._factories
