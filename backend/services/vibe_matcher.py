"""Orchestrates Claude-powered vibe matching between user queries and DJ profiles."""

import json
import re

from backend.models import DJListItem, VibeMatchResult
from backend.services.claude_client import complete


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
    """Remove markdown code fences if Claude wraps the JSON."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def match_djs(query: str, dj_profiles: list[DJListItem]) -> tuple[list[dict], str | None]:
    """
    Call Claude to rank DJs against a vibe query.

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
