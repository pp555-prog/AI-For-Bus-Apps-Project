from fastapi import APIRouter, HTTPException, Query

from backend.database import get_db
from backend.models import DJ, DJListItem

router = APIRouter()


@router.get("/djs", response_model=list[DJListItem])
async def list_djs(
    setup: str | None = Query(None, description="Filter by setup: digital, vinyl, hybrid"),
    fee_tier: str | None = Query(None, description="Filter by fee tier: boutique, premium, elite"),
    bpm_low: int | None = Query(None, description="Minimum BPM"),
    bpm_high: int | None = Query(None, description="Maximum BPM"),
    limit: int = Query(50, ge=1, le=100),
):
    """List DJs with optional filters."""
    query = "SELECT * FROM djs WHERE 1=1"
    params: list = []

    if setup:
        query += " AND setup = ?"
        params.append(setup)
    if fee_tier:
        query += " AND fee_tier = ?"
        params.append(fee_tier)
    if bpm_low is not None:
        query += " AND bpm_high >= ?"
        params.append(bpm_low)
    if bpm_high is not None:
        query += " AND bpm_low <= ?"
        params.append(bpm_high)

    query += " ORDER BY fee_from DESC LIMIT ?"
    params.append(limit)

    db = await get_db()
    try:
        rows = await db.execute_fetchall(query, params)
        return [DJListItem(**dict(row)) for row in rows]
    finally:
        await db.close()


@router.get("/djs/{dj_id}", response_model=DJ)
async def get_dj(dj_id: str):
    """Get full DJ profile by ID."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall("SELECT * FROM djs WHERE id = ?", [dj_id])
        if not rows:
            raise HTTPException(status_code=404, detail=f"DJ '{dj_id}' not found")
        return DJ(**dict(rows[0]))
    finally:
        await db.close()
