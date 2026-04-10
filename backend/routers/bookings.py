from fastapi import APIRouter, HTTPException

from backend.database import get_db
from backend.models import BookingCreate, BookingResponse

router = APIRouter()


@router.post("/bookings", response_model=BookingResponse, status_code=201)
async def create_booking(booking: BookingCreate):
    """Submit a booking offer."""
    db = await get_db()
    try:
        # Verify DJ exists
        dj_rows = await db.execute_fetchall("SELECT id FROM djs WHERE id = ?", [booking.dj_id])
        if not dj_rows:
            raise HTTPException(status_code=404, detail=f"DJ '{booking.dj_id}' not found")

        cursor = await db.execute(
            """INSERT INTO bookings (dj_id, venue_id, date, start_time, set_length, offered_fee, status)
               VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
            [
                booking.dj_id,
                booking.venue_id,
                booking.date,
                booking.start_time,
                booking.set_length,
                booking.offered_fee,
            ],
        )
        await db.commit()
        booking_id = cursor.lastrowid

        rows = await db.execute_fetchall("SELECT * FROM bookings WHERE id = ?", [booking_id])
        return BookingResponse(**dict(rows[0]))
    finally:
        await db.close()


@router.get("/bookings", response_model=list[BookingResponse])
async def list_bookings():
    """List all bookings, newest first."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall("SELECT * FROM bookings ORDER BY created_at DESC")
        return [BookingResponse(**dict(row)) for row in rows]
    finally:
        await db.close()
