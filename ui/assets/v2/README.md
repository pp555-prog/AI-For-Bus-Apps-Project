# NOCTURNE Fallback Demo Assets

These files are canned fallback placeholders served statically by FastAPI
(`backend/main.py` mounts `ui/` at the site root). They are returned by the
legacy stub endpoints when the live OpenRouter integrations cannot run (e.g.
no `OPENROUTER_API_KEY` configured).

- `music-preview.mp3` -> fallback for `/api/ai/music-preview`. The live demo
  path is `/api/ai/demo-music-preview` which calls Lyria 3 via OpenRouter.
- `party-simulation.mp4` -> fallback for `/api/ai/party-simulation-video` and
  for `/api/ai/demo-performance-video` when no API key is set. The live demo
  path uses Seedance 2.0 via OpenRouter.
- `dj-voice-intro.mp3` -> fallback for `/api/ai/dj-voice-intro`. ElevenLabs
  voice synthesis remains a v2 roadmap item.

Keep the filenames unchanged unless you also update the stub endpoints in
`backend/routers/ai.py`.
