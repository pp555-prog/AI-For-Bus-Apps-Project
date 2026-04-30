# NOCTURNE — Tasks

This is the canonical task list for the **product** (the DJ-Venue marketplace platform itself). It tracks what's built, what's planned, and what's roadmap. Class-related deliverables (presentation, eval write-up, user study) live in the session log, not here.

If you are an agent, read [`AGENTS.md`](./AGENTS.md) first, then the session log, then this file. Pick an unchecked item, build it, check the box, append to the session log.

---

## v1 — Built (Live Today)

These are working in the deployed product.

- [x] **DJ profiles** — name, bio, genres, style tags, rate, location, links, availability
- [x] **Venue profiles** — name, type, vibe, genres, capacity, budget, location
- [x] **Profile browsing UI** — `discovery.html`, `search.html`, `vibe-search.html`
- [x] **Booking inquiry flow** — `booking.html` → `POST /api/bookings`
- [x] **Live radar feed** — `GET /api/radar` returns recent bookings with `time_ago`
- [x] **LLM vibe matching** — `POST /api/ai/vibe-match` returns ranked DJ matches with reasoning. Routed via OpenRouter; default model `openai/gpt-oss-120b:free`. Swappable via `OPENROUTER_MODEL`.
- [x] **LLM bio generation** — `POST /api/ai/generate-bio` drafts DJ bios from structured input
- [x] **LLM promo prompts** — `POST /api/ai/promo-prompt` generates promo content prompts
- [x] **LLM party-simulation text** — `POST /api/ai/party-simulation` produces scene descriptions
- [x] **Audio-driven venue matching** — `POST /api/ai/demo-venue-match` accepts an optional uploaded audio clip; frontend trims to 30s mono 16 kHz WAV; OpenRouter `google/gemini-2.5-flash` returns a structured style read; the LLM venue matcher (`vibe_matcher.match_venues`) ranks venues with reasoning using the augmented style
- [x] **Audio-match eval harness (SPEC §9.4)** — `evals/audio_match_eval.py` + `audio_compute_metrics.py` run a paired T vs T+A comparison on the demo-venue-match endpoint (one audio clip per seeded venue, neutral typed style as the control). Eval runs are pending audio sample collection
- [x] **Seedance prompt-structure eval (SPEC §9.5)** — `evals/seedance_prompt_eval.py` is a deterministic linter that verifies the rendered Seedance video prompt follows the Seedance 2.0 AI Handbook. 15 checks per venue: Single-Shot Skeleton sections (p.7), asset roles (p.5), camera/lighting/constraint vocabulary (p.16), banned anti-patterns (p.14), and a mode-aware camera-structure check that auto-detects Single-Shot (one dominant move) vs Multi-Shot (three Establish/Develop/Payoff beats per p.8). Costs $0, runs in milliseconds, exits non-zero on regression. Currently passing 3/3 canned venues under the Multi-Shot prompt shipped 2026-04-30.
- [x] **Seedance video output eval harness (SPEC §9.6)** — `evals/seedance_video_eval.py` + `seedance_video_compute_metrics.py` run real Seedance generations conditioned on the seeded venue image, download the MP4s, and score them on a 5-dimension handbook-aligned rubric (identity preservation / venue fidelity / action clarity / camera coherence / behavioral realism) + a yes/no constraints check. Targets composite ≥ 4.0 and pass rate ≥ 70%. Cost: N × ~$1.51 per Seedance run. First end-to-end run completed 2026-04-29 (3/3 videos generated and downloaded for berghain-berlin / the-nest / amnesia-ibiza); rubric ratings pending. Photos are uploaded but not forwarded to Seedance — see "Known limitations" below.

#### Known limitations of §9.6 (documented in SPEC §9.6 + AGENTS.md)

- **Real-person photos blocked at submit time.** Seedance 2.0, Veo 3.1, and Sora 2 all refuse `input_references` containing identifiable people via the `"InputImageSensitiveContentDetected.PrivacyInformation"` policy. Backend therefore sends only the venue image_url; the rendered DJ is a generic stand-in. The `identity_preservation` rubric dimension is N/A under this constraint and is scored as neutral `3` for comparability.
- **Data URL size limit.** OpenRouter video silently returns `id: null` for image payloads above ~2 MB. Eval auto-resizes photos to ≤1024 px JPEG via Pillow (`Pillow>=10` is in `requirements.txt`).
- [x] **Lyria 3 music previews** — `POST /api/ai/demo-music-preview` generates a ~30s instrumental clip per matched venue via OpenRouter (`google/lyria-3-clip-preview`; preview pricing currently $0/call, published ~$0.04/clip when GA). Streaming + `modalities:["text","audio"]` required.
- [x] **Personalized OpenRouter video** — `POST /api/ai/demo-performance-video` + polling endpoint generate a Seedance 2.0 reference-video conditioned on the matched venue's photo (default 720p/10s silent, `generate_audio: false`, ~$1.51 per clip, ~140 s wall-clock). The Lyria/fallback clip is synced in the browser and can be muxed into the final MP4 via ffmpeg. The shipped prompt is **Multi-Shot** (Establish → Develop → Payoff afterparty arc per Seedance 2.0 Handbook p.8).
  - **Venue image only** goes into `input_references`. Performer photos are accepted by the frontend for UX continuity but the backend does NOT forward them to Seedance — see the §9.6 Known Limitations below for the moderation policy that blocks real-person photos.
  - Currently uses the single `Venue.image_url` field. A multi-image upgrade (`Venue.image_urls: list[str]`, JSON-typed column matching the `genres` / `vibe_keywords` pattern, 2–3 photos per venue) is a natural follow-up.
- [x] **Video soundtrack mux** — `POST /api/ai/demo-performance-video/mux` combines a completed silent Seedance MP4 with the Lyria/fallback soundtrack via `ffmpeg`, returning `/assets/generated/...mp4`; `/personal-demo.html` still falls back to synced browser playback if `ffmpeg` is unavailable.
- [x] **SQLite + auto-seed** — 10 DJs / 7 venues / 3 bookings seeded on first run

---

## v1 — Remaining (Planned, Not Yet Built)

These are scoped for v1 but not yet in the product.

### n8n workflow automation

- [x] **Set up n8n** (n8n Cloud; Docker skipped)
- [x] **Booking confirmation workflow** → `n8n/workflows/booking_confirmation.json`
  - Webhook node receives booking payload from FastAPI
  - Email nodes send templated messages to DJ and venue with booking details
  - Acceptance: a real test booking triggers two emails
  - VERIFIED: workflow imported into n8n Cloud workspace `pabloplnz`, Gmail SMTP credential configured, activated, end-to-end test via curl with flat JSON payload triggered both emails successfully.
- [x] **Wire FastAPI → n8n**
  - In `backend/routers/bookings.py`, after a successful booking insert, POST the booking JSON to the n8n webhook URL
  - Webhook URL stored in `.env` as `N8N_BOOKING_WEBHOOK`
  - Handle webhook failure gracefully — booking should still succeed if n8n is down
  - VERIFIED: end-to-end test on 2026-04-28. POST to /api/bookings with dj_id=aelxis-vox, venue_id=amnesia-ibiza triggered n8n webhook successfully; both confirmation emails delivered to Gmail. Codex implementation in SESSION 11; manual verification in SESSION 12.
- [x] **Update SPEC §8 and README**: change n8n's tag from `[v1 — planned]` to `[v1 — LIVE]`
  - SPEC §8: n8n row tag updated from amber `[v1 — planned]` to green `[v1 — LIVE]`
  - README Key Features: removed the "v1 — Planned" subsection; added "Booking Confirmation Emails" to the v1 — Live list
  - README Tech Stack table: n8n Phase changed from `v1 — planned` to `**v1 — live**`

### Booking status workflow

- [x] **Add status field** to `bookings` table: `pending | confirmed | cancelled` (default `pending`)
  - Migration in `backend/database.py`
  - Column already existed; Codex confirmed in SESSION 14 and skipped re-adding it
- [x] **Add status-change endpoints**
  - `PATCH /api/bookings/{id}/confirm`
  - `PATCH /api/bookings/{id}/cancel`
  - Return updated booking object
  - Also added `GET /api/bookings/{id}` to support the UI fetch
- [x] **Surface status in the UI**
  - `booking.html` shows current status when `?id=<id>` is in the URL
  - Confirm/cancel buttons appear on existing-booking view; both visible to anyone (role gating deferred)
  - VERIFIED 2026-04-28: created booking id=8, PATCH /confirm flipped status to confirmed, UI displayed status correctly with Confirm disabled, Cancel button click flipped status to cancelled and the buttons disappeared. n8n booking-confirmation regression check passed (two emails delivered after the fresh POST).

### DJ availability — beyond static dates

- [x] **Calendar input UI** — DJ profile page lets dates be toggled as bookable/unbookable in the Booking Horizon calendar
- [ ] **Availability storage** — replace the seed's static availability strings with real date ranges
  - Current implementation keeps the existing JSON-as-TEXT exact-date list and adds a PATCH endpoint to update it; date-range semantics are still a follow-up.
- [x] **Match filter** — `vibe-match` honors availability when `event_date` is supplied in the request body

---

## Class Demo Stubs (Legacy / Canned)

These are canned preview endpoints and static assets that predate the live
Lyria + Seedance flow. They remain as fallbacks but are no longer the main
demo path.

- [x] **Canned music preview stub** - `POST /api/ai/music-preview` (returns the static `/assets/v2/music-preview.mp3`; superseded by `/api/ai/demo-music-preview` which calls Lyria 3 live)
- [x] **Canned party-simulation video stub** - `POST /api/ai/party-simulation-video` (returns a static MP4; superseded by `/api/ai/demo-performance-video`)
- [x] **ElevenLabs-style DJ voice intro stub** - `POST /api/ai/dj-voice-intro` (still canned; ElevenLabs remains v2 roadmap)

---
## v2 — Roadmap (Generative Media)

Documented in SPEC §8 with `[v2]` tags. Build only after v1 is complete.

### Music previews — DROPPED (Suno) / SHIPPED (Lyria 3)

- [~] **Suno API integration** — DROPPED. No official public Suno API; project
  chose Google Lyria 3 via OpenRouter for the single-key architecture instead.
- [x] **Live music endpoint** — `POST /api/ai/demo-music-preview` calls Lyria 3
  live and returns the generated clip (`google/lyria-3-clip-preview`).
- [x] **UI: preview player** on the personalized demo (`/personal-demo.html`)
  fires automatically when the user picks a venue match.
- [ ] **Caching** — Lyria clips are not cached; each match triggers a fresh
  generation (preview pricing currently $0; ~$0.04 per clip when GA). Add a
  `(venue_id, style_hash)`-keyed cache if cost or latency becomes an issue.

### OpenRouter Video — AI party simulation videos

- [x] **Choose provider** based on output quality + API access (see SPEC OQ-3)
  - Selected OpenRouter Video to keep AI generation behind the existing OpenRouter account/key.
- [x] **Video API integration** → `backend/services/openrouter_video_client.py` (silent — `generate_audio: false`)
- [x] **Endpoint** `POST /api/ai/demo-performance-video` — submits an async OpenRouter video job using selected venue context and the venue image reference; performer images are accepted by the UI but not forwarded under the current real-person image moderation constraint
- [x] **UI: video player** on `/personal-demo.html` (the personalized class demo). Standalone DJ-profile / match-preview integration on the main marketplace pages still pending.
- [x] **Async job pattern** — videos take ~140s to generate; return a job id and poll
  - `GET /api/ai/demo-performance-video/{job_id}` polls the OpenRouter video job and returns the completed video URL when ready.
- [x] **Mux generated audio into MP4** — `POST /api/ai/demo-performance-video/mux` uses `ffmpeg` to bake Lyria/fallback audio into the completed video file when available.

### ElevenLabs — voice synthesis

- [ ] **ElevenLabs API integration** → `backend/services/elevenlabs_client.py`
- [ ] **DJ intro generation** — endpoint that takes the AI-generated bio and produces a 15-second voice intro
- [ ] **Venue announcement narration** — endpoint that takes a venue tagline and produces narration
- [ ] **Voice-matching feature** — match a DJ's vocal style to the venue's brand tone (research first; defer if too vague)

### Auth (gates v2 monetization)

- [ ] **Choose auth approach** — JWT vs session vs Auth0 vs Clerk
- [ ] **DJ and Venue accounts** — sign-up, sign-in, password reset
- [ ] **Profile-edit gating** — only the owner can edit their profile
- [ ] **Tie inquiries / bookings to authenticated users**

---

## v3+ — Roadmap (Promo Engine, Bookings, Monetization)

Just bullets, not a checklist. Detailed design happens when we get there.

- **Promo engine**: automated promo content generation (videos, reels, social posts) per DJ × venue match, with brand-voice matching
- **In-platform bookings**: payment integration, escrow, calendar sync, contract generation
- **Reviews & ratings**: post-event feedback feeds back into the matching engine
- **DJ-derived style fingerprint**: analyze DJ mixes (Mixcloud / SoundCloud links) to infer style signals beyond self-reported tags
- **Event-specific search** (e.g., "DJ for New Year's Eve")
- **Multi-DJ agency support**: one account managing multiple DJ profiles
- **SaaS subscription tiers** — once we know who pays (DJ-side first, per SPEC OQ-1)

---

## How to Update This Plan

- Check boxes (`[ ]` → `[x]`) as you complete items.
- If you discover a sub-task, add it as a nested checkbox under its parent.
- If you change the plan structurally, note the reasoning in the session log under "Key Decisions."
- Do not delete completed items — they document what shipped.
- If a planned item is dropped, mark it `[~]` with a note instead of deleting it.
