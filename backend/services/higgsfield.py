"""Higgsfield video generation integration.

For the MVP, this module uses Claude to generate creative prompts that
would be sent to the Higgsfield API. Actual Higgsfield API calls can be
added once the API key and SDK are available.
"""

from backend.services.claude_client import complete


SYSTEM_PROMPT = """\
You are a cinematic video director specializing in electronic music event \
visuals. Given a DJ profile and a venue profile, generate a detailed \
Higgsfield AI video prompt that would produce a stunning 15-second party \
simulation clip.

Your prompt should describe:
- Camera movement and framing
- Lighting and atmospheric effects (haze, lasers, strobes)
- Crowd energy and density
- The DJ's performance style and equipment
- Color palette matching the DJ's genre and venue's aesthetic
- Any signature visual moments

Respond ONLY with a JSON object:
{
  "video_prompt": "The full Higgsfield prompt (2-4 sentences).",
  "style_tags": ["cinematic", "moody", "high-energy"],
  "suggested_duration": 15
}
"""


def generate_party_simulation_prompt(
    dj_name: str,
    dj_tagline: str,
    dj_genres: list[str],
    venue_name: str,
    venue_vibe_tags: list[str],
    venue_capacity: int | None = None,
) -> dict:
    """Use Claude to create a Higgsfield-ready video generation prompt."""
    user_message = (
        f"DJ: {dj_name} ({dj_tagline})\n"
        f"Genres: {', '.join(dj_genres)}\n"
        f"Venue: {venue_name}\n"
        f"Venue vibe: {', '.join(venue_vibe_tags)}\n"
        f"Venue capacity: {venue_capacity or 'unknown'}\n\n"
        f"Generate a Higgsfield video prompt for a party simulation."
    )

    import json
    import re

    raw = complete(SYSTEM_PROMPT, user_message)
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return {
            "video_prompt": f"Cinematic party simulation: {dj_name} performing at {venue_name}.",
            "style_tags": ["cinematic", "electronic", "nightlife"],
            "suggested_duration": 15,
        }
