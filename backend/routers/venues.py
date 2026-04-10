from fastapi import APIRouter, HTTPException

from backend.database import get_db
from backend.models import Venue

router = APIRouter()


@router.get("/venues", response_model=list[Venue])
async def list_venues():
    """List all venues."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall("SELECT * FROM venues ORDER BY name")
        return [Venue(**dict(row)) for row in rows]
    finally:
        await db.close()


@router.get("/venues/{venue_id}", response_model=Venue)
async def get_venue(venue_id: str):
    """Get single venue by ID."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall("SELECT * FROM venues WHERE id = ?", [venue_id])
        if not rows:
            raise HTTPException(status_code=404, detail=f"Venue '{venue_id}' not found")
        return Venue(**dict(rows[0]))
    finally:
        await db.close()
