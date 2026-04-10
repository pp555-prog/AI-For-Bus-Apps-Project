from datetime import datetime, timedelta

from fastapi import APIRouter

from backend.database import get_db
from backend.models import RadarEvent

router = APIRouter()


def _time_ago(created_at: str) -> str:
    """Convert an ISO timestamp to a human-readable 'X ago' string."""
    try:
        ts = datetime.fromisoformat(created_at)
    except (ValueError, TypeError):
        return "recently"

    delta = datetime.utcnow() - ts
    minutes = int(delta.total_seconds() / 60)

    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} min ago"

    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours > 1 else ''} ago"

    days = hours // 24
    return f"{days} day{'s' if days > 1 else ''} ago"


def _action_from_status(status: str) -> str:
    return {
        "confirmed": "booked",
        "pending": "received an offer from",
        "declined": "declined",
    }.get(status, "connected with")


@router.get("/radar", response_model=list[RadarEvent])
async def get_radar():
    """Return recent bookings as live radar events."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """
            SELECT b.status, b.created_at,
                   d.name AS dj_name, v.name AS venue_name
            FROM bookings b
            JOIN djs d ON b.dj_id = d.id
            LEFT JOIN venues v ON b.venue_id = v.id
            ORDER BY b.created_at DESC
            LIMIT 10
            """
        )
        return [
            RadarEvent(
                venue_name=dict(row).get("venue_name") or "A venue",
                dj_name=dict(row)["dj_name"],
                action=_action_from_status(dict(row)["status"]),
                time_ago=_time_ago(dict(row)["created_at"]),
            )
            for row in rows
        ]
    finally:
        await db.close()
