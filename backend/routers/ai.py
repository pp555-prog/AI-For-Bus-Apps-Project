from fastapi import APIRouter, HTTPException

from backend.database import get_db
from backend.models import (
    BioGenerateRequest,
    DemoAssetResponse,
    DemoMusicPreviewRequest,
    DemoMusicPreviewResponse,
    DemoPerformanceVideoRequest,
    DemoPerformanceVideoResponse,
    DemoVenueMatch,
    DemoVenueMatchRequest,
    DemoVenueMatchResponse,
    DJ,
    DJVoiceIntroRequest,
    DJListItem,
    MusicPreviewRequest,
    PartySimulationRequest,
    PartySimulationVideoRequest,
    PromoPromptRequest,
    Venue,
    VibeMatchRequest,
    VibeMatchResponse,
    VibeMatchResult,
)
from backend.services import (
    audio_analyzer,
    llm_client,
    lyria_client,
    openrouter_video_client,
    vibe_matcher,
    higgsfield,
)

router = APIRouter()
DEMO_ASSET_NOTE = "Demo asset; v2 will generate on demand."


async def _ensure_dj_exists(db, dj_id: str) -> None:
    rows = await db.execute_fetchall("SELECT id FROM djs WHERE id = ?", [dj_id])
    if not rows:
        raise HTTPException(status_code=404, detail=f"DJ '{dj_id}' not found")


async def _ensure_venue_exists(db, venue_id: str) -> None:
    rows = await db.execute_fetchall("SELECT id FROM venues WHERE id = ?", [venue_id])
    if not rows:
        raise HTTPException(status_code=404, detail=f"Venue '{venue_id}' not found")


def _build_seedance_prompt(
    *,
    performer_name: str,
    venue: Venue,
    style_text: str,
    has_venue_ref: bool,
    performer_ref_count: int,
) -> str:
    """Construct a Seedance 2.0 video prompt following the official handbook.

    Structured per the Single-Shot Skeleton (Seedance 2.0 AI Handbook p.7):
    Subject / Environment / Main action / Camera / Lighting / Style / Audio,
    plus an explicit Asset-Roles block (handbook p.5: "References need roles
    — define HOW external information is used, not just state it") and a
    Constraints block (handbook p.16 vocabulary: avoid / preserve / maintain).

    Avoids the handbook's named anti-patterns (p.14): adjective soup, too many
    camera moves, unassigned reference stacks, controlling everything equally.
    Uses concrete vocabulary (p.16) for camera ("dolly in", "shallow focus",
    "medium close-up") and lighting ("rim light", "key light", "haze").
    """
    refs_lines: list[str] = []
    if has_venue_ref:
        refs_lines.append(
            "R1 = Environment Sheet (the matched venue): use only for "
            "architecture, materials, scale, color palette, and lighting language."
        )
    if performer_ref_count > 0:
        slot = 2 if has_venue_ref else 1
        plural = "+" if performer_ref_count > 1 else ""
        refs_lines.append(
            f"R{slot}{plural} = Identity Sheet ({performer_name}): use only for "
            "face, build, hair, and clothing. Do not redesign the performer."
        )
    asset_roles = " ".join(refs_lines) or "References: identity only."

    venue_vibe_phrase = ", ".join(venue.vibe_tags) or "club"
    venue_location = venue.city or "the city"
    env_anchor = "matching R1 exactly" if has_venue_ref else f"a {venue_vibe_phrase} club interior"

    return (
        # Format/Goal
        "Format: one continuous 10-second photoreal music-performance shot, "
        "single take, no edits, no graphic overlays. "
        # Asset Roles (handbook principle 5)
        f"Asset roles: {asset_roles} "
        # Subject
        f"Subject: {performer_name}, identity locked to the Identity Sheet references. "
        # Environment (handbook principle 4: environment is active, not wallpaper)
        f"Environment: interior of {venue.name} in {venue_location}, "
        f"{env_anchor}; small audience visible in the foreground as silhouettes. "
        # Main action (handbook principle 1: one dominant readable action; principle 3: physical)
        f"Main action: {performer_name} stands behind the DJ booth, both hands working the mixer, "
        "head nodding to the beat. "
        # Camera (handbook principle 2: camera serves story; one move only)
        "Camera: slow dolly-in from the back of the room toward the booth, "
        f"ending in a medium close-up of {performer_name}; shallow focus on the performer throughout. "
        # Lighting (concrete vocabulary from p.16)
        + (
            f"Lighting: match the lighting language of R1 ({venue_vibe_phrase}); "
            if has_venue_ref
            else f"Lighting: {venue_vibe_phrase} club aesthetic; "
        ) +
        "soft haze in the air, rim light behind the performer, single key light from above the booth. "
        # Sound
        "Sound: silent. "
        # Style
        f"Style: photoreal documentary; the musical style being performed is {style_text}. "
        # Constraints (handbook p.16 vocabulary)
        f"Preserve {performer_name}'s exact face, hair, and clothing from the Identity Sheet. "
        "Avoid: text overlays, logos, watermarks, brand names, captions, on-screen graphics, "
        "celebrity likenesses."
    )


def _venue_match_score(style: str, venue: Venue) -> tuple[int, str]:
    style_terms = {term.strip().lower() for term in style.replace("/", " ").replace(",", " ").split() if term.strip()}
    venue_terms = {term.lower() for term in venue.vibe_tags}
    venue_terms.update((venue.description or "").lower().replace("-", " ").split())
    overlap = sorted(style_terms & venue_terms)

    score = 58 + min(len(overlap) * 12, 30)
    if any(term in style_terms for term in {"warehouse", "industrial", "techno", "underground"}):
        if any(tag in venue_terms for tag in {"warehouse", "industrial", "underground", "concrete"}):
            score += 10
    if any(term in style_terms for term in {"ibiza", "festival", "cinematic", "melodic"}):
        if any(tag in venue_terms for tag in {"ibiza", "festival", "cinematic", "massive", "immersive"}):
            score += 10
    if any(term in style_terms for term in {"intimate", "house", "jazz", "warm"}):
        if any(tag in venue_terms for tag in {"intimate", "velvet", "warmly"}):
            score += 10

    score = max(45, min(score, 98))
    if overlap:
        reason = f"Strong overlap on {', '.join(overlap[:4])}."
    else:
        reason = "Best fit based on venue atmosphere, capacity, and style language."
    return score, reason


# ── Vibe Match ───────────────────────────────────────────────────────────────

@router.post("/vibe-match", response_model=VibeMatchResponse)
async def vibe_match(request: VibeMatchRequest):
    """LLM-powered DJ matching from a natural-language vibe description."""
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
    """Generate a compelling DJ bio using the configured LLM."""
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

    bio = llm_client.complete(system, user_msg)
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

    raw = llm_client.complete(system, user_msg)
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


# ── v2 Demo Asset Stubs ─────────────────────────────────────────────────────

@router.post("/demo-venue-match", response_model=DemoVenueMatchResponse)
async def demo_venue_match(request: DemoVenueMatchRequest):
    """Match the demo performer to seeded venues for the personalized class demo.

    If an audio clip is supplied, an audio-input LLM listens to it and produces
    a structured style read. That read is augmented onto the user's typed style
    and passed to the LLM venue matcher. If audio analysis fails or no audio
    is supplied, the LLM matcher still runs on the typed style alone. The
    deterministic keyword scorer is the last-resort fallback.
    """
    db = await get_db()
    try:
        rows = await db.execute_fetchall("SELECT * FROM venues")
        venues = [Venue(**dict(row)) for row in rows]
    finally:
        await db.close()

    venues_by_id = {venue.id: venue for venue in venues}

    audio_analysis: dict | None = None
    style_segments = [request.style] if request.style else []
    if request.audio_data_url:
        try:
            audio_analysis = await audio_analyzer.analyze(request.audio_data_url)
            phrase = audio_analysis.get("style_phrase")
            if isinstance(phrase, str) and phrase:
                style_segments.append(f"AI heard in the uploaded track: {phrase}")
        except audio_analyzer.AudioAnalyzerError as exc:
            audio_analysis = {"error": str(exc)}

    combined_style = "\n".join(s for s in style_segments if s).strip()

    matcher_used = "llm"
    interpretation: str | None = None
    ranked: list[DemoVenueMatch] = []

    if combined_style:
        try:
            matches, interpretation = vibe_matcher.match_venues(combined_style, venues)
        except Exception:  # noqa: BLE001 - any LLM failure -> deterministic fallback
            matches = []
        for entry in matches:
            venue = venues_by_id.get(entry.get("venue_id"))
            if not venue:
                continue
            ranked.append(
                DemoVenueMatch(
                    venue=venue,
                    score=int(entry.get("score") or 0),
                    reasoning=str(entry.get("reasoning") or "").strip()
                        or "LLM match without explicit reasoning.",
                )
            )

    if not ranked:
        matcher_used = "deterministic"
        for venue in venues:
            score, reasoning = _venue_match_score(combined_style or request.style, venue)
            ranked.append(DemoVenueMatch(venue=venue, score=score, reasoning=reasoning))
        ranked.sort(key=lambda item: item.score, reverse=True)
        ranked = ranked[:3]

    return DemoVenueMatchResponse(
        results=ranked,
        interpretation=interpretation,
        audio_analysis=audio_analysis,
        combined_style=combined_style or None,
        matcher=matcher_used,
    )


@router.post("/demo-performance-video", response_model=DemoPerformanceVideoResponse)
async def demo_performance_video(request: DemoPerformanceVideoRequest):
    """Submit an OpenRouter reference-video job of the uploaded performer at a venue."""
    db = await get_db()
    try:
        venue_rows = await db.execute_fetchall("SELECT * FROM venues WHERE id = ?", [request.venue_id])
        if not venue_rows:
            raise HTTPException(status_code=404, detail=f"Venue '{request.venue_id}' not found")
        venue = Venue(**dict(venue_rows[0]))
    finally:
        await db.close()

    if not openrouter_video_client.is_configured():
        return DemoPerformanceVideoResponse(
            video_url="/assets/v2/party-simulation.mp4",
            provider="openrouter/video",
            status="fallback",
            generated=False,
            note="Demo asset; set OPENROUTER_API_KEY to generate a personalized OpenRouter video.",
        )
    if not request.image_data_urls:
        raise HTTPException(status_code=400, detail="Upload at least one performer image")

    # Build input_references: venue scene first (so the model anchors on the
    # room), then performer photos (for identity). Cap performer photos at 3
    # so the venue image survives Seedance's 4-reference limit.
    venue_image_url = (venue.image_url or "").strip()
    performer_refs = request.image_data_urls[:3]
    input_references: list[str] = []
    if venue_image_url:
        input_references.append(venue_image_url)
    input_references.extend(performer_refs)

    prompt = _build_seedance_prompt(
        performer_name=request.performer_name,
        venue=venue,
        style_text=request.style,
        has_venue_ref=bool(venue_image_url),
        performer_ref_count=len(performer_refs),
    )

    try:
        result = await openrouter_video_client.submit_video(
            prompt,
            input_references,
        )
    except openrouter_video_client.OpenRouterVideoError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return DemoPerformanceVideoResponse(
        job_id=result.get("id"),
        status=result.get("status", "pending"),
        polling_url=result.get("polling_url"),
        provider="openrouter/video",
        generated=False,
        note="OpenRouter video job submitted. Poll this job until status is completed.",
    )


@router.get("/demo-performance-video/{job_id}", response_model=DemoPerformanceVideoResponse)
async def get_demo_performance_video(job_id: str):
    """Poll an OpenRouter video job for the personalized demo."""
    try:
        result = await openrouter_video_client.get_video_job(job_id)
    except openrouter_video_client.OpenRouterVideoError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    unsigned_urls = result.get("unsigned_urls") or []
    video_url = unsigned_urls[0] if unsigned_urls else None
    return DemoPerformanceVideoResponse(
        job_id=result.get("id", job_id),
        status=result.get("status", "unknown"),
        polling_url=result.get("polling_url"),
        video_url=video_url,
        provider="openrouter/video",
        generated=result.get("status") == "completed" and bool(video_url),
        note="OpenRouter video job status.",
    )


@router.post("/demo-music-preview", response_model=DemoMusicPreviewResponse)
async def demo_music_preview(request: DemoMusicPreviewRequest):
    """Generate a Lyria 3 music clip tailored to the matched venue + performer style."""
    db = await get_db()
    try:
        venue_rows = await db.execute_fetchall("SELECT * FROM venues WHERE id = ?", [request.venue_id])
        if not venue_rows:
            raise HTTPException(status_code=404, detail=f"Venue '{request.venue_id}' not found")
        venue = Venue(**dict(venue_rows[0]))
    finally:
        await db.close()

    prompt = (
        f"Compose a 30-second instrumental music clip for a DJ named {request.performer_name} "
        f"performing at {venue.name} in {venue.city or 'the city'}. "
        f"Performer style: {request.style}. "
        f"Venue atmosphere: {', '.join(venue.vibe_tags) or 'club, electronic'}. "
        f"Produce a peak-time loop with driving rhythm, atmospheric pads, and a clear groove "
        f"that would fit a club soundsystem. No vocals. No spoken word. Instrumental only."
    )

    if not lyria_client.is_configured():
        return DemoMusicPreviewResponse(
            audio_url="/assets/v2/music-preview.mp3",
            prompt=prompt,
            provider="lyria-3-clip-preview",
            generated=False,
            note="Demo asset; set OPENROUTER_API_KEY to generate a personalized Lyria clip.",
        )

    try:
        result = await lyria_client.generate_clip(prompt)
    except lyria_client.LyriaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    audio_url = result.get("audio_url")
    audio_data_url = result.get("audio_data_url")
    if not audio_url and not audio_data_url:
        raise HTTPException(
            status_code=502,
            detail=(
                "Lyria response did not contain a recognizable audio payload. "
                "Raw shape keys: " + ", ".join(sorted((result.get("raw") or {}).keys()))
            ),
        )

    return DemoMusicPreviewResponse(
        audio_url=audio_url,
        audio_data_url=audio_data_url,
        prompt=prompt,
        provider="lyria-3-clip-preview",
        generated=True,
        note="Lyria 3 clip generated for the matched venue.",
    )


@router.post("/music-preview", response_model=DemoAssetResponse)
async def music_preview(request: MusicPreviewRequest):
    """Return a canned Suno-style music preview asset for the class demo."""
    db = await get_db()
    try:
        await _ensure_dj_exists(db, request.dj_id)
        await _ensure_venue_exists(db, request.venue_id)
    finally:
        await db.close()

    return DemoAssetResponse(
        audio_url="/assets/v2/music-preview.mp3",
        provider="suno",
        generated=False,
        note=DEMO_ASSET_NOTE,
    )


@router.post("/party-simulation-video", response_model=DemoAssetResponse)
async def party_simulation_video(request: PartySimulationVideoRequest):
    """Return the canned party simulation video asset for the class demo."""
    db = await get_db()
    try:
        await _ensure_dj_exists(db, request.dj_id)
        await _ensure_venue_exists(db, request.venue_id)
    finally:
        await db.close()

    return DemoAssetResponse(
        video_url="/assets/v2/party-simulation.mp4",
        provider="openrouter/video",
        generated=False,
        note=DEMO_ASSET_NOTE,
    )


@router.post("/dj-voice-intro", response_model=DemoAssetResponse)
async def dj_voice_intro(request: DJVoiceIntroRequest):
    """Return a canned ElevenLabs-style DJ voice intro asset for the class demo."""
    db = await get_db()
    try:
        await _ensure_dj_exists(db, request.dj_id)
    finally:
        await db.close()

    return DemoAssetResponse(
        audio_url="/assets/v2/dj-voice-intro.mp3",
        provider="elevenlabs",
        generated=False,
        note=DEMO_ASSET_NOTE,
    )
