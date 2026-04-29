# Agent Onboarding — NOCTURNE

**Read this file first. Then read the session log. Then start work.**

This file is the canonical onboarding document for any AI agent (Claude, Codex, Cursor, Copilot, or other) working on this project. The Claude-specific file `CLAUDE.md` defers to this one.

---

## 1. The Single Most Important Rule

Before doing **any** work on this project, read:

```
Review at the start of each session and update at the end of each session.txt
```

That file lives **only at the main project root** (not in worktrees — Windows path-length limits prevent duplicating it there). It is the running session log — every prior session's decisions, files changed, and "what comes next" notes are there. **Read it first** to avoid duplicating, undoing, or contradicting prior work. If you are working in a worktree, the session log is at `../../../Review at the start of each session and update at the end of each session.txt` relative to the worktree root.

After the session log, read [`TASKS.md`](./TASKS.md) — the canonical task checklist for the product. Pick an unchecked item, do it, check the box, append to the session log.

At the **end of every session**, append a new `SESSION N` block to the same file documenting:
- Date and agent identity (e.g. "Claude Sonnet 4.6", "GPT-5 via Codex")
- What was done (numbered list)
- Files changed
- Key decisions and their rationale
- What comes next

---

## 2. What This Project Is

**NOCTURNE** is a DJ-Venue marketplace built as a class project for **NBA 6925: Advanced AI for Business Applications** at Cornell University. It uses AI to match DJs with venues based on style, vibe, budget, and location, and to generate content (bios, promo prompts, party simulations).

The defining product question: *can AI make the DJ-venue match tangible before money changes hands?*

The full Product Requirements Document is in `SPEC.docx`. **Read SPEC.docx Section 9 before touching any AI feature** — it defines the evaluation plan and target metrics.

---

## 3. Architecture in 30 Seconds

```text
ui/  (static HTML + Tailwind, Stitch-generated)
  - fetches API via script tags

backend/ (FastAPI + aiosqlite + SQLite)
  - routers/   - REST endpoints (djs, venues, bookings, ai, radar)
  - services/  - LLM client (OpenRouter), vibe matcher, OpenRouter video client, Lyria music client
  - seed.py    - auto-seeds 10 DJs / 7 venues / 3 bookings on first run
  - main.py    - mounts routers + static UI

External AI (all routed through the single OpenRouter key):
  - OpenRouter LLM   (v1, LIVE)    - vibe matching, bio gen, promo prompts, party-sim text, venue match reasoning
  - OpenRouter Audio (v1, LIVE)    - audio-input style analysis for the personalized demo; default google/gemini-2.5-flash
  - OpenRouter Video (v1, LIVE)    - personalized async video generation; default bytedance/seedance-2.0
  - OpenRouter Lyria (v1, LIVE)    - 30s instrumental music clips; default google/lyria-3-clip-preview
  - n8n              (v1, LIVE)    - booking confirmation emails on every booking
  - OpenAI Codex     (dev tool)    - used to write code; not a runtime feature
  - ElevenLabs       (v2 roadmap)  - voice synthesis
```


**LIVE = working today and demoable.** OpenRouter-routed LLM, OpenRouter video (Seedance 2.0), OpenRouter Lyria 3 music, and the n8n booking confirmation workflow. All AI generation flows through one OpenRouter API key.
**Planned = scoped for v1 but not yet built.** Booking status workflow, real DJ availability calendar.
**Dev tool = used during development, not part of the deployed product.** Codex falls here.
**Class demo flow** uses `/personal-demo.html`. `POST /api/ai/demo-venue-match` accepts performer name, typed style, photos, and an optional audio clip; the frontend client-side-trims the audio to 30s mono 16 kHz WAV before posting. The backend runs `audio_analyzer.analyze` (Gemini via OpenRouter) for the structured style read, augments the typed style, and calls `vibe_matcher.match_venues` (LLM-powered) for the ranked venues with reasoning. Match selection then fires `POST /api/ai/demo-music-preview` (Lyria) and `POST /api/ai/demo-performance-video` + `GET /api/ai/demo-performance-video/{job_id}` (Seedance) in parallel. The video call passes the matched **venue's photo** as the first `input_reference` and the **performer's photos** as the subsequent ones, so Seedance anchors the rendered scene on the actual room AND the actual person, not a generic club.
**v2 = roadmap, not yet production-complete.** Do not market ElevenLabs/full media workflows as live in user-facing copy.

---

## 4. Key Files

| File | What it is | When to touch |
|------|-----------|---------------|
| `Review at the start of each session and update at the end of each session.txt` | Session log | Read at start, append at end of every session |
| `TASKS.md` | Product task checklist | Read after session log; check off items as you complete them |
| `SPEC.docx` | Product Requirements Document | When scope, features, or eval plan change |
| `README.md` | User-facing project intro | When public-facing description changes |
| `AGENTS.md` (this file) | Universal agent onboarding | Rarely; only when onboarding rules change |
| `CLAUDE.md` | Claude-specific notes (defers to AGENTS.md) | Rarely |
| `backend/routers/ai.py` | LLM-powered endpoints (vibe-match, bio, promo, party-sim) plus the personalized demo endpoints (`demo-venue-match`, `demo-music-preview`, `demo-performance-video` + polling) | When adding/changing AI features |
| `backend/services/llm_client.py` | LLM wrapper — OpenAI SDK pointed at OpenRouter | When changing model selection or retry logic |
| `backend/services/openrouter_video_client.py` | OpenRouter async video client (Seedance 2.0 default) | When changing video model or async polling |
| `backend/services/lyria_client.py` | OpenRouter Lyria 3 music client | When changing music model or response parsing |
| `backend/services/audio_analyzer.py` | OpenRouter audio-input client; sends uploaded clips to Gemini for structured style analysis | When changing the audio model or output schema |
| `backend/services/vibe_matcher.py` | Core matching engine | When changing the match algorithm or prompt |
| `backend/seed.py` | Sample data generator | When test data needs to change |
| `evals/run_eval.py` + `compute_metrics.py` | DJ-match eval harness (SPEC §9.3) | When prompt/scoring changes warrant a re-run |
| `evals/audio_match_eval.py` + `audio_compute_metrics.py` | Audio-driven match eval (SPEC §9.4) — paired T vs T+A on `/api/ai/demo-venue-match` with one audio clip per seeded venue | When the audio analyzer or venue matcher changes; results go in SPEC §9.4 |
| `evals/seedance_prompt_eval.py` | Seedance prompt-structure linter (SPEC §9.5) — verifies the rendered video prompt follows the Seedance 2.0 AI Handbook; deterministic, $0 to run | Whenever `backend/services/seedance_prompt.py` changes; can run in CI |
| `evals/seedance_video_eval.py` + `seedance_video_compute_metrics.py` | Seedance video output eval (SPEC §9.6) — generates real videos with uploaded performer photos and scores them on a handbook-aligned rubric | When evaluating actual video quality; costs ~$1.51 per venue tested |
| `backend/services/seedance_prompt.py` | Seedance video prompt builder; structured per the official Seedance 2.0 AI Handbook (Single-Shot Skeleton + asset roles + concrete vocabulary) | When the prompt structure or handbook citations change |
| `init.sh` | First-time setup script | Rarely |
| `run.py` | Launches uvicorn on port 8000 | Rarely |

---

## 5. Running the Project

```bash
bash init.sh        # first-time: creates .venv, installs deps, copies .env
python run.py       # starts the server at http://localhost:8000
```

`OPENROUTER_API_KEY` must be set in `.env` for any AI endpoint to work. Without it, profile and booking pages still function but AI endpoints raise. Default model is `openai/gpt-oss-120b:free` — change via `OPENROUTER_MODEL`. Browse free models at https://openrouter.ai/models?max_price=0.

API docs auto-generated at `http://localhost:8000/docs`.

---

## 6. Course Context (Why This Matters)

This is graded against a rubric (see `NBA_6925_4920_S26_Project_Presentation.pdf`):

- **AI fit + data feasibility (10 pts)** — the problem must be a genuine AI fit, not solvable by ChatGPT alone
- **Evaluation plan + preliminary results (7.5 pts)** — see SPEC Section 9
- **Live demo (10 pts)** — the AI features must work end-to-end
- **User study insights (2.5 pts)** — at least one external user must try the MVP
- **MVP submission (2.5 pts)** — already complete

**Implication for agents:** any change that breaks the live AI demo or undermines the eval plan is a regression, not a refactor. Verify the demo path (`/api/ai/vibe-match`) still works after non-trivial backend changes.

---

## 7. Conventions

- **No new dependencies** without recording the why in the session log.
- **Don't deploy production patterns** (auth, payments, escrow) — explicitly out of MVP scope.
- **SQLite, no ORM** — `aiosqlite` queries are written by hand in `database.py`. Match the existing style.
- **JSON-typed columns** (genres, vibe_keywords, tech_rider, availability) are stored as TEXT and parsed by Pydantic `@field_validator` on read. Don't normalize them into separate tables.
- **Static UI mount comes after API routers** in `main.py`, so `/api/*` always wins.
- **The personalized class demo (`/personal-demo.html`) is the canonical demo path** — venue match → Lyria 3 music clip → Seedance 2.0 video. All three calls share one OpenRouter API key. Don't reintroduce Suno, fal.ai, or Higgsfield as runtime providers.
- **Video generation costs real money** — Seedance 2.0 720p/10s ≈ $1.51/clip and ~140 s wall-clock per call. Lyria 3 is currently in preview and OpenRouter has been billing $0/call (published price ~$0.04/clip when GA). Don't fire Seedance against a live API in code paths that aren't user-triggered.
- **Seedance is generated silent** — `openrouter_video_client.py` sends `generate_audio: false`. ByteDance's safety filter rejects jobs with audio enabled (~$1.50 wasted, ~2 min lost on stage). Lyria supplies the soundtrack alongside the silent video.
- **The Seedance prompt is structured per the official handbook** — `_build_seedance_prompt()` in `backend/routers/ai.py` follows the Single-Shot Skeleton (Subject / Environment / Main action / Camera / Lighting / Style / Audio) from the Seedance 2.0 AI Handbook (page 7), with explicit Asset Roles (page 5) and Constraints vocabulary (page 16). Don't rewrite this back into free prose — the handbook's anti-patterns (adjective soup, too many camera moves, unassigned references, controlling everything equally) actively degrade Seedance output.
- **Lyria requires streaming + modalities** — to receive audio (not just a `<instrumental>Caption: ...` text), the request must include `modalities: ["text","audio"]` and `stream: true`. Audio comes as one large `delta.audio.data` SSE chunk; parse via `aiter_bytes()` and split on `\n\n`, not `aiter_lines()`.

---

## 8. Where to Get Stuck Less

If something feels missing or contradictory, it probably is. Check the session log for prior context before assuming the codebase is wrong. If the session log doesn't explain it, ask the user — don't guess.
