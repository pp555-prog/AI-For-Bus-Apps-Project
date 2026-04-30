"""LLM client for NOCTURNE.

Routes single-turn completions through OpenRouter using the OpenAI SDK.
The active model is set via OPENROUTER_MODEL in .env (default:
openai/gpt-oss-120b:free). To switch providers (Claude, Gemini, GPT,
DeepSeek, Llama, etc.), change OPENROUTER_MODEL — no code change required.
"""

from openai import OpenAI

from backend.config import settings

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not settings.OPENROUTER_API_KEY:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Add it to .env "
                "(get a key at https://openrouter.ai/settings/keys)."
            )
        _client = OpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
        )
    return _client


def complete(
    system_prompt: str,
    user_message: str,
    *,
    model: str | None = None,
    max_tokens: int = 1024,
) -> str:
    """Send a single-turn message to the configured LLM and return the text response."""
    client = _get_client()
    resp = client.chat.completions.create(
        model=model or settings.OPENROUTER_MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return resp.choices[0].message.content or ""
