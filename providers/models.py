# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProviderConfig:
    """Configuration for a single AI provider instance."""

    name: str
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    enabled: bool = False
    extra: dict = field(default_factory=dict)

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key) or bool(self.base_url)


@dataclass
class GenerationRequest:
    """Standard request object for AI text generation.

    Operators create this object and pass it to ProviderManager.generate().
    Providers receive this object and use its fields to configure the API call.
    """

    prompt: str
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 8192
    model: str = ""
    response_format: str = ""


@dataclass
class TokenUsage:
    """Token usage statistics from a generation response."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class GenerationResponse:
    """Standard response object from AI text generation.

    Providers return this object. Operators extract .text from it.
    No provider-specific response objects should reach operators.
    """

    text: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    finish_reason: str = "stop"
    provider: str = ""
    model: str = ""


@dataclass
class ProviderCapabilities:
    """Advertised capabilities of an AI provider.

    Operators use capability detection instead of provider-specific conditionals.
    """

    supports_text: bool = True
    supports_streaming: bool = False
    supports_vision: bool = False
    supports_json: bool = False
    supports_reasoning: bool = False
    supports_tool_calling: bool = False
    supports_image_generation: bool = False
    supports_model_listing: bool = False
