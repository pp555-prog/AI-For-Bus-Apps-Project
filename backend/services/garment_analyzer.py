"""Garment / outfit visual analyzer.

Sends uploaded performer photos to a multimodal LLM (default:
google/gemini-2.5-flash via OpenRouter) and returns a structured wardrobe
read that the venue matcher and the Seedance prompt builder both consume.

Mirrors the design of `backend/services/audio_analyzer.py`: same
chat-completions transport, same JSON-only response, same `style_phrase`
condensation. The garment side runs in parallel with the audio side
during /api/ai/demo-venue-match so the user does not have to type their
outfit into the Style textarea.
"""

from __future__ import annotations

import json
import re

import httpx

from backend.config import settings


class GarmentAnalyzerError(RuntimeError):
    """Raised when garment / outfit analysis fails."""


SYSTEM_PROMPT = """\
You are NOCTURNE's Wardrobe Intelligence engine. You receive one or more \
photos of a DJ's outfit (typically flat lay, on a hanger, on a mannequin, \
or worn) and must describe the outfit for the venue-matching engine AND \
for the venue-simulation video generator.

Look at the photo(s) and respond ONLY with a JSON object (no markdown, no \
commentary) in this exact format:

{
  "summary": "One short sentence describing the outfit as a whole.",
  "garments": ["mint green linen button-down shirt", "..."],
  "color_palette": ["primary color", "accent color"],
  "material": "linen | denim | leather | cotton | technical | mixed",
  "style_register": "summery resort | smart casual | edgy streetwear | techno underground | minimalist | streetwear-luxury | other",
  "venue_signals": ["beach club", "rooftop terrace", "afterhours warehouse", "..."]
}

The `garments` array should list every visible item the way a stylist \
would describe it (color + material + cut/silhouette + brand if the brand \
is visibly readable). The `venue_signals` array should contain 2-5 venue \
archetypes the outfit suggests. Be honest and specific. If the photos are \
unclear or do not show clothing, say so in the summary and return empty \
arrays for the structured fields.
"""


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


async def analyze(image_data_urls: list[str]) -> dict:
    """Analyze one or more performer photos and return a structured wardrobe read.

    All photos go in a single multi-image chat call so the model sees the
    outfit holistically (top + bottom + shoes when supplied separately).
    Returns a dict matching SYSTEM_PROMPT plus a `style_phrase` field that
    condenses the analysis into one line for downstream prompts.
    """
    if not settings.OPENROUTER_API_KEY:
        raise GarmentAnalyzerError("OPENROUTER_API_KEY is not configured")
    if not image_data_urls:
        raise GarmentAnalyzerError("No photos to analyze")

    # Cap at 3 to mirror the Seedance reference cap and keep the call fast.
    photo_urls = [
        u for u in image_data_urls[:3]
        if isinstance(u, str) and u.startswith("data:image/")
    ]
    if not photo_urls:
        raise GarmentAnalyzerError("No image data URLs in supported format")

    user_content: list[dict] = [
        {
            "type": "text",
            "text": "Look at these photo(s) and return the structured wardrobe read.",
        }
    ]
    for url in photo_urls:
        user_content.append({"type": "image_url", "image_url": {"url": url}})

    payload = {
        "model": settings.OPENROUTER_VISION_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
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
        raise GarmentAnalyzerError(
            f"Vision model returned {exc.response.status_code}: {exc.response.text[:500]}"
        ) from exc
    except httpx.HTTPError as exc:
        raise GarmentAnalyzerError(f"Vision model request failed: {exc}") from exc

    raw = response.json()
    try:
        content = raw["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise GarmentAnalyzerError(
            f"Unexpected response shape from vision model: {raw}"
        ) from exc

    if isinstance(content, list):
        content = "".join(
            p.get("text", "") for p in content if isinstance(p, dict)
        )

    cleaned = _strip_fences(content or "")
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Gemini sometimes drops a comma between fields or truncates a long
        # response. First try a structural repair, then fall back to regex-
        # extracting whatever fields we can find. Only raise if neither path
        # surfaces anything usable -- a partial wardrobe read still renders
        # cleanly in the demo, "Photo analysis failed" does not.
        try:
            data = json.loads(_try_repair_json(cleaned))
        except json.JSONDecodeError:
            data = _extract_partial(cleaned)
            if not data:
                raise GarmentAnalyzerError(
                    f"Vision model returned non-JSON content: {cleaned[:300]}"
                )

    data["style_phrase"] = _condense_style(data)
    return data


def _try_repair_json(text: str) -> str:
    """Best-effort fix for the two malformations Gemini commonly produces:
    a missing comma between a string value and the next key, and a truncated
    tail (missing closing braces/brackets)."""
    # Insert missing comma between `"..."` (string value) and `"key":` on
    # the same or next line. Same for `]` or `}` followed by `"key":`.
    text = re.sub(r'("[^"]*")(\s+)("[^"]+"\s*:)', r'\1,\2\3', text)
    text = re.sub(r'(\])(\s+)("[^"]+"\s*:)', r'\1,\2\3', text)
    text = re.sub(r'(\})(\s+)("[^"]+"\s*:)', r'\1,\2\3', text)
    # Drop a truncated tail: anything from the last comma to end of string
    # that doesn't close cleanly (the most common Gemini failure mode is
    # ending mid-field, e.g. `... "linen", "` or `... "x":` with no value).
    text = re.sub(r',\s*"[^"]*"\s*:\s*"?[^"}\]]*$', '', text)
    text = re.sub(r',\s*"[^"]*"\s*:\s*\[?[^"}\]]*$', '', text)
    text = re.sub(r',\s*"[^"]*$', '', text)
    text = re.sub(r',\s*$', '', text)
    # Strip trailing commas before close (after the truncation cleanup so we
    # don't leave a `,}` behind)
    text = re.sub(r',\s*([}\]])', r'\1', text)
    # Close any unbalanced braces/brackets at the end
    text = text + ']' * max(0, text.count('[') - text.count(']'))
    text = text + '}' * max(0, text.count('{') - text.count('}'))
    return text


def _extract_partial(text: str) -> dict:
    """Last resort: regex-pull whatever fields are visibly present."""
    out: dict = {}
    m = re.search(r'"summary"\s*:\s*"([^"]*)"', text)
    if m:
        out["summary"] = m.group(1)
    for field in ("garments", "color_palette", "venue_signals"):
        m = re.search(rf'"{field}"\s*:\s*\[([^\]]*)\]', text, re.DOTALL)
        if m:
            items = re.findall(r'"([^"]+)"', m.group(1))
            if items:
                out[field] = items
    for field in ("material", "style_register"):
        m = re.search(rf'"{field}"\s*:\s*"([^"]*)"', text)
        if m:
            out[field] = m.group(1)
    return out


def _condense_style(analysis: dict) -> str:
    """Build a short natural-language wardrobe phrase for downstream prompts."""
    parts: list[str] = []
    summary = analysis.get("summary")
    if isinstance(summary, str) and summary:
        parts.append(summary.rstrip("."))
    garments = analysis.get("garments") or []
    if isinstance(garments, list) and garments:
        parts.append("wearing: " + ", ".join(str(g) for g in garments))
    palette = analysis.get("color_palette") or []
    if isinstance(palette, list) and palette:
        parts.append("palette: " + ", ".join(str(c) for c in palette))
    register = analysis.get("style_register")
    if isinstance(register, str) and register:
        parts.append(f"register: {register}")
    return ". ".join(parts)
