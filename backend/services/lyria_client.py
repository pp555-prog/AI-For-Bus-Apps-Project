"""Lyria 3 music generation client.

Routes through OpenRouter's chat-completions endpoint with audio output.
The active music model is set via OPENROUTER_MUSIC_MODEL (default:
google/lyria-3-clip-preview, ~30s clip). To return audio, OpenRouter requires
both `modalities: ["text", "audio"]` and `stream: true`. The audio arrives
inside the stream as one or more `delta.audio.data` base64 chunks; we
concatenate them and detect the actual format from the magic bytes (Lyria
typically returns MP3 even when WAV is requested).
"""

from __future__ import annotations

import base64
import json

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
        "Accept": "text/event-stream",
    }


def _detect_audio_mime(raw: bytes) -> str:
    """Return a best-guess audio MIME type from magic bytes."""
    if raw[:3] == b"ID3" or (len(raw) > 1 and raw[0] == 0xFF and (raw[1] & 0xE0) == 0xE0):
        return "audio/mpeg"  # MP3
    if raw[:4] == b"RIFF" and raw[8:12] == b"WAVE":
        return "audio/wav"
    if raw[:4] == b"OggS":
        return "audio/ogg"
    if raw[:4] == b"fLaC":
        return "audio/flac"
    return "audio/mpeg"  # Lyria default in observed responses


async def generate_clip(prompt: str) -> dict:
    """Generate a music clip from a text prompt.

    Returns dict with `audio_data_url` (data URL with the detected MIME type)
    plus `caption_text` (Lyria's <instrumental>Caption: text describing the
    clip) and `raw_first_chunk` for debugging.
    """
    if not settings.OPENROUTER_API_KEY:
        raise LyriaError("OPENROUTER_API_KEY is not configured")

    payload = {
        "model": settings.OPENROUTER_MUSIC_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "modalities": ["text", "audio"],
        "audio": {"format": "wav"},
        "stream": True,
    }

    text_parts: list[str] = []
    audio_b64_parts: list[str] = []
    first_chunk_obj: dict | None = None
    chunk_count = 0

    def _ingest(obj: dict) -> None:
        nonlocal first_chunk_obj, chunk_count
        chunk_count += 1
        if first_chunk_obj is None:
            first_chunk_obj = obj
        delta = (obj.get("choices") or [{}])[0].get("delta") or {}
        content = delta.get("content")
        if isinstance(content, str):
            text_parts.append(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    if isinstance(part.get("text"), str):
                        text_parts.append(part["text"])
                    if part.get("type") in ("audio", "output_audio"):
                        ad = (part.get("audio") or {}).get("data") or part.get("data")
                        if isinstance(ad, str) and ad:
                            audio_b64_parts.append(ad)
        audio = delta.get("audio")
        if isinstance(audio, dict):
            for k in ("data", "base64"):
                v = audio.get(k)
                if isinstance(v, str) and v:
                    audio_b64_parts.append(v)
                    break

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            async with client.stream(
                "POST",
                f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions",
                json=payload,
                headers=_headers(),
            ) as response:
                if response.status_code >= 400:
                    err_body = await response.aread()
                    raise LyriaError(
                        f"Lyria returned {response.status_code}: {err_body.decode('utf-8', 'replace')[:500]}"
                    )

                # Manual SSE parsing on the raw byte stream. We avoid
                # `aiter_lines()` because Lyria emits a single SSE event whose
                # `data:` line contains ~1 MB of base64-encoded audio, and some
                # httpx line iterators chunk that awkwardly.
                buf = b""
                async for raw in response.aiter_bytes():
                    buf += raw
                    while b"\n\n" in buf:
                        event_bytes, buf = buf.split(b"\n\n", 1)
                        for line in event_bytes.decode("utf-8", "replace").splitlines():
                            if not line.startswith("data:"):
                                continue
                            data_str = line[5:].strip()
                            if not data_str or data_str == "[DONE]":
                                continue
                            try:
                                _ingest(json.loads(data_str))
                            except json.JSONDecodeError:
                                continue
    except httpx.HTTPError as exc:
        raise LyriaError(f"Lyria stream failed: {exc}") from exc

    if not audio_b64_parts:
        raise LyriaError(
            f"Lyria stream produced no audio (chunks={chunk_count}). "
            f"First chunk shape: {json.dumps(first_chunk_obj)[:300] if first_chunk_obj else 'none'}"
        )

    full_b64 = "".join(audio_b64_parts)
    raw_bytes = base64.b64decode(full_b64)
    mime = _detect_audio_mime(raw_bytes)
    audio_data_url = f"data:{mime};base64,{full_b64}"

    return {
        "audio_url": None,
        "audio_data_url": audio_data_url,
        "caption_text": "".join(text_parts).strip() or None,
        "mime_type": mime,
        "byte_size": len(raw_bytes),
        "chunk_count": chunk_count,
    }
