# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Provider abstraction layer for KaiMi Studio.

This package provides the multi-provider AI architecture:

- BaseProvider: Abstract interface all providers implement
- ProviderRegistry: Factory for creating provider instances
- ProviderManager: Orchestrates provider lifecycle and configuration
- ProviderConfig, GenerationRequest, GenerationResponse: Standard objects
- ProviderCapabilities: Feature advertisement for capability detection
- Standardized exceptions: Consistent error handling across providers

Adding a new provider:
    1. Create a class that inherits from BaseProvider
    2. Implement all abstract methods
    3. Register it with ProviderRegistry
    4. That's it — no operator changes needed.
"""
