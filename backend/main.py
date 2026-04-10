from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.database import init_db
from backend.seed import seed_db
from backend.routers import djs, venues, bookings, ai, radar


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_db()
    yield


app = FastAPI(title="NOCTURNE API", version="0.1.0", lifespan=lifespan)

# CORS — allow everything for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers (mounted BEFORE static files so /api/* takes priority)
app.include_router(djs.router, prefix="/api", tags=["DJs"])
app.include_router(venues.router, prefix="/api", tags=["Venues"])
app.include_router(bookings.router, prefix="/api", tags=["Bookings"])
app.include_router(ai.router, prefix="/api/ai", tags=["AI"])
app.include_router(radar.router, prefix="/api", tags=["Radar"])

# Static files — serve the Stitch UI from project root /ui
ui_dir = Path(__file__).resolve().parent.parent / "ui"
app.mount("/", StaticFiles(directory=str(ui_dir), html=True), name="static")
