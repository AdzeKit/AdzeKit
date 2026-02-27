"""LLM client for AdzeKit.

Thin wrapper around the Anthropic SDK. Reads ANTHROPIC_API_KEY from
environment or .env file. All agent interactions go through this module.
"""

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """LLM configuration. Reads from env / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key.",
    )
    anthropic_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Anthropic model ID.",
    )
    max_tokens: int = Field(
        default=4096,
        description="Maximum tokens per response.",
    )


def get_llm_settings() -> LLMSettings:
    return LLMSettings()


def create_client(settings: LLMSettings | None = None):
    """Create an Anthropic client instance."""
    from anthropic import Anthropic

    settings = settings or get_llm_settings()
    api_key = settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY is not set. "
            "Set it in your environment or in a .env file."
        )
    return Anthropic(api_key=api_key)


def chat(
    messages: list[dict],
    system: str = "",
    tools: list[dict] | None = None,
    settings: LLMSettings | None = None,
) -> dict:
    """Send a message to Claude and return the full response.

    Args:
        messages: Conversation history in Anthropic format.
        system: System prompt.
        tools: Tool definitions in Anthropic schema.
        settings: LLM settings override.

    Returns:
        The raw Anthropic API response as a dict-like object.
    """
    settings = settings or get_llm_settings()
    client = create_client(settings)

    kwargs: dict = {
        "model": settings.anthropic_model,
        "max_tokens": settings.max_tokens,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system
    if tools:
        kwargs["tools"] = tools

    return client.messages.create(**kwargs)
