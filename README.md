# NOCTURNE — DJ-Venue Marketplace

> AI-powered matchmaking between DJs and venues — smart matching, immersive simulations, and instant promo content.

## Overview

DJ-Venue Marketplace is a platform that connects DJs with venues using intelligent matching based on budget, music style, and event requirements. Beyond matchmaking, it leverages AI integrations to let both parties preview what an event would actually feel and sound like — generating party simulations and promotional materials — before any booking is confirmed.

The platform is designed to reduce the friction of booking the right DJ for the right space, while giving both DJs and venues powerful tools to market themselves.

## Key Features

- **Smart Matching** — Match DJs and venues based on budget, music genre, crowd size, vibe, and availability
- **Party Simulations** — Generate AI video previews of what an event would look like using video generation AI
- **Promotional Content** — Auto-generate promo materials (videos, reels, clips) for DJs and venues
- **AI Music Previews** — Let venues hear AI-generated music samples tailored to their space via Suno
- **Voice Matching** — Use ElevenLabs to incorporate voice features (e.g., DJ intros, venue announcements, promo narration)
- **Marketplace UI** — Clean, intuitive interface built with Stitch

## Tech Stack

| Tool / Platform | Purpose |
|----------------|---------|
| [Stitch](https://stitch.withgoogle.com) | Frontend UI / marketplace interface (Tailwind CSS) |
| [FastAPI](https://fastapi.tiangolo.com) | Python backend API |
| [Claude API](https://docs.anthropic.com) | AI-powered vibe matching and content generation |
| [Suno](https://suno.com) | AI music generation for previews and promo |
| [ElevenLabs](https://elevenlabs.io) | Voice synthesis for DJ intros, narration, and voice matching |
| [Higgsfield](https://higgsfield.ai) | AI video generation for party simulations |
| SQLite | Lightweight database for MVP |

## How It Works

```
DJ Profile          Venue Profile
(genre, rate,  ───► (capacity, vibe,  ───► AI Matching Engine
 availability)       budget, location)          │
                                                 ▼
                                       Match Results & Recommendations
                                                 │
                          ┌──────────────────────┼──────────────────────┐
                          ▼                      ▼                      ▼
                   Music Preview          Party Simulation        Promo Materials
                   (Suno)                 (Video AI)              (Video + ElevenLabs)
```

## Project Structure

```
AI-For-Bus-Apps-Project/
├── backend/                  # FastAPI backend
│   ├── main.py               # App entry point, mounts static UI + API routers
│   ├── config.py             # Pydantic Settings (.env reader)
│   ├── database.py           # SQLite via aiosqlite
│   ├── models.py             # Pydantic request/response schemas
│   ├── seed.py               # 10 DJs, 7 venues, 3 bookings — auto-seeds on first run
│   ├── routers/
│   │   ├── djs.py            # GET /api/djs, GET /api/djs/{id}
│   │   ├── venues.py         # GET /api/venues, GET /api/venues/{id}
│   │   ├── bookings.py       # POST /api/bookings, GET /api/bookings
│   │   ├── ai.py             # POST /api/ai/vibe-match, /generate-bio, /promo-prompt, /party-simulation
│   │   └── radar.py          # GET /api/radar (live booking feed)
│   └── services/
│       ├── claude_client.py  # Anthropic SDK wrapper
│       ├── vibe_matcher.py   # Claude-powered DJ matching engine
│       └── higgsfield.py     # Higgsfield video generation prompts
├── ui/                       # Stitch-generated frontend (HTML/Tailwind CSS)
│   ├── discovery.html        # Home — editorial DJ grid + live radar + venue showcase
│   ├── search.html           # Vibe search — AI filter sidebar + DJ result cards
│   ├── vibe-search.html      # DJ profile — bio, promo vault, tech rider, calendar
│   └── booking.html          # Booking offer form with escrow CTA
├── requirements.txt
├── .env.example
├── run.py                    # python run.py → starts uvicorn on port 8000
├── SPEC.docx                 # Product Requirements Document
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.10+
- Anthropic API key (for Claude-powered vibe matching)

### Installation

```bash
git clone https://github.com/pabloqc98/AI-For-Bus-Apps-Project.git
cd AI-For-Bus-Apps-Project
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Run

```bash
python run.py
```

Open **http://localhost:8000/discovery.html** — the database auto-seeds with sample DJs and venues on first run.

### API Docs

FastAPI auto-generates interactive docs at **http://localhost:8000/docs**.

## Course Context

This project was developed for **NBA 6925: Advanced AI for Business Applications** at Cornell University.

## License

MIT
