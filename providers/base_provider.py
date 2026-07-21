from __future__ import annotations

from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """Abstract interface for all AI model providers."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate a text response for the given prompt."""
        raise NotImplementedError

    @abstractmethod
    def validate_configuration(self) -> bool:
        """Return True when provider configuration is valid and usable."""
        raise NotImplementedError

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the human-readable provider name."""
        raise NotImplementedError

    @abstractmethod
    def get_supported_features(self) -> dict:
        """Return a feature map supported by this provider."""
        raise NotImplementedError