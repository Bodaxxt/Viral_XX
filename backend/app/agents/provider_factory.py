"""
Provider Factory — detects which AI provider is configured
and returns an instantiated provider adapter (matching Node.js priority order:
Gemini > Anthropic > OpenAI > Local fallback).
"""

from typing import Optional
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.agents.providers import BaseProvider, GeminiProvider, AnthropicProvider, OpenAIProvider


class LocalFallbackProvider(BaseProvider):
    """
    Safe, cost-free local provider used when no API key is configured.
    Delegates to the agent's built-in deterministic orchestrator.
    The call() method is intentionally not implemented here — the agent
    calls orchestrate_local() directly for the local path.
    """
    name = "local"

    async def call(self, *args, **kwargs):
        raise NotImplementedError("LocalFallbackProvider delegates to orchestrate_local() directly.")


def get_provider() -> BaseProvider:
    """
    Returns the highest-priority configured LLM provider.
    Priority: Gemini > Anthropic > OpenAI > Local (no key).
    Never silently switches providers in an unexpected way.
    """
    if settings.GEMINI_API_KEY:
        logger.info("AI provider selected: Gemini (%s)", settings.GEMINI_MODEL)
        return GeminiProvider()

    if settings.ANTHROPIC_API_KEY:
        logger.info("AI provider selected: Anthropic Claude (%s)", settings.ANTHROPIC_MODEL)
        return AnthropicProvider()

    if settings.OPENAI_API_KEY:
        logger.info("AI provider selected: OpenAI (%s)", settings.OPENAI_MODEL)
        return OpenAIProvider()

    logger.info("No AI provider API key configured — using local deterministic orchestrator.")
    return LocalFallbackProvider()


def detect_provider_name() -> str:
    """Returns the active provider name without instantiating the client."""
    if settings.GEMINI_API_KEY:
        return "gemini"
    if settings.ANTHROPIC_API_KEY:
        return "anthropic"
    if settings.OPENAI_API_KEY:
        return "openai"
    return "local"
