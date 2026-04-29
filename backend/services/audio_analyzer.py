"""Audio-input style analyzer.

Sends an uploaded audio clip to a multimodal LLM (default: google/gemini-2.5-flash)
via OpenRouter chat completions and returns a structured style read that the
venue matcher can use as a signal alongside the user's typed style.
"""

from __future__ import annotations

import base64
import json
import re

import httpx

from backend.config import settings


class AudioAnalyzerError(RuntimeError):
    """Raised when audio analysis fails."""


SYSTEM_PROMPT = """\
You are NOCTURNE's Vibe Intelligence engine. You receive a short audio clip \
of a DJ's track or production and must describe its sonic identity for the \
venue-matching engine.

Listen to the clip and respond ONLY with a JSON object (no markdown, no \
commentary) in this exact format:

{
  "summary": "One short sentence on the sonic identity of the track.",
  "genres": ["primary genre", "sub-genre"],
  "bpm_estimate": "approx 128 BPM",
  "energy": "low | medium | high | peak-time",
  "mood": "two or three adjectives",
  "production_notes": "One sentence on textures, instruments, or sonic signatures.",
  "venue_signals": ["warehouse", "intimate", "festival main-stage", "rooftop", ...]
}

The venue_signals array should contain 2-5 venue archetypes the track would \
fit best. Be honest and specific. If the audio is unclear or silent, say so \
in the summary and return empty arrays.
"""


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _parse_data_url(data_url: str) -> tuple[str, str]:
    """Pull base64 payload + audio format from a data URL."""
    m = re.match(r"^data:audio/([a-zA-Z0-9.+-]+);base64,(.*)$", data_url, re.DOTALL)
    if not m:
        raise AudioAnalyzerError("Audio data URL is not in 'data:audio/<fmt>;base64,...' form.")
    fmt = m.group(1).lower()
    if fmt == "x-wav":
        fmt = "wav"
    if fmt == "mpeg":
        fmt = "mp3"
    return fmt, m.group(2)


async def analyze(audio_data_url: str) -> dict:
    """Analyze an audio clip and return a structured style read.

    Returns a dict matching SYSTEM_PROMPT's schema, plus a `style_phrase`
    field that condenses the analysis into one line for downstream prompts.
    """
    if not settings.OPENROUTER_API_KEY:
        raise AudioAnalyzerError("OPENROUTER_API_KEY is not configured")

    audio_format, audio_b64 = _parse_data_url(audio_data_url)

    payload = {
        "model": settings.OPENROUTER_AUDIO_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Listen to this clip and return the structured style read.",
                    },
                    {
                        "type": "input_audio",
                        "input_audio": {"data": audio_b64, "format": audio_format},
                    },
                ],
            },
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            response = await client.post(
                f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise AudioAnalyzerError(
            f"Audio model returned {exc.response.status_code}: {exc.response.text[:500]}"
        ) from exc
    except httpx.HTTPError as exc:
        raise AudioAnalyzerError(f"Audio model request failed: {exc}") from exc

    raw = response.json()
    try:
        content = raw["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AudioAnalyzerError(f"Unexpected response shape from audio model: {raw}") from exc

    if isinstance(content, list):
        # Some providers return list-of-parts; extract text parts
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))

    cleaned = _strip_fences(content or "")
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AudioAnalyzerError(f"Audio model returned non-JSON content: {cleaned[:300]}") from exc

    data["style_phrase"] = _condense_style(data)
    return data


def _condense_style(analysis: dict) -> str:
    """Build a short natural-language style phrase the venue matcher can ingest."""
    parts: list[str] = []
    summary = analysis.get("summary")
    if isinstance(summary, str) and summary:
        parts.append(summary.rstrip("."))
    genres = analysis.get("genres") or []
    if isinstance(genres, list) and genres:
        parts.append("genres: " + ", ".join(str(g) for g in genres))
    bpm = analysis.get("bpm_estimate")
    if isinstance(bpm, str) and bpm:
        parts.append(bpm)
    energy = analysis.get("energy")
    if isinstance(energy, str) and energy:
        parts.append(f"{energy} energy")
    mood = analysis.get("mood")
    if isinstance(mood, str) and mood:
        parts.append(f"mood: {mood}")
    return ". ".join(parts)
