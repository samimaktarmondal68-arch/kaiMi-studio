from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable

from providers.base_provider import BaseProvider


class _GeminiProviderAdapter(BaseProvider):
    """Adapter that exposes the providers BaseProvider interface for Gemini."""

    def __init__(self, config: dict | None = None) -> None:
        self._config = config or {}
        self._api_key = (self._config.get("api_key") or "").strip() or os.getenv("GEMINI_API_KEY")

    def generate(self, prompt: str) -> str:
        from core.ai.gemini_provider import GeminiProvider

        provider = GeminiProvider(api_key=self._api_key or None)
        return provider.generate(prompt)

    def validate_configuration(self) -> bool:
        return bool(self._api_key)

    def get_provider_name(self) -> str:
        return "Gemini"

    def get_supported_features(self) -> dict:
        return {
            "text_generation": True,
            "chat": True,
            "streaming": False,
        }


class _PlaceholderProvider(BaseProvider):
    """Placeholder provider for future implementations."""

    def __init__(self, provider_name: str) -> None:
        self._provider_name = provider_name

    def generate(self, prompt: str) -> str:
        raise NotImplementedError(f"{self._provider_name} provider is not implemented yet.")

    def validate_configuration(self) -> bool:
        return False

    def get_provider_name(self) -> str:
        return self._provider_name

    def get_supported_features(self) -> dict:
        return {
            "text_generation": False,
            "chat": False,
            "streaming": False,
        }


class ProviderManager:
    """Manages AI provider registration, configuration, and active provider selection."""

    PROVIDER_NAMES = ("gemini", "openrouter", "deepseek", "openai", "claude", "ollama")

    def __init__(self, config_path: str | Path | None = None) -> None:
        self._config_path = Path(config_path) if config_path else Path(__file__).resolve().parent.parent / "config" / "providers.json"
        self._factories: dict[str, Callable[[], BaseProvider]] = {}
        self._instances: dict[str, BaseProvider] = {}
        self._config = self._load_configuration()
        self._register_all_providers()

    def _default_configuration(self) -> dict:
        return {
            "active_provider": "gemini",
            "providers": {
                "gemini": {"enabled": True, "api_key": ""},
                "openrouter": {"enabled": False, "api_key": ""},
                "deepseek": {"enabled": False, "api_key": ""},
                "openai": {"enabled": False, "api_key": ""},
                "claude": {"enabled": False, "api_key": ""},
                "ollama": {"enabled": False, "url": "http://localhost:11434"},
            },
        }

    def _load_configuration(self) -> dict:
        if not self._config_path.exists():
            return self._default_configuration()

        try:
            with open(self._config_path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return self._default_configuration()

        config = self._default_configuration()
        if isinstance(loaded, dict):
            active = loaded.get("active_provider")
            if isinstance(active, str) and active.strip():
                config["active_provider"] = active.strip().lower()

            providers = loaded.get("providers")
            if isinstance(providers, dict):
                for name in self.PROVIDER_NAMES:
                    provider_cfg = providers.get(name)
                    if isinstance(provider_cfg, dict):
                        config["providers"][name].update(provider_cfg)
        return config

    def _save_configuration(self) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_path, "w", encoding="utf-8") as handle:
            json.dump(self._config, handle, indent=4)

    def register_provider(self, name: str, factory: Callable[[], BaseProvider]) -> None:
        self._factories[name.strip().lower()] = factory

    def _register_all_providers(self) -> None:
        self.register_provider(
            "gemini",
            lambda: _GeminiProviderAdapter(self._config["providers"].get("gemini", {})),
        )
        self.register_provider("openrouter", lambda: _PlaceholderProvider("OpenRouter"))
        self.register_provider("deepseek", lambda: _PlaceholderProvider("DeepSeek"))
        self.register_provider("openai", lambda: _PlaceholderProvider("OpenAI"))
        self.register_provider("claude", lambda: _PlaceholderProvider("Claude"))
        self.register_provider("ollama", lambda: _PlaceholderProvider("Ollama"))

    def get_registered_providers(self) -> list[str]:
        return sorted(self._factories.keys())

    def get_active_provider_name(self) -> str:
        active = str(self._config.get("active_provider", "gemini")).strip().lower()
        return active if active in self._factories else "gemini"

    def set_active_provider(self, provider_name: str, persist: bool = True) -> None:
        name = provider_name.strip().lower()
        if name not in self._factories:
            raise ValueError(f"Unknown provider: {provider_name}")
        self._config["active_provider"] = name
        if persist:
            self._save_configuration()

    def _get_provider(self, provider_name: str) -> BaseProvider:
        name = provider_name.strip().lower()
        if name not in self._factories:
            raise ValueError(f"Unknown provider: {provider_name}")
        if name not in self._instances:
            self._instances[name] = self._factories[name]()
        return self._instances[name]

    def get_active_provider(self) -> BaseProvider:
        return self._get_provider(self.get_active_provider_name())

    def validate_provider_configuration(self, provider_name: str | None = None) -> bool:
        target = provider_name.strip().lower() if provider_name else self.get_active_provider_name()
        provider = self._get_provider(target)
        return provider.validate_configuration()

    def get_provider_capabilities(self, provider_name: str | None = None) -> dict:
        target = provider_name.strip().lower() if provider_name else self.get_active_provider_name()
        provider = self._get_provider(target)
        return provider.get_supported_features()
