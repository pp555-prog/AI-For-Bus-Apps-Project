import logging

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.config import settings
from backend.database import get_db
from backend.models import BookingCreate, BookingResponse

router = APIRouter()
logger = logging.getLogger(__name__)


async def _fetch_booking(db, booking_id: int) -> BookingResponse:
    rows = await db.execute_fetchall("SELECT * FROM bookings WHERE id = ?", [booking_id])
    if not rows:
        raise HTTPException(status_code=404, detail=f"Booking '{booking_id}' not found")
    return BookingResponse(**dict(rows[0]))


async def _post_booking_webhook(payload: dict):
    webhook_url = settings.N8N_BOOKING_WEBHOOK
    if not webhook_url:
        return

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()
    except Exception as exc:
        logger.warning("n8n booking webhook failed: %s", exc)


@router.post("/bookings", response_model=BookingResponse, status_code=201)
async def create_booking(booking: BookingCreate, background_tasks: BackgroundTasks):
    """Submit a booking offer."""
    db = await get_db()
    try:
        # Verify DJ exists
        dj_rows = await db.execute_fetchall(
            "SELECT id, name, email FROM djs WHERE id = ?",
            [booking.dj_id],
        )
        if not dj_rows:
            raise HTTPException(status_code=404, detail=f"DJ '{booking.dj_id}' not found")

        venue_id = booking.venue_id
        if venue_id:
            venue_rows = await db.execute_fetchall(
                "SELECT id, name, email FROM venues WHERE id = ?",
                [venue_id],
            )
            if not venue_rows:
                raise HTTPException(status_code=404, detail=f"Venue '{venue_id}' not found")
        elif booking.venue_name:
            venue_rows = await db.execute_fetchall(
                "SELECT id, name, email FROM venues WHERE lower(name) = lower(?)",
                [booking.venue_name],
            )
            if venue_rows:
                venue_id = venue_rows[0]["id"]

        cursor = await db.execute(
            """INSERT INTO bookings
               (dj_id, venue_id, date, start_time, set_length, offered_fee, message, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
            [
                booking.dj_id,
                venue_id,
                booking.date,
                booking.start_time,
                booking.set_length,
                booking.offered_fee,
                booking.message,
            ],
        )
        await db.commit()
        booking_id = cursor.lastrowid

        rows = await db.execute_fetchall(
            """SELECT
                   b.*,
                   d.name AS dj_name,
                   d.email AS dj_email,
                   v.name AS joined_venue_name,
                   v.email AS venue_email
               FROM bookings b
               JOIN djs d ON d.id = b.dj_id
               LEFT JOIN venues v ON v.id = b.venue_id
               WHERE b.id = ?""",
            [booking_id],
        )
        booking_row = dict(rows[0])
        venue_name = booking_row["joined_venue_name"] or booking.venue_name or "Unknown Venue"
        message = booking_row["message"] or "No message provided."

        # n8n expects flat JSON; do not wrap these fields in a "body" object.
        webhook_payload = {
            "dj_name": booking_row["dj_name"],
            "dj_email": booking_row["dj_email"],
            "venue_name": venue_name,
            "venue_email": booking_row["venue_email"],
            "event_date": booking_row["date"],
            "budget": booking_row["offered_fee"],
            "message": message,
        }

        if settings.N8N_BOOKING_WEBHOOK:
            if webhook_payload["dj_email"] and webhook_payload["venue_email"]:
                background_tasks.add_task(_post_booking_webhook, webhook_payload)
            else:
                logger.warning(
                    "Skipping n8n booking webhook for booking %s because DJ or venue email is missing.",
                    booking_id,
                )

        return BookingResponse(**booking_row)
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


@router.get("/bookings/{booking_id}", response_model=BookingResponse)
async def get_booking(booking_id: int):
    """Get a single booking by ID."""
    db = await get_db()
    try:
        return await _fetch_booking(db, booking_id)
    finally:
        await db.close()


async def _set_booking_status(booking_id: int, status: str):
    db = await get_db()
    try:
        await _fetch_booking(db, booking_id)
        await db.execute(
            "UPDATE bookings SET status = ? WHERE id = ?",
            [status, booking_id],
        )
        await db.commit()
        return await _fetch_booking(db, booking_id)
    finally:
        await db.close()


@router.patch("/bookings/{booking_id}/confirm", response_model=BookingResponse)
async def confirm_booking(booking_id: int):
    """Mark a booking as confirmed."""
    return await _set_booking_status(booking_id, "confirmed")


@router.patch("/bookings/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(booking_id: int):
    """Mark a booking as cancelled."""
    return await _set_booking_status(booking_id, "cancelled")
