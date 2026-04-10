from fastapi import APIRouter, HTTPException

from backend.database import get_db
from backend.models import (
    BioGenerateRequest,
    DJ,
    DJListItem,
    PartySimulationRequest,
    PromoPromptRequest,
    Venue,
    VibeMatchRequest,
    VibeMatchResponse,
    VibeMatchResult,
)
from backend.services import claude_client, vibe_matcher, higgsfield

router = APIRouter()


# ── Vibe Match ───────────────────────────────────────────────────────────────

@router.post("/vibe-match", response_model=VibeMatchResponse)
async def vibe_match(request: VibeMatchRequest):
    """Claude-powered DJ matching from a natural-language vibe description."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall("SELECT * FROM djs")
        all_djs = {dj.id: dj for dj in (DJListItem(**dict(r)) for r in rows)}
    finally:
        await db.close()

    matches_raw, interpretation = vibe_matcher.match_djs(
        request.query, list(all_djs.values())
    )

    results = []
    for m in matches_raw:
        dj = all_djs.get(m.get("dj_id"))
        if dj:
            results.append(
                VibeMatchResult(
                    dj=dj,
                    score=m.get("score", 50),
                    reasoning=m.get("reasoning", ""),
                )
            )

    return VibeMatchResponse(results=results, query_interpretation=interpretation)


# ── Bio Generation ───────────────────────────────────────────────────────────

@router.post("/generate-bio")
async def generate_bio(request: BioGenerateRequest):
    """Generate a compelling DJ bio using Claude."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall("SELECT * FROM djs WHERE id = ?", [request.dj_id])
        if not rows:
            raise HTTPException(status_code=404, detail=f"DJ '{request.dj_id}' not found")
        dj = DJ(**dict(rows[0]))
    finally:
        await db.close()

    system = (
        "You are a luxury editorial copywriter for NOCTURNE, a premium DJ-venue "
        "marketplace. Write compelling, atmospheric DJ bios in 2 paragraphs. "
        "Use a refined, editorial tone — think high-end music magazine."
    )
    user_msg = (
        f"Write a bio for {dj.name}.\n"
        f"Genres: {', '.join(dj.genres)}\n"
        f"Style: {dj.tagline}\n"
        f"Setup: {dj.setup}\n"
        f"Vibe keywords: {', '.join(dj.vibe_keywords)}"
    )

    bio = claude_client.complete(system, user_msg)
    return {"dj_id": dj.id, "bio": bio}


# ── Promo Prompt Generation ─────────────────────────────────────────────────

@router.post("/promo-prompt")
async def promo_prompt(request: PromoPromptRequest):
    """Generate Suno music + ElevenLabs voice prompts for a DJ-venue pairing."""
    db = await get_db()
    try:
        dj_rows = await db.execute_fetchall("SELECT * FROM djs WHERE id = ?", [request.dj_id])
        venue_rows = await db.execute_fetchall("SELECT * FROM venues WHERE id = ?", [request.venue_id])
        if not dj_rows:
            raise HTTPException(status_code=404, detail="DJ not found")
        if not venue_rows:
            raise HTTPException(status_code=404, detail="Venue not found")
        dj = DJ(**dict(dj_rows[0]))
        venue = Venue(**dict(venue_rows[0]))
    finally:
        await db.close()

    system = (
        "You are a creative director for NOCTURNE. Generate two things:\n"
        "1. A Suno AI music generation prompt for a 30-second clip matching "
        "this DJ's style at this venue.\n"
        "2. An ElevenLabs voice-over script for a 15-second promo announcement.\n\n"
        "Respond ONLY with JSON:\n"
        '{"suno_prompt": "...", "elevenlabs_script": "..."}'
    )
    user_msg = (
        f"DJ: {dj.name} ({dj.tagline}), genres: {', '.join(dj.genres)}\n"
        f"Venue: {venue.name} ({venue.city}), vibe: {', '.join(venue.vibe_tags)}, "
        f"capacity: {venue.capacity}"
    )

    import json
    import re

    raw = claude_client.complete(system, user_msg)
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return {
            "suno_prompt": f"Electronic music in the style of {dj.name} for {venue.name}.",
            "elevenlabs_script": f"NOCTURNE presents {dj.name} at {venue.name}.",
        }


# ── Party Simulation (Higgsfield) ────────────────────────────────────────────

@router.post("/party-simulation")
async def party_simulation(request: PartySimulationRequest):
    """Generate a Higgsfield video prompt for a DJ-venue party simulation."""
    db = await get_db()
    try:
        dj_rows = await db.execute_fetchall("SELECT * FROM djs WHERE id = ?", [request.dj_id])
        venue_rows = await db.execute_fetchall("SELECT * FROM venues WHERE id = ?", [request.venue_id])
        if not dj_rows:
            raise HTTPException(status_code=404, detail="DJ not found")
        if not venue_rows:
            raise HTTPException(status_code=404, detail="Venue not found")
        dj = DJ(**dict(dj_rows[0]))
        venue = Venue(**dict(venue_rows[0]))
    finally:
        await db.close()

    result = higgsfield.generate_party_simulation_prompt(
        dj_name=dj.name,
        dj_tagline=dj.tagline or "",
        dj_genres=dj.genres,
        venue_name=venue.name,
        venue_vibe_tags=venue.vibe_tags,
        venue_capacity=venue.capacity,
    )

    return {"dj_id": dj.id, "venue_id": venue.id, **result}
