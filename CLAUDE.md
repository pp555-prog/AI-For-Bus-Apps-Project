# Claude Instructions

**Read [`AGENTS.md`](./AGENTS.md) first.** It is the canonical onboarding document for this project and applies to all AI agents, including Claude.

This file exists only to ensure Claude Code (which auto-loads `CLAUDE.md` at session start) reaches `AGENTS.md`.

## Claude-Specific Notes

- **Session log:** the canonical session log is `Review at the start of each session and update at the end of each session.txt` in the project root. Read it before doing any work; append a new `SESSION N` block at the end of every session.
- **Worktrees:** when working in a `.claude/worktrees/*` checkout, treat the file in the **main project root** as the source of truth for `SPEC.docx`, `README.md`, `AGENTS.md`, `CLAUDE.md`, and the session log. Always copy edits back to the main project root before finishing — Word and other tools open the main copy, not the worktree.
- **LLM provider:** as of SESSION 18, the runtime LLM is routed through OpenRouter (OpenAI SDK pointed at `https://openrouter.ai/api/v1`). The active model is set by `OPENROUTER_MODEL` in `.env` (default `openai/gpt-oss-120b:free`). Don't reintroduce the `anthropic` SDK or hard-code Claude — use `from backend.services.llm_client import complete` and let `OPENROUTER_MODEL` decide.

- **Personalized class demo:** as of SESSION 22, `/personal-demo.html` is the main demo path for uploading Pablo's performer photos, matching him to a venue, and submitting/polling an OpenRouter video job. Default video model is `bytedance/seedance-2.0` via `backend/services/openrouter_video_client.py`. Do not reintroduce fal.ai or Higgsfield as the live video provider unless the user explicitly asks.
- **Live music generation:** the demo also fires a Google Lyria 3 clip per matched venue via `backend/services/lyria_client.py` (`google/lyria-3-clip-preview`, ~$0.04 per clip, routed through the same OpenRouter key). Don't reintroduce Suno as a runtime provider — there is no official Suno public API and the project explicitly chose Lyria for the single-key OpenRouter architecture.
- **Audio-input style analysis:** when a user uploads a track on `/personal-demo.html`, the frontend trims it client-side to 30s mono 16 kHz WAV and posts it to `/api/ai/demo-venue-match`. The backend runs `backend/services/audio_analyzer.py` (default `google/gemini-2.5-flash` via OpenRouter chat-completions with `input_audio` content blocks). The structured analysis is concatenated with the user's typed style and fed to the LLM venue matcher (`vibe_matcher.match_venues`). Don't add a server-side audio decoder — keep the trim on the frontend so we don't pull in pydub/ffmpeg.
