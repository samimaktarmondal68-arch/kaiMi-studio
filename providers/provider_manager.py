# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""ProviderManager — the single gateway for AI generation.

Operators call ProviderManager.generate(GenerationRequest) and receive
a GenerationResponse. ProviderManager handles provider selection,
initialization, validation, and configuration internally.

No operator should ever know which concrete provider is active.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from providers.base_provider import BaseProvider
from providers.exceptions import (
    GenerationFailedError,
    ProviderError,
    ProviderNotConfiguredError,
    QuotaExceededError,
    RateLimitedError,
    NetworkError,
)
from providers.models import (
    GenerationRequest,
    GenerationResponse,
    ProviderCapabilities,
    ProviderConfig,
)
from providers.registry import ProviderRegistry

logger = logging.getLogger("kaimi_studio.providers.manager")

# Provider metadata: display name, default base URL, whether API key is required
PROVIDER_METADATA: dict[str, dict] = {
    "gemini": {
        "display_name": "Gemini",
        "base_url": "",
        "requires_key": True,
        "description": "Google Gemini",
    },
    "anthropic": {
        "display_name": "Anthropic",
        "base_url": "https://api.anthropic.com",
        "requires_key": True,
        "description": "Claude by Anthropic",
    },
    "openai": {
        "display_name": "OpenAI",
        "base_url": "https://api.openai.com",
        "requires_key": True,
        "description": "GPT models by OpenAI",
    },
    "openrouter": {
        "display_name": "OpenRouter",
        "base_url": "https://openrouter.ai/api",
        "requires_key": True,
        "description": "Multi-model router",
    },
    "opencode": {
        "display_name": "OpenCode",
        "base_url": "https://opencode.ai/zen",
        "requires_key": True,
        "description": "OpenCode Zen API",
    },
    "groq": {
        "display_name": "Groq",
        "base_url": "https://api.groq.com/openai",
        "requires_key": True,
        "description": "Groq LPU inference",
    },
    "deepseek": {
        "display_name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "requires_key": True,
        "description": "DeepSeek AI",
    },
    "mistral": {
        "display_name": "Mistral",
        "base_url": "https://api.mistral.ai",
        "requires_key": True,
        "description": "Mistral AI",
    },
    "cohere": {
        "display_name": "Cohere",
        "base_url": "https://api.cohere.com",
        "requires_key": True,
        "description": "Command models by Cohere",
    },
    "xai": {
        "display_name": "xAI",
        "base_url": "https://api.x.ai",
        "requires_key": True,
        "description": "Grok by xAI",
    },
    "ollama": {
        "display_name": "Ollama",
        "base_url": "http://localhost:11434/v1",
        "requires_key": False,
        "description": "Local models via Ollama",
    },
    "lmstudio": {
        "display_name": "LM Studio",
        "base_url": "http://localhost:1234/v1",
        "requires_key": False,
        "description": "Local models via LM Studio",
    },
    "localai": {
        "display_name": "LocalAI",
        "base_url": "http://localhost:8080/v1",
        "requires_key": False,
        "description": "Local models via LocalAI",
    },
    "vllm": {
        "display_name": "vLLM",
        "base_url": "http://localhost:8000/v1",
        "requires_key": False,
        "description": "Local models via vLLM",
    },
    "llamacpp": {
        "display_name": "llama.cpp",
        "base_url": "http://localhost:8080/v1",
        "requires_key": False,
        "description": "Local models via llama.cpp Server",
    },
    "textgenwebui": {
        "display_name": "Text Gen WebUI",
        "base_url": "http://localhost:5000/v1",
        "requires_key": False,
        "description": "Local models via Text Generation WebUI",
    },
}


class ProviderManager:
    """Manages AI provider lifecycle, configuration, and generation.

    This is the ONLY class operators interact with for AI generation.
    It internally uses a ProviderRegistry to create provider instances
    from registered provider classes.

    Adding a new provider requires only:
        1. Creating a class that inherits BaseProvider
        2. Calling register_provider() with the class
        No operator changes needed.
    """

    def __init__(self, config_path: str | Path | None = None) -> None:
        self._config_path = (
            Path(config_path)
            if config_path
            else Path(__file__).resolve().parent.parent / "config" / "providers.json"
        )
        self._registry = ProviderRegistry()
        self._instances: dict[str, BaseProvider] = {}
        self._config = self._load_configuration()
        self._register_builtin_providers()

    # ── Provider registration ────────────────────────────────────────

    def register_provider(self, name: str, provider_class: type[BaseProvider]) -> None:
        """Register a provider class. This is the extension point."""
        self._registry.register(name, provider_class)

    def _register_builtin_providers(self) -> None:
        from providers.gemini_provider import GeminiProvider
        from providers.opencode_provider import OpenAICompatibleProvider
        from providers.anthropic_provider import AnthropicProvider
        from providers.cohere_provider import CohereProvider

        # Gemini (custom SDK)
        self._registry.register("gemini", GeminiProvider)

        # Anthropic (custom HTTP)
        self._registry.register("anthropic", AnthropicProvider)

        # Cohere (custom HTTP)
        self._registry.register("cohere", CohereProvider)

        # All OpenAI-compatible cloud providers
        self._registry.register("openai", OpenAICompatibleProvider)
        self._registry.register("openrouter", OpenAICompatibleProvider)
        self._registry.register("opencode", OpenAICompatibleProvider)
        self._registry.register("groq", OpenAICompatibleProvider)
        self._registry.register("deepseek", OpenAICompatibleProvider)
        self._registry.register("mistral", OpenAICompatibleProvider)
        self._registry.register("xai", OpenAICompatibleProvider)

        # All OpenAI-compatible local providers
        self._registry.register("ollama", OpenAICompatibleProvider)
        self._registry.register("lmstudio", OpenAICompatibleProvider)
        self._registry.register("localai", OpenAICompatibleProvider)
        self._registry.register("vllm", OpenAICompatibleProvider)
        self._registry.register("llamacpp", OpenAICompatibleProvider)
        self._registry.register("textgenwebui", OpenAICompatibleProvider)

    # ── Provider metadata ────────────────────────────────────────────

    def get_provider_metadata(self, provider_name: str | None = None) -> dict:
        """Return metadata for a provider (display name, base URL, requires_key, etc)."""
        target = provider_name.strip().lower() if provider_name else self.get_active_provider_name()
        return dict(PROVIDER_METADATA.get(target, {
            "display_name": target.title(),
            "base_url": "",
            "requires_key": True,
            "description": "",
        }))

    def get_all_provider_metadata(self) -> dict[str, dict]:
        """Return metadata for all registered providers."""
        result = {}
        for name in self._registry.get_registered_names():
            result[name] = self.get_provider_metadata(name)
        return result

    def provider_requires_key(self, provider_name: str | None = None) -> bool:
        """Check if a provider requires an API key (local providers don't)."""
        target = provider_name.strip().lower() if provider_name else self.get_active_provider_name()
        meta = PROVIDER_METADATA.get(target, {})
        return meta.get("requires_key", True)

    def show_base_url(self, provider_name: str | None = None) -> bool:
        """Check if the base URL field should be shown for a provider."""
        target = provider_name.strip().lower() if provider_name else self.get_active_provider_name()
        meta = PROVIDER_METADATA.get(target, {})
        return bool(meta.get("base_url", ""))

    # ── Configuration ────────────────────────────────────────────────

    def _default_configuration(self) -> dict:
        providers = {}
        for name, meta in PROVIDER_METADATA.items():
            providers[name] = {
                "enabled": name == "gemini",
                "api_key": "",
                "base_url": meta["base_url"],
                "model": "",
            }
        return {
            "active_provider": "gemini",
            "providers": providers,
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
                for name, provider_cfg in providers.items():
                    if isinstance(provider_cfg, dict):
                        key = name.strip().lower()
                        if key not in config["providers"]:
                            config["providers"][key] = {}
                        config["providers"][key].update(provider_cfg)
        return config

    def _save_configuration(self) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_path, "w", encoding="utf-8") as handle:
            json.dump(self._config, handle, indent=4)

    # ── Provider config access ───────────────────────────────────────

    def get_provider_config(self, provider_name: str) -> dict:
        """Return the raw config dict for a provider."""
        name = provider_name.strip().lower()
        return dict(self._config.get("providers", {}).get(name, {}))

    def get_provider_model(self, provider_name: str | None = None) -> str:
        """Return the configured model for a provider."""
        target = provider_name.strip().lower() if provider_name else self.get_active_provider_name()
        cfg = self._config.get("providers", {}).get(target, {})
        return cfg.get("model", "")

    def get_provider_api_key(self, provider_name: str | None = None) -> str:
        """Return the configured API key for a provider."""
        target = provider_name.strip().lower() if provider_name else self.get_active_provider_name()
        cfg = self._config.get("providers", {}).get(target, {})
        return cfg.get("api_key", "")

    def get_provider_base_url(self, provider_name: str | None = None) -> str:
        """Return the configured base URL for a provider."""
        target = provider_name.strip().lower() if provider_name else self.get_active_provider_name()
        cfg = self._config.get("providers", {}).get(target, {})
        return cfg.get("base_url", "")

    def set_provider_api_key(self, provider_name: str, api_key: str) -> None:
        """Update the API key for a provider and evict cached instance."""
        name = provider_name.strip().lower()
        providers = self._config.setdefault("providers", {})
        if name not in providers:
            providers[name] = {}
        providers[name]["api_key"] = api_key.strip()
        self._instances.pop(name, None)
        self._save_configuration()

    def set_provider_base_url(self, provider_name: str, base_url: str) -> None:
        """Update the base URL for a provider and evict cached instance."""
        name = provider_name.strip().lower()
        providers = self._config.setdefault("providers", {})
        if name not in providers:
            providers[name] = {}
        providers[name]["base_url"] = base_url.strip()
        self._instances.pop(name, None)
        self._save_configuration()

    def set_provider_model(self, provider_name: str, model: str) -> None:
        """Update the model for a provider and evict cached instance."""
        name = provider_name.strip().lower()
        providers = self._config.setdefault("providers", {})
        if name not in providers:
            providers[name] = {}
        providers[name]["model"] = model.strip()
        self._instances.pop(name, None)
        self._save_configuration()

    def save_provider_config(self, provider_name: str, api_key: str = "", base_url: str = "", model: str = "") -> None:
        """Save all provider config fields at once and evict cached instance."""
        name = provider_name.strip().lower()
        providers = self._config.setdefault("providers", {})
        if name not in providers:
            providers[name] = {}
        if api_key != "":
            providers[name]["api_key"] = api_key.strip()
        if base_url != "":
            providers[name]["base_url"] = base_url.strip()
        if model != "":
            providers[name]["model"] = model.strip()
        self._instances.pop(name, None)
        self._save_configuration()

    # ── Active provider management ───────────────────────────────────

    def get_active_provider_name(self) -> str:
        """Return the currently active provider name."""
        active = str(self._config.get("active_provider", "gemini")).strip().lower()
        if self._registry.is_registered(active):
            return active
        return "gemini" if self._registry.is_registered("gemini") else ""

    def set_active_provider(self, provider_name: str, persist: bool = True) -> None:
        """Switch the active provider."""
        name = provider_name.strip().lower()
        if not self._registry.is_registered(name):
            raise ValueError(f"Unknown provider: {provider_name}")
        self._config["active_provider"] = name
        if persist:
            self._save_configuration()

    def get_registered_providers(self) -> list[str]:
        """Return sorted list of registered provider names."""
        return self._registry.get_registered_names()

    # ── Provider instance management ─────────────────────────────────

    def _build_provider_config(self, name: str) -> ProviderConfig:
        """Build a ProviderConfig from the stored configuration."""
        raw = self._config.get("providers", {}).get(name, {})
        return ProviderConfig(
            name=name,
            api_key=raw.get("api_key", ""),
            base_url=raw.get("base_url", ""),
            model=raw.get("model", ""),
            enabled=raw.get("enabled", False),
        )

    def _get_provider(self, provider_name: str) -> BaseProvider:
        """Get or create a provider instance by name."""
        name = provider_name.strip().lower()
        if not self._registry.is_registered(name):
            raise ValueError(f"Unknown provider: {provider_name}")

        if name not in self._instances:
            provider_config = self._build_provider_config(name)
            logger.info(
                "[Manager] Creating provider '%s': api_key=%s, base_url=%s, model=%s",
                name,
                "SET" if provider_config.api_key else "EMPTY",
                provider_config.base_url or "(none)",
                provider_config.model or "(none)",
            )
            self._instances[name] = self._registry.create(name, provider_config)

        return self._instances[name]

    def get_active_provider(self) -> BaseProvider:
        """Get the active provider instance."""
        return self._get_provider(self.get_active_provider_name())

    # ── Validation & capabilities ────────────────────────────────────

    def validate_provider_configuration(self, provider_name: str | None = None) -> bool:
        """Check if a provider has a valid API key configured."""
        target = provider_name.strip().lower() if provider_name else self.get_active_provider_name()
        raw = self._config.get("providers", {}).get(target, {})
        api_key = raw.get("api_key", "").strip()
        return bool(api_key)

    def get_provider_capabilities(self, provider_name: str | None = None) -> ProviderCapabilities:
        """Return the capabilities of a provider."""
        target = provider_name.strip().lower() if provider_name else self.get_active_provider_name()
        provider = self._get_provider(target)
        return provider.get_capabilities()

    def test_provider_connection(self, provider_name: str | None = None) -> tuple[bool, str]:
        """Test if a provider is accessible.

        Returns:
            Tuple of (success, message).
        """
        target = provider_name.strip().lower() if provider_name else self.get_active_provider_name()
        logger.info("[Manager] test_provider_connection: provider=%s", target)
        try:
            provider = self._get_provider(target)
            is_valid = provider.validate_key()
            logger.info("[Manager] validate_key result: %s", is_valid)
            if is_valid:
                return True, f"{target.title()} connection successful."
            return False, f"{target.title()} API key is invalid."
        except Exception as exc:
            logger.error(
                "[Manager] test_provider_connection failed for '%s': %s: %s",
                target, type(exc).__name__, exc,
                exc_info=True,
            )
            return False, f"{target.title()} connection failed: {exc}"

    def list_models(self, provider_name: str | None = None) -> list[str]:
        """List available models for a provider."""
        target = provider_name.strip().lower() if provider_name else self.get_active_provider_name()
        logger.info("[Manager] list_models: provider=%s", target)

        try:
            provider = self._get_provider(target)
            logger.info("[Manager] Provider instance: %s, initialized=%s", type(provider).__name__, provider.is_initialized)

            api_key = self._config.get("providers", {}).get(target, {}).get("api_key", "")
            base_url = self._config.get("providers", {}).get(target, {}).get("base_url", "")
            logger.info(
                "[Manager] Config: api_key=%s, base_url=%s",
                "SET" if api_key else "EMPTY",
                base_url or "(none)",
            )

            result = provider.list_models()
            logger.info("[Manager] list_models returned %d models", len(result))
            return result
        except Exception as exc:
            logger.error(
                "[Manager] list_models failed for '%s': %s: %s",
                target, type(exc).__name__, exc,
                exc_info=True,
            )
            return []

    # ── Auto-failover sequence ───────────────────────────────────────

    FAILOVER_SEQUENCE = [
        "gemini",
        "openrouter",
        "groq",
        "deepseek",
        "openai",
        "anthropic",
        "mistral",
        "xai",
        "cohere",
    ]

    # ── Core generation ──────────────────────────────────────────────

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate text using the active provider with automatic failover.

        Tries the active provider first. If it fails with a quota or rate
        limit error, automatically falls back through the failover sequence.

        Args:
            request: Standard generation request.

        Returns:
            Standard generation response with text and metadata.

        Raises:
            ProviderNotConfiguredError: If no provider is configured.
            ProviderError: For any unrecoverable provider-level failure.
        """
        provider_name = self.get_active_provider_name()
        if not provider_name:
            raise ProviderNotConfiguredError("No active provider configured.")

        attempted = set()

        while provider_name and provider_name not in attempted:
            attempted.add(provider_name)

            provider = self._get_provider(provider_name)

            if not provider.validate_key():
                last_error = ProviderNotConfiguredError(
                    f"Provider '{provider_name}' is not configured.",
                    provider=provider_name,
                )
                provider_name = self._get_next_failover(provider_name, attempted)
                continue

            try:
                if not provider.is_initialized:
                    provider.initialize()
            except Exception as exc:
                last_error = exc
                provider_name = self._get_next_failover(provider_name, attempted)
                continue

            try:
                return provider.generate(request)
            except QuotaExceededError as exc:
                logger.warning(
                    "[Manager] Quota exceeded for '%s', failing over", provider_name,
                )
                last_error = exc
                provider_name = self._get_next_failover(provider_name, attempted)
                continue
            except RateLimitedError as exc:
                logger.warning(
                    "[Manager] Rate limited for '%s', failing over", provider_name,
                )
                last_error = exc
                provider_name = self._get_next_failover(provider_name, attempted)
                continue
            except NetworkError as exc:
                logger.warning(
                    "[Manager] Network error for '%s', failing over", provider_name,
                )
                last_error = exc
                provider_name = self._get_next_failover(provider_name, attempted)
                continue
            except ProviderError:
                raise
            except NotImplementedError as exc:
                raise ProviderError(
                    f"Provider '{provider_name}' is not implemented: {exc}",
                    provider=provider_name,
                    cause=exc,
                ) from exc
            except Exception as exc:
                raise GenerationFailedError(
                    f"Generation failed with provider '{provider_name}': {exc}",
                    provider=provider_name,
                    cause=exc,
                ) from exc

        raise GenerationFailedError(
            "All available providers exhausted. "
            f"Last error: {last_error}",
        ) from (last_error if isinstance(last_error, Exception) else None)

    def _get_next_failover(self, current: str, attempted: set) -> str | None:
        """Find the next un-attempted provider in the failover sequence."""
        for name in self.FAILOVER_SEQUENCE:
            if name not in attempted and self._registry.is_registered(name):
                cfg = self._config.get("providers", {}).get(name, {})
                if cfg.get("api_key", "").strip():
                    return name
        return None
