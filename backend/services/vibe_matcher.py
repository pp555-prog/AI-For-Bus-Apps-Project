"""Orchestrates LLM-powered vibe matching between user queries and DJ profiles,
and between performer style descriptions and venue profiles (used by the
personalized demo flow)."""

import json
import re

from backend.models import DJListItem, Venue, VibeMatchResult
from backend.services.llm_client import complete


SYSTEM_PROMPT = """\
You are NOCTURNE's Vibe Intelligence engine — an expert at matching DJs to \
musical atmospheres. You understand genres, sub-genres, BPM ranges, energy \
levels, and the nuanced relationship between a DJ's sound and a venue's \
desired atmosphere.

You will receive:
1. A JSON array of available DJ profiles.
2. A natural-language description of the desired atmosphere from a venue \
   manager or event curator.

Your job: rank the TOP 5 DJs that best match the described atmosphere.

Use all profile signals: tagline, genres, vibe keywords, setup, fee tier, and
especially the DJ bio. The bio is the best evidence for how the DJ actually
sounds in context. If tags and bio point in different directions, weigh the bio
language heavily and explain the tradeoff. Do not rank a DJ highly from a single
matching genre tag if the bio suggests a different energy, venue fit, or scale.

Respond ONLY with a valid JSON object (no markdown fences, no commentary) \
in this exact format:
{
  "query_interpretation": "One sentence summarizing what the user is looking for.",
  "matches": [
    {
      "dj_id": "the-dj-slug",
      "score": 92,
      "reasoning": "One sentence explaining why this DJ is a great match."
    }
  ]
}

Order matches by score descending. Scores should range from 0 to 100.
Return at most 5 matches. Only include DJs with a score above 40.
"""


def _strip_fences(text: str) -> str:
    """Remove markdown code fences if the LLM wraps the JSON."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def match_djs(query: str, dj_profiles: list[DJListItem]) -> tuple[list[dict], str | None]:
    """
    Call the LLM to rank DJs against a vibe query.

    Returns (matches_list, query_interpretation) where matches_list items are
    dicts with keys: dj_id, score, reasoning.
    """
    # Build DJ catalog for the prompt
    catalog = []
    for dj in dj_profiles:
        catalog.append({
            "id": dj.id,
            "name": dj.name,
            "tagline": dj.tagline,
            "genres": dj.genres,
            "vibe_keywords": dj.vibe_keywords,
            "bio": dj.bio,
            "setup": dj.setup,
            "fee_tier": dj.fee_tier,
        })

    user_message = (
        f"Available DJs:\n{json.dumps(catalog, indent=2)}\n\n"
        f"Desired atmosphere:\n{query}"
    )

    raw = complete(SYSTEM_PROMPT, user_message)
    cleaned = _strip_fences(raw)

    try:
        data = json.loads(cleaned)
        matches = data.get("matches", [])
        interpretation = data.get("query_interpretation")
        return matches, interpretation
    except (json.JSONDecodeError, TypeError, KeyError):
        # Fallback: return all DJs with neutral score
        return [], None


# ── Venue matching (personalized demo) ──────────────────────────────────────

VENUE_SYSTEM_PROMPT = """\
You are NOCTURNE's Vibe Intelligence engine. You receive a description of a \
performer's musical style (sometimes augmented by an audio analysis of one of \
their tracks) and a JSON array of venue profiles.

Your job: rank the TOP 3 venues that fit the performer's sound best.

Use venue type, vibe tags, capacity, city context, and description language. \
Treat the audio analysis (if present) as the strongest signal because it \
reflects how the performer actually sounds, not how they label themselves. \
Genre tags can mislead; rely on the sonic identity description.

Respond ONLY with a valid JSON object (no markdown fences, no commentary) \
in this exact format:

{
  "interpretation": "One short sentence on the performer's sonic identity.",
  "matches": [
    {
      "venue_id": "venue-slug",
      "score": 92,
      "reasoning": "One sentence on why this venue fits."
    }
  ]
}

Order by score descending. Scores 0-100. Return at most 3 matches.
"""


def match_venues(style_description: str, venues: list[Venue]) -> tuple[list[dict], str | None]:
    """Rank venues against a performer's style description.

    Returns (matches_list, interpretation) where matches_list items are
    dicts with keys: venue_id, score, reasoning.
    """
    catalog = []
    for venue in venues:
        catalog.append({
            "id": venue.id,
            "name": venue.name,
            "city": venue.city,
            "capacity": venue.capacity,
            "vibe_tags": venue.vibe_tags,
            "description": venue.description,
        })

    user_message = (
        f"Available venues:\n{json.dumps(catalog, indent=2)}\n\n"
        f"Performer style:\n{style_description}"
    )

    raw = complete(VENUE_SYSTEM_PROMPT, user_message)
    cleaned = _strip_fences(raw)

    try:
        data = json.loads(cleaned)
        matches = data.get("matches", [])
        interpretation = data.get("interpretation")
        return matches, interpretation
    except (json.JSONDecodeError, TypeError, KeyError):
        return [], None
