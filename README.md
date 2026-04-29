# NOCTURNE — DJ-Venue Marketplace

> AI-powered matchmaking between DJs and venues — smart matching, immersive simulations, and instant promo content.

## Overview

DJ-Venue Marketplace is a platform that connects DJs with venues using intelligent matching based on budget, music style, and event requirements. Beyond matchmaking, it leverages AI integrations to let both parties preview what an event would actually feel and sound like — generating party simulations and promotional materials — before any booking is confirmed.

The platform is designed to reduce the friction of booking the right DJ for the right space, while giving both DJs and venues powerful tools to market themselves.

## Key Features

### v1 — Live
- **Smart Matching** — LLM-powered (default: `openai/gpt-oss-120b:free` via OpenRouter) matches DJs and venues by genre, vibe, capacity, and location, returning ranked results with written reasoning
- **AI Bio Generation** — drafts DJ profile bios from structured input (genres, style tags, experience)
- **AI Promo Prompts** — generates promo-content prompts tailored to a DJ's brand and a venue's vibe
- **Party Simulation Text** — produces descriptive scene text used to seed downstream video tools
- **Audio-driven Venue Match** — performers can upload a track on `/personal-demo.html`; an audio-input LLM (`google/gemini-2.5-flash` via OpenRouter) listens to the first 30s and returns a structured style read (genres, BPM, energy, mood, venue archetypes) that augments the typed style for venue matching
- **AI Music Previews** — Google Lyria 3 generates a ~30s instrumental clip tailored to the matched venue + performer style (routed through OpenRouter; `google/lyria-3-clip-preview`; preview pricing currently $0/call, expected ~$0.04/clip when GA)
- **Personalized video previews** — OpenRouter video generation submits an async reference-video job from uploaded performer photos for the class demo (`bytedance/seedance-2.0`, 720p, 10 s, silent — `generate_audio: false`; the Lyria clip plays as the soundtrack alongside the silent video)
- **Booking Confirmation Emails** — n8n workflow sends templated emails to both DJ and venue when a booking inquiry is submitted
- **Marketplace UI** — Clean, intuitive interface built with Stitch (Tailwind CSS)

### v2 — Roadmap
- **Voice Features** — ElevenLabs DJ intros, venue announcements, and AI promo narration

## Tech Stack

| Tool / Platform | Phase | Purpose |
|----------------|-------|---------|
| [Stitch](https://stitch.withgoogle.com) | v1 — live | Frontend UI / marketplace interface (Tailwind CSS) |
| [FastAPI](https://fastapi.tiangolo.com) | v1 — live | Python backend API |
| [OpenRouter](https://openrouter.ai) | **v1 — live** | Single-key router for every AI call: the LLM (vibe matching, bio generation, promo prompts, party simulation text, venue match reasoning — `OPENROUTER_MODEL`, default `openai/gpt-oss-120b:free`), the audio-input analyzer for the personalized demo (`OPENROUTER_AUDIO_MODEL`, default `google/gemini-2.5-flash`), the music generator (Lyria, separate row below), and the video generator (Seedance, separate row below). Each is swappable via env var without code changes. |
| SQLite | v1 — live | Lightweight database for MVP |
| [n8n](https://n8n.io) | **v1 — live** | Workflow automation — booking confirmation emails (DJ + venue) on every booking inquiry |
| [OpenAI Codex](https://platform.openai.com/docs/guides/code) | dev tool | AI-assisted code generation used during development; not a runtime feature |
| [Google Lyria 3](https://openrouter.ai/google/lyria-3-clip-preview) | **v1 — live** | AI music generation (instrumental clips) routed through OpenRouter; default model `google/lyria-3-clip-preview`. Requires `modalities: ["text","audio"]` + `stream: true` to return audio. |
| [OpenRouter Video](https://openrouter.ai/docs/guides/overview/multimodal/video-generation) | **v1 — live** (class demo) | Async AI video generation for personalized party simulations; default model `bytedance/seedance-2.0`, 720p / 10 s, silent (`generate_audio: false`). Observed wall-clock ~140 s per clip. |
| [ElevenLabs](https://elevenlabs.io) | v2 | Voice synthesis for DJ intros, narration, voice matching |

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
                   (Lyria 3)              (OpenRouter Video)      (Video + ElevenLabs)
```

## Project Structure

```text
AI-For-Bus-Apps-Project/
|-- backend/                  # FastAPI backend
|   |-- main.py               # App entry point, mounts static UI + API routers
|   |-- config.py             # Pydantic Settings (.env reader)
|   |-- database.py           # SQLite via aiosqlite
|   |-- models.py             # Pydantic request/response schemas
|   |-- seed.py               # 10 DJs, 7 venues, 3 bookings; auto-seeds on first run
|   |-- routers/
|   |   |-- djs.py            # GET /api/djs, GET /api/djs/{id}
|   |   |-- venues.py         # GET /api/venues, GET /api/venues/{id}
|   |   |-- bookings.py       # Booking create/list/status endpoints
|   |   |-- ai.py             # Vibe match, demo venue match, OpenRouter video endpoints
|   |   `-- radar.py          # GET /api/radar (live booking feed)
|   `-- services/
|       |-- llm_client.py     # LLM wrapper; OpenAI SDK pointed at OpenRouter
|       |-- vibe_matcher.py   # LLM-powered DJ + venue matching engine
|       |-- audio_analyzer.py # OpenRouter audio-input client (style read for personalized demo)
|       |-- openrouter_video_client.py # OpenRouter async video generation
|       |-- seedance_prompt.py # Seedance prompt builder (Seedance 2.0 AI Handbook structure)
|       |-- lyria_client.py   # OpenRouter Lyria 3 music generation
|       `-- higgsfield.py     # Legacy party-simulation prompt helper
|-- ui/                       # Stitch-generated frontend (HTML/Tailwind CSS)
|   |-- discovery.html        # Home; editorial DJ grid + live radar + venue showcase
|   |-- search.html           # Vibe search; AI filter sidebar + DJ result cards
|   |-- vibe-search.html      # DJ profile; bio, promo vault, tech rider, calendar
|   |-- personal-demo.html    # Personalized class demo: photo + audio upload, venue match, Lyria + Seedance
|   |-- booking.html          # Booking offer form with escrow CTA
|   `-- assets/v2/            # Static fallback MP3/MP4 served when OPENROUTER_API_KEY is missing
|-- evals/                    # Eval harnesses for SPEC §9
|   |-- run_eval.py           # §9.3 DJ-match eval (text-only LLM matcher)
|   |-- compute_metrics.py    # §9.3 metrics report
|   |-- audio_match_eval.py   # §9.4 audio-driven match eval (paired T vs T+A)
|   |-- audio_compute_metrics.py # §9.4 lift metrics report
|   |-- audio_samples/        # Per-venue audio clips for §9.4 (gitignored)
|   `-- seedance_prompt_eval.py # §9.5 Seedance prompt-structure linter (handbook-based)
|-- n8n/
|   `-- workflows/booking_confirmation.json  # n8n workflow JSON; import into n8n Cloud
|-- AGENTS.md                 # Universal AI agent onboarding; READ FIRST
|-- CLAUDE.md                 # Claude-specific notes (defers to AGENTS.md)
|-- Review at the start of each session and update at the end of each session.txt
|-- SPEC.docx                 # Product Requirements Document (incl. eval plan in Section 9)
|-- README.md                 # This file; public-facing project intro
|-- init.sh                   # First-time setup
|-- run.py                    # python run.py starts uvicorn on port 8000
|-- requirements.txt
|-- .env.example
`-- nocturne.db               # SQLite (auto-created on first run; gitignored)
```

## Getting Started

### Prerequisites

- Python 3.10+
- OpenRouter API key (free tier works — get one at https://openrouter.ai/settings/keys, no credit card required)
- n8n Cloud workspace (for v1 booking confirmation emails)

### Installation

```bash
git clone https://github.com/pabloqc98/AI-For-Bus-Apps-Project.git
cd AI-For-Bus-Apps-Project
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY
# (optional) change OPENROUTER_MODEL — default is openai/gpt-oss-120b:free
```

OpenRouter video, music, and audio-input generation all use the same
`OPENROUTER_API_KEY` as the LLM features. Configure `OPENROUTER_VIDEO_MODEL`,
`OPENROUTER_VIDEO_RESOLUTION`, `OPENROUTER_VIDEO_DURATION`, and
`OPENROUTER_VIDEO_ASPECT_RATIO` in `.env` to control the personalized
performance-video demo. `OPENROUTER_MUSIC_MODEL` controls Lyria (default
`google/lyria-3-clip-preview`); `OPENROUTER_AUDIO_MODEL` controls the
audio-input model used for the "listen to my track" step (default
`google/gemini-2.5-flash`).

For n8n Cloud, create or open the project workspace in n8n Cloud and copy its
workspace URL into `N8N_CLOUD_WORKSPACE_URL` in `.env`. Leave
`N8N_BOOKING_WEBHOOK` blank until the booking confirmation workflow is created;
n8n will provide the production webhook URL from the Webhook node after that
workflow exists and is activated.

#### n8n booking confirmation workflow

The booking confirmation workflow lives at
`n8n/workflows/booking_confirmation.json`.

1. In n8n Cloud, go to **Workflows** -> **Add workflow** -> **Import from File**
   and select `n8n/workflows/booking_confirmation.json`.
2. Open each **Send Email** node and choose or create an SMTP credential. Any
   SMTP provider works; update the `From Email` field if your provider requires
   an approved sender address.
3. Open the **Booking Confirmation Webhook** node. After the workflow is saved
   and activated, n8n shows the Production URL for the POST webhook at path
   `booking-confirmation`. Copy that production URL into `.env` as
   `N8N_BOOKING_WEBHOOK`.
4. Activate the workflow in n8n Cloud. Keep it inactive until the SMTP
   credential is configured and both email nodes are ready to send.

### Run

```bash
python run.py
```

Open **http://localhost:8000/discovery.html** — the database auto-seeds with sample DJs and venues on first run.

### API Docs

FastAPI auto-generates interactive docs at **http://localhost:8000/docs**.

## Course Context

This project was developed for **NBA 6925: Advanced AI for Business Applications** at Cornell University. See `SPEC.docx` Section 9 for the AI evaluation plan and target metrics.

## For AI Agents (Claude, Codex, Cursor, etc.)

If you are an AI agent working on this codebase:

1. **Read [`AGENTS.md`](./AGENTS.md) first.** It is the canonical onboarding document.
2. **Then read the session log** — `Review at the start of each session and update at the end of each session.txt` in the project root.
3. **Append a new `SESSION N` block** to that log at the end of every working session.

Claude Code users: `CLAUDE.md` auto-loads and points to the same place.

## License

MIT
