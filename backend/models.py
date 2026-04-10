from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, field_validator


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_json_field(v: Any) -> Any:
    """Transparently deserialise JSON-encoded TEXT columns from SQLite."""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except (json.JSONDecodeError, TypeError):
            return v
    return v


# ── DJ ───────────────────────────────────────────────────────────────────────

class DJ(BaseModel):
    id: str
    name: str
    tagline: str | None = None
    genres: list[str] = []
    bio: str | None = None
    image_url: str | None = None
    bpm_low: int | None = None
    bpm_high: int | None = None
    setup: str | None = None
    fee_tier: str | None = None
    fee_from: int | None = None
    badge: str | None = None
    vibe_keywords: list[str] = []
    tech_rider: dict = {}
    availability: list[str] = []
    soundcloud_url: str | None = None

    @field_validator("genres", "vibe_keywords", "availability", mode="before")
    @classmethod
    def _parse_list(cls, v: Any) -> list[str]:
        return _parse_json_field(v) if v else []

    @field_validator("tech_rider", mode="before")
    @classmethod
    def _parse_dict(cls, v: Any) -> dict:
        return _parse_json_field(v) if v else {}


class DJListItem(BaseModel):
    id: str
    name: str
    tagline: str | None = None
    genres: list[str] = []
    image_url: str | None = None
    setup: str | None = None
    fee_tier: str | None = None
    fee_from: int | None = None
    badge: str | None = None

    @field_validator("genres", mode="before")
    @classmethod
    def _parse_list(cls, v: Any) -> list[str]:
        return _parse_json_field(v) if v else []


# ── Venue ────────────────────────────────────────────────────────────────────

class Venue(BaseModel):
    id: str
    name: str
    city: str | None = None
    capacity: int | None = None
    vibe_tags: list[str] = []
    image_url: str | None = None
    description: str | None = None

    @field_validator("vibe_tags", mode="before")
    @classmethod
    def _parse_list(cls, v: Any) -> list[str]:
        return _parse_json_field(v) if v else []


# ── Booking ──────────────────────────────────────────────────────────────────

class BookingCreate(BaseModel):
    dj_id: str
    venue_id: str | None = None
    venue_name: str | None = None
    date: str
    start_time: str
    set_length: str
    offered_fee: int


class BookingResponse(BaseModel):
    id: int
    dj_id: str
    venue_id: str | None = None
    date: str
    start_time: str
    set_length: str
    offered_fee: int
    status: str
    created_at: str | None = None


# ── AI: Vibe Match ──────────────────────────────────────────────────────────

class VibeMatchRequest(BaseModel):
    query: str


class VibeMatchResult(BaseModel):
    dj: DJListItem
    score: int
    reasoning: str


class VibeMatchResponse(BaseModel):
    results: list[VibeMatchResult]
    query_interpretation: str | None = None


# ── AI: Bio / Promo ─────────────────────────────────────────────────────────

class BioGenerateRequest(BaseModel):
    dj_id: str


class PromoPromptRequest(BaseModel):
    dj_id: str
    venue_id: str


class PartySimulationRequest(BaseModel):
    dj_id: str
    venue_id: str


# ── Radar ────────────────────────────────────────────────────────────────────

class RadarEvent(BaseModel):
    venue_name: str
    dj_name: str
    action: str
    time_ago: str
