import asyncio
import base64
import shutil
import subprocess
import uuid
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException

from backend.config import settings
from backend.database import get_db
from backend.models import (
    BioGenerateRequest,
    DemoAssetResponse,
    DemoMuxVideoRequest,
    DemoMuxVideoResponse,
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
    garment_analyzer,
    llm_client,
    lyria_client,
    openrouter_video_client,
    seedance_prompt,
    vibe_matcher,
    higgsfield,
)

router = APIRouter()
DEMO_ASSET_NOTE = "Demo asset; v2 will generate on demand."
MUSIC_FALLBACK_URL = "/assets/v2/music-preview.wav"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
UI_DIR = PROJECT_ROOT / "ui"
GENERATED_ASSET_DIR = UI_DIR / "assets" / "generated"


def _dj_available_on(dj: DJListItem, event_date: str | None) -> bool:
    if not event_date:
        return True
    return event_date in set(dj.availability or [])


def _find_ffmpeg() -> str | None:
    configured = (settings.FFMPEG_PATH or "ffmpeg").strip()
    configured_path = Path(configured)
    if configured_path.exists():
        return str(configured_path)
    return shutil.which(configured)


def _resolve_static_asset(url_path: str) -> Path:
    candidate = (UI_DIR / url_path.lstrip("/")).resolve()
    ui_root = UI_DIR.resolve()
    if candidate != ui_root and ui_root not in candidate.parents:
        raise HTTPException(status_code=400, detail="Static asset path is outside the UI directory")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail=f"Static asset '{url_path}' not found")
    return candidate


async def _materialize_media_source(source: str, destination: Path) -> None:
    if source.startswith("data:"):
        try:
            _, payload = source.split(",", 1)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid data URL media source") from exc
        destination.write_bytes(base64.b64decode(payload))
        return

    if source.startswith("/"):
        shutil.copyfile(_resolve_static_asset(source), destination)
        return

    if source.startswith(("http://", "https://")):
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0), follow_redirects=True) as client:
            response = await client.get(source)
            if response.status_code >= 400:
                raise HTTPException(
                    status_code=502,
                    detail=f"Could not download media source ({response.status_code})",
                )
            destination.write_bytes(response.content)
        return

    raise HTTPException(status_code=400, detail="Media source must be a data URL, /assets path, or http(s) URL")


def _resize_data_url_for_seedance(data_url: str, max_dim: int = 1024, quality: int = 85) -> str:
    """Resize an image data URL so it fits Seedance's ~2 MB silent-drop limit.

    Mirrors `evals/seedance_video_eval.py:encode_image` but operates on a base64
    data URL coming from the browser instead of a file path. OpenRouter video
    silently returns `id: null` for image payloads above ~2 MB; re-encoding to
    JPEG quality 85 at max_dim=1024 keeps each reference well under 250 KB.

    Returns the resized data URL, or the original if Pillow is unavailable or
    the input cannot be parsed (defensive — caller still gets a valid string).
    """
    if not data_url or not data_url.startswith("data:"):
        return data_url
    try:
        from io import BytesIO

        from PIL import Image
    except ImportError:
        return data_url

    try:
        _, payload = data_url.split(",", 1)
        raw = base64.b64decode(payload)
    except (ValueError, base64.binascii.Error):
        return data_url

    try:
        img = Image.open(BytesIO(raw))
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_dim:
            ratio = max_dim / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        new_b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/jpeg;base64,{new_b64}"
    except Exception:
        return data_url


async def _ensure_dj_exists(db, dj_id: str) -> None:
    rows = await db.execute_fetchall("SELECT id FROM djs WHERE id = ?", [dj_id])
    if not rows:
        raise HTTPException(status_code=404, detail=f"DJ '{dj_id}' not found")


async def _ensure_venue_exists(db, venue_id: str) -> None:
    rows = await db.execute_fetchall("SELECT id FROM venues WHERE id = ?", [venue_id])
    if not rows:
        raise HTTPException(status_code=404, detail=f"Venue '{venue_id}' not found")


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


def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if item)
    return str(value)


def _audio_guidance_for_music(audio_analysis: dict | None) -> str:
    """Format the uploaded-track analysis for the Lyria music prompt."""
    if not audio_analysis or audio_analysis.get("error"):
        return ""

    rows = []
    for label, key in [
        ("Summary", "summary"),
        ("Genres", "genres"),
        ("BPM", "bpm_estimate"),
        ("Energy", "energy"),
        ("Mood", "mood"),
        ("Production notes", "production_notes"),
        ("Venue signals", "venue_signals"),
    ]:
        text = _as_text(audio_analysis.get(key)).strip()
        if text:
            rows.append(f"{label}: {text}")

    if not rows:
        return ""

    return (
        "Uploaded track analysis from NOCTURNE's audio listener:\n"
        + "\n".join(f"- {row}" for row in rows)
    )


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

    candidate_djs = [dj for dj in all_djs.values() if _dj_available_on(dj, request.event_date)]
    if request.event_date and not candidate_djs:
        return VibeMatchResponse(
            results=[],
            query_interpretation=(
                f"No DJs currently list availability on {request.event_date}. "
                "Try another date or clear the event date filter."
            ),
        )

    query = request.query
    if request.event_date:
        query = f"{request.query}\nEvent date: {request.event_date}. Only rank DJs available on this date."

    matches_raw, interpretation = vibe_matcher.match_djs(
        query, candidate_djs
    )

    results = []
    for m in matches_raw:
        dj = all_djs.get(m.get("dj_id"))
        if dj and _dj_available_on(dj, request.event_date):
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
    """Generate provider-neutral music + voice-over prompts for a DJ-venue pairing.

    Returns two strings the LLM can hand to whichever music and voice
    services are wired in (Lyria 3 today; ElevenLabs is roadmap). The keys
    `music_prompt` and `voice_script` are intentionally provider-neutral.
    """
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
        "1. A music-generation prompt (provider-neutral) for a 30-second clip "
        "matching this DJ's style at this venue.\n"
        "2. A voice-over script for a 15-second promo announcement (provider-"
        "neutral; will be sent to a TTS service).\n\n"
        "Respond ONLY with JSON:\n"
        '{"music_prompt": "...", "voice_script": "..."}'
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
            "music_prompt": f"Electronic music in the style of {dj.name} for {venue.name}.",
            "voice_script": f"NOCTURNE presents {dj.name} at {venue.name}.",
        }


# ── Party Simulation (text scene description) ────────────────────────────────

@router.post("/party-simulation")
async def party_simulation(request: PartySimulationRequest):
    """Generate a provider-neutral video-prompt for a DJ-venue party simulation.

    Produces a JSON video-prompt that downstream code can hand to whichever
    video model is wired in (currently Seedance 2.0 via OpenRouter for the
    personalized class demo; see `/api/ai/demo-performance-video`).
    """
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
    garment_analysis: dict | None = None
    style_segments = [request.style] if request.style else []
    if request.audio_data_url:
        try:
            audio_analysis = await audio_analyzer.analyze(request.audio_data_url)
            phrase = audio_analysis.get("style_phrase")
            if isinstance(phrase, str) and phrase:
                style_segments.append(f"AI heard in the uploaded track: {phrase}")
        except audio_analyzer.AudioAnalyzerError as exc:
            audio_analysis = {"error": str(exc)}

    if request.image_data_urls:
        try:
            garment_analysis = await garment_analyzer.analyze(request.image_data_urls)
            phrase = garment_analysis.get("style_phrase")
            if isinstance(phrase, str) and phrase:
                style_segments.append(f"AI saw in the uploaded photos: {phrase}")
        except garment_analyzer.GarmentAnalyzerError as exc:
            garment_analysis = {"error": str(exc)}

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
        garment_analysis=garment_analysis,
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
            note="Demo asset; live generation requires API credentials.",
        )
    if not request.image_data_urls:
        raise HTTPException(status_code=400, detail="Upload at least one performer image")

    # Build input_references. As of 2026-04-29, Seedance 2.0 / Veo 3.1 / Sora 2
    # refuse images that contain identifiable people via the
    # "InputImageSensitiveContentDetected.PrivacyInformation" filter. The earlier
    # blanket-skip of every performer photo was scoped to that face-photo case.
    # As of 2026-05-01 the user uploads garment-only reference shots (flat lay,
    # mannequin, hanger), which should pass the moderation layer. We forward
    # them as Identity Sheet references so the prompt's wardrobe-preservation
    # language has something to anchor on. Each reference is resized to
    # <=1024 px JPEG to dodge the OpenRouter ~2 MB silent-drop limit.
    # Reference conditioning on Seedance is style-leaning (not 1:1 garment
    # transfer); pixel-true outfit transfer is still v2 work (virtual try-on
    # then img2vid). Tracked in SPEC §9.6.
    venue_image_url = (venue.image_url or "").strip()
    input_references: list[str] = []
    if venue_image_url:
        input_references.append(venue_image_url)

    performer_ref_count = 0
    for data_url in (request.image_data_urls or [])[:3]:  # cap at 3 references
        if not data_url:
            continue
        resized = _resize_data_url_for_seedance(data_url)
        if resized:
            input_references.append(resized)
            performer_ref_count += 1

    # Auto-augment style_text with the Tier 3 wardrobe read so the user does
    # not have to describe the outfit by hand. Mirrors the parallel garment
    # analysis that runs during /api/ai/demo-venue-match. Cheap call (~2s
    # on Gemini Flash) and silent-fallback if it fails — the user's typed
    # style is preserved either way.
    augmented_style = (request.style or "").strip()
    if request.image_data_urls:
        try:
            garment_read = await garment_analyzer.analyze(request.image_data_urls)
            wardrobe_phrase = garment_read.get("style_phrase")
            if isinstance(wardrobe_phrase, str) and wardrobe_phrase:
                sep = " | " if augmented_style else ""
                augmented_style = f"{augmented_style}{sep}wardrobe: {wardrobe_phrase}"
        except garment_analyzer.GarmentAnalyzerError:
            pass

    prompt = seedance_prompt.build_seedance_prompt(
        performer_name=request.performer_name,
        venue=venue,
        style_text=augmented_style,
        has_venue_ref=bool(venue_image_url),
        performer_ref_count=performer_ref_count,
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
        note="Venue simulation queued; rendering now.",
    )


@router.get("/demo-performance-video/{job_id}", response_model=DemoPerformanceVideoResponse)
async def get_demo_performance_video(job_id: str):
    """Poll an OpenRouter video job for the personalized demo.

    When the job is `completed`, OpenRouter only exposes the rendered MP4 at
    `https://openrouter.ai/api/v1/videos/<job_id>/content?index=0`, which
    requires the OpenRouter Bearer token. Browsers can't send that token, so a
    raw `<video src="...openrouter...">` tag fails silently. We download the
    MP4 server-side (with Bearer auth), cache it under
    `ui/assets/generated/seedance-<job_id>.mp4`, and return the local URL so
    the static mount can serve it without auth. Subsequent polls hit the
    cached file.
    """
    try:
        result = await openrouter_video_client.get_video_job(job_id)
    except openrouter_video_client.OpenRouterVideoError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    status = result.get("status", "unknown")
    unsigned_urls = result.get("unsigned_urls") or []
    remote_url = (
        result.get("video_url")
        or (unsigned_urls[0] if unsigned_urls else None)
    )

    local_url: str | None = None
    note = "Venue simulation status."

    if status == "completed" and remote_url:
        GENERATED_ASSET_DIR.mkdir(parents=True, exist_ok=True)
        # Use job_id directly so re-polls land on the same cached file.
        safe_id = "".join(ch for ch in job_id if ch.isalnum() or ch in ("-", "_"))
        cached_path = GENERATED_ASSET_DIR / f"seedance-{safe_id}.mp4"
        if not cached_path.exists() or cached_path.stat().st_size < 1024:
            try:
                headers: dict[str, str] = {}
                if "openrouter.ai" in remote_url and settings.OPENROUTER_API_KEY:
                    headers["Authorization"] = f"Bearer {settings.OPENROUTER_API_KEY}"
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(180.0), follow_redirects=True
                ) as client:
                    response = await client.get(remote_url, headers=headers)
                    response.raise_for_status()
                    cached_path.write_bytes(response.content)
            except httpx.HTTPError as exc:
                # Fall back to returning the remote URL — the browser still
                # can't load it, but the eval / curl path keeps working.
                note = f"Video completed but server-side download failed: {exc!s}"
                return DemoPerformanceVideoResponse(
                    job_id=result.get("id", job_id),
                    status=status,
                    polling_url=result.get("polling_url"),
                    video_url=remote_url,
                    provider="openrouter/video",
                    generated=False,
                    note=note,
                )
        local_url = f"/assets/generated/seedance-{safe_id}.mp4"
        note = "Venue simulation ready."

    return DemoPerformanceVideoResponse(
        job_id=result.get("id", job_id),
        status=status,
        polling_url=result.get("polling_url"),
        video_url=local_url or remote_url,
        provider="openrouter/video",
        generated=bool(local_url),
        note=note,
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

    performer_style = (request.combined_style or request.style).strip()
    audio_guidance = _audio_guidance_for_music(request.audio_analysis)
    audio_direction = (
        f"\n\n{audio_guidance}\n"
        "Use that uploaded-track analysis as the primary musical fingerprint: "
        "preserve its tempo range, groove feel, energy, mood, and production textures "
        "where compatible with the venue. Compose a NEW instrumental clip inspired by "
        "those qualities; do not copy melodies, vocals, lyrics, samples, or any "
        "recognizable protected expression from the uploaded track."
        if audio_guidance
        else ""
    )
    prompt = (
        f"Compose a 30-second instrumental music clip for a DJ named {request.performer_name} "
        f"performing at {venue.name} in {venue.city or 'the city'}. "
        f"Performer style and match context: {performer_style}. "
        f"Venue atmosphere: {', '.join(venue.vibe_tags) or 'club, electronic'}. "
        f"Venue description: {venue.description or 'electronic club venue'}."
        f"{audio_direction}\n\n"
        "Make the output feel like a venue-ready extension of the uploaded track's "
        "sonic identity, adapted to this room. Produce a peak-time club loop with a "
        "clear groove and club-soundsystem low end. No vocals. No spoken word. "
        "Instrumental only."
    )

    if not lyria_client.is_configured():
        return DemoMusicPreviewResponse(
            audio_url=MUSIC_FALLBACK_URL,
            prompt=prompt,
            provider="lyria-3-clip-preview",
            generated=False,
            note="Demo asset; live generation requires API credentials.",
        )

    try:
        result = await lyria_client.generate_clip(prompt)
    except lyria_client.LyriaError as exc:
        return DemoMusicPreviewResponse(
            audio_url=MUSIC_FALLBACK_URL,
            prompt=prompt,
            provider="lyria-3-clip-preview",
            generated=False,
            note="Live music generation produced no audio; using the fallback soundtrack.",
        )

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
        note="Music preview ready.",
    )


@router.post("/demo-performance-video/mux", response_model=DemoMuxVideoResponse)
async def mux_demo_performance_video(request: DemoMuxVideoRequest):
    """Mux a completed silent video with the generated Lyria soundtrack."""
    audio_source = request.audio_data_url or request.audio_url
    if not audio_source:
        raise HTTPException(status_code=400, detail="Provide audio_url or audio_data_url")

    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return DemoMuxVideoResponse(
            provider="ffmpeg",
            generated=False,
            note=(
                "ffmpeg is not installed or not on PATH. Set FFMPEG_PATH in .env "
                "to enable exported MP4s with music baked in."
            ),
        )

    GENERATED_ASSET_DIR.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:12]
    work_dir = GENERATED_ASSET_DIR / f"mux-{run_id}"
    work_dir.mkdir(parents=True, exist_ok=True)
    video_input = work_dir / "video.mp4"
    audio_input = work_dir / "audio.bin"
    output_path = GENERATED_ASSET_DIR / f"performance-with-music-{run_id}.mp4"

    try:
        await _materialize_media_source(request.video_url, video_input)
        await _materialize_media_source(audio_source, audio_input)

        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(video_input),
            "-i",
            str(audio_input),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        completed = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "ffmpeg failed").strip()[-800:]
            raise HTTPException(status_code=502, detail=f"ffmpeg mux failed: {detail}")
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="ffmpeg mux timed out") from exc
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    return DemoMuxVideoResponse(
        video_url=f"/assets/generated/{output_path.name}",
        provider="ffmpeg",
        generated=True,
        note="Generated MP4 with the Lyria soundtrack muxed into the video file.",
    )


@router.post("/music-preview", response_model=DemoAssetResponse)
async def music_preview(request: MusicPreviewRequest):
    """Return the canned music preview fallback asset for legacy callers."""
    db = await get_db()
    try:
        await _ensure_dj_exists(db, request.dj_id)
        await _ensure_venue_exists(db, request.venue_id)
    finally:
        await db.close()

    return DemoAssetResponse(
        audio_url=MUSIC_FALLBACK_URL,
        provider="lyria-3-clip-preview",
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
