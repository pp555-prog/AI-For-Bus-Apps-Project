import aiosqlite
from backend.config import settings

DATABASE_PATH = settings.DATABASE_PATH


async def get_db() -> aiosqlite.Connection:
    """Return a new connection. Caller must close it or use as async context manager."""
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    """Create tables if they don't exist."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS djs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                tagline TEXT,
                genres TEXT,
                bio TEXT,
                image_url TEXT,
                bpm_low INTEGER,
                bpm_high INTEGER,
                setup TEXT,
                fee_tier TEXT,
                fee_from INTEGER,
                badge TEXT,
                vibe_keywords TEXT,
                tech_rider TEXT,
                availability TEXT,
                soundcloud_url TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS venues (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                city TEXT,
                capacity INTEGER,
                vibe_tags TEXT,
                image_url TEXT,
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dj_id TEXT REFERENCES djs(id),
                venue_id TEXT REFERENCES venues(id),
                date TEXT,
                start_time TEXT,
                set_length TEXT,
                offered_fee INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        await db.commit()
