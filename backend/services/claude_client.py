"""Thin wrapper around the Anthropic SDK."""

import anthropic

from backend.config import settings

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def complete(
    system_prompt: str,
    user_message: str,
    *,
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 1024,
) -> str:
    """Send a single-turn message to Claude and return the text response."""
    client = _get_client()
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text
