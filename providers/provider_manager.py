"""ProviderManager — the single gateway for AI generation.

Operators call ProviderManager.generate(GenerationRequest) and receive
a GenerationResponse. ProviderManager handles provider selection,
initialization, validation, and configuration internally.

No operator should ever know which concrete provider is active.
"""

from __future__ import annotations

import json
from pathlib import Path

from providers.base_provider import BaseProvider
from providers.exceptions import (
    GenerationFailedError,
    ProviderError,
    ProviderNotConfiguredError,
)
from providers.models import (
    GenerationRequest,
    GenerationResponse,
    ProviderCapabilities,
    ProviderConfig,
)
from providers.registry import ProviderRegistry


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

        self._registry.register("gemini", GeminiProvider)
        self._registry.register("opencode", OpenAICompatibleProvider)

    # ── Configuration ────────────────────────────────────────────────

    def _default_configuration(self) -> dict:
        return {
            "active_provider": "gemini",
            "providers": {
                "gemini": {
                    "enabled": True,
                    "api_key": "",
                    "model": "gemini-2.0-flash",
                },
                "opencode": {
                    "enabled": False,
                    "api_key": "",
                    "base_url": "https://opencode.ai/zen",
                    "model": "",
                },
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
        try:
            provider = self._get_provider(target)
            is_valid = provider.validate_key()
            if is_valid:
                return True, f"{target.title()} connection successful."
            return False, f"{target.title()} API key is invalid."
        except Exception as exc:
            return False, f"{target.title()} connection failed: {exc}"

    def list_models(self, provider_name: str | None = None) -> list[str]:
        """List available models for a provider."""
        target = provider_name.strip().lower() if provider_name else self.get_active_provider_name()
        try:
            provider = self._get_provider(target)
            return provider.list_models()
        except Exception:
            return []

    # ── Core generation ──────────────────────────────────────────────

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate text using the active provider.

        This is the primary method operators call. It handles:
        1. Obtaining the active provider
        2. Initializing it if needed
        3. Validating configuration
        4. Generating text
        5. Translating errors to standardized exceptions

        Args:
            request: Standard generation request.

        Returns:
            Standard generation response with text and metadata.

        Raises:
            ProviderNotConfiguredError: If the provider has no API key.
            ProviderError: For any provider-level failure.
        """
        provider_name = self.get_active_provider_name()
        if not provider_name:
            raise ProviderNotConfiguredError("No active provider configured.")

        provider = self._get_provider(provider_name)

        if not provider.validate_key():
            raise ProviderNotConfiguredError(
                f"Provider '{provider_name}' is not configured. "
                "Set a valid API key in Settings.",
                provider=provider_name,
            )

        try:
            if not provider.is_initialized:
                provider.initialize()
        except Exception as exc:
            if isinstance(exc, ProviderError):
                raise
            raise ProviderError(
                f"Failed to initialize provider '{provider_name}': {exc}",
                provider=provider_name,
                cause=exc,
            ) from exc

        try:
            return provider.generate(request)
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
