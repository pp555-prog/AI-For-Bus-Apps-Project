"""Lyria 3 music generation client.

Routes through OpenRouter's chat-completions endpoint. The active music model
is set via OPENROUTER_MUSIC_MODEL (default: google/lyria-3-clip-preview, a
~30s clip at $0.04/call). The response shape for music generation isn't
formally documented; this client tries the patterns OpenRouter uses for
multimodal output and returns the raw response alongside the parsed audio
so we can tighten the parser after the first live call.
"""

from __future__ import annotations

import httpx

from backend.config import settings


class LyriaError(RuntimeError):
    """Raised when Lyria music generation fails."""


def is_configured() -> bool:
    return bool(settings.OPENROUTER_API_KEY)


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }


async def generate_clip(prompt: str) -> dict:
    """Generate a music clip from a text prompt. Returns dict with audio_url
    or audio_data_url, plus the raw response for debugging."""
    if not settings.OPENROUTER_API_KEY:
        raise LyriaError("OPENROUTER_API_KEY is not configured")

    payload = {
        "model": settings.OPENROUTER_MUSIC_MODEL,
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(180.0)) as client:
            response = await client.post(
                f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions",
                json=payload,
                headers=_headers(),
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise LyriaError(
            f"Lyria returned {exc.response.status_code}: {exc.response.text[:500]}"
        ) from exc
    except httpx.HTTPError as exc:
        raise LyriaError(f"Lyria request failed: {exc}") from exc

    raw = response.json()
    audio_url, audio_data_url = _extract_audio(raw)
    return {
        "audio_url": audio_url,
        "audio_data_url": audio_data_url,
        "raw": raw,
    }


def _extract_audio(raw: dict) -> tuple[str | None, str | None]:
    """Walk the response looking for a music URL or base64 audio payload.

    OpenRouter's response shape for Lyria isn't formally documented, so we
    try the patterns that appear in OpenAI-compatible audio/multimodal
    responses. First non-empty match wins.
    """
    choices = raw.get("choices") or []
    if not choices:
        return None, None
    message = choices[0].get("message") or {}

    # Pattern 1: message.audio.{url,data,base64}  (OpenAI gpt-audio family)
    audio = message.get("audio") or {}
    if isinstance(audio, dict):
        if isinstance(audio.get("url"), str):
            return audio["url"], None
        for key in ("data", "base64"):
            if isinstance(audio.get(key), str) and audio[key]:
                fmt = audio.get("format") or audio.get("mime_type") or "audio/mpeg"
                return None, f"data:{fmt};base64,{audio[key]}"

    # Pattern 2: message.content as a list of typed parts
    content = message.get("content")
    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                continue
            ptype = part.get("type", "")
            if ptype in ("audio_url", "output_audio_url"):
                url_obj = part.get("audio_url") or part.get("url")
                if isinstance(url_obj, dict) and isinstance(url_obj.get("url"), str):
                    return url_obj["url"], None
                if isinstance(url_obj, str):
                    return url_obj, None
            if ptype in ("output_audio", "audio"):
                data = (part.get("audio") or {}).get("data") or part.get("data")
                fmt = (part.get("audio") or {}).get("format") or part.get("format") or "audio/mpeg"
                if isinstance(data, str) and data:
                    return None, f"data:{fmt};base64,{data}"

    # Pattern 3: top-level data array (DALL·E-style)
    for item in raw.get("data") or []:
        if isinstance(item, dict):
            if isinstance(item.get("url"), str):
                return item["url"], None
            if isinstance(item.get("b64_json"), str):
                return None, f"data:audio/mpeg;base64,{item['b64_json']}"

    return None, None
