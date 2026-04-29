# NOCTURNE — AI Evaluation

This directory holds the offline evaluation harness for the OpenRouter-routed
vibe matching engine. It implements the protocol defined in `SPEC.docx` Section 9.

> **Naming note:** the CSV columns and code variables are named `claude_*`
> (e.g. `claude_score`, `claude_reasoning`) for historical reasons — the
> matcher was originally Claude. As of SESSION 18 the runtime LLM is whatever
> `OPENROUTER_MODEL` is set to (default `openai/gpt-oss-120b:free`). The
> column names are kept for backward compatibility with existing CSVs.

## What it measures

| Metric | Definition | Target |
|---|---|---|
| **Match Precision** | Average human relevance rating (1–5) across all rated (venue, DJ) pairs | ≥ 4.0 / 5.0 |
| **Rank Accuracy** | Fraction of venues where the matcher's top-1 DJ is also the human's top pick | ≥ 70% |

## Running the eval

### Stage 1 — collect the matcher's predictions

```powershell
# Make sure the backend is running (window 1)
cd <project root>
.\.venv\Scripts\python.exe run.py
```

```powershell
# In a second window:
.\.venv\Scripts\python.exe evals\run_eval.py
```

This calls `/api/ai/vibe-match` once per venue (7 venues × top-3 = 21 pairs) and writes:

- `evals/results_full.csv` — every pair the matcher returned, with its score and reasoning
- `evals/rate_me.csv` — same pairs but with a blank `human_rating` column

### Stage 2 — rate the pairs (manual, ~30 min)

1. Open `evals/rate_me.csv` in Excel
2. **Hide the `claude_score` and `claude_reasoning` columns** in `results_full.csv` if you peek at it — to keep your ratings honest
3. For each row, look at `venue_name`, `dj_name`, and `dj_bio_short`, then put a number 1–5 in the `human_rating` column:
   - **1** — clear mismatch (wrong genre, wrong vibe, wrong scale)
   - **2** — weak fit
   - **3** — neutral, plausible
   - **4** — good fit
   - **5** — exceptional match
4. Save the file (keep CSV format)

### Stage 3 — compute metrics

```powershell
.\.venv\Scripts\python.exe evals\compute_metrics.py
```

Writes `evals/metrics.md` with both metric values, per-venue agreement table, and failure-mode candidates.

### Stage 4 — update the SPEC

Open `SPEC.docx` and update Section 9.3 with the actual numbers from `metrics.md`. This becomes Slide 5 of the class presentation.

## If a target is missed

- Inspect the failure-mode pairs in `metrics.md`
- Adjust the system prompt in `backend/services/vibe_matcher.py`
- Re-run from Stage 1 (use a different filename or commit between runs so you can compare)
- Document both runs in the SPEC §9.3 narrative

## Files (text-only matcher eval — SPEC §9.3)

| File | Purpose |
|---|---|
| `run_eval.py` | Stage 1: queries the matcher for each venue, writes the rate-me CSV |
| `compute_metrics.py` | Stage 3: reads the filled-in ratings, writes `metrics.md` |
| `results_full.csv` | (generated) matcher outputs — preserved for the metrics computation |
| `rate_me.csv` | (generated) blank rating sheet for the human rater |
| `metrics.md` | (generated) final report — the numbers that go into SPEC §9.3 |

---

# Audio-Driven Venue Match eval (SPEC §9.4)

A second eval that tests the **personalized demo** flow on
`POST /api/ai/demo-venue-match`. It answers: *does adding an audio clip on
top of the typed style improve the venue match?*

## Design

Paired comparison on the same 7 audio clips (one per seeded venue):

- **T (control):** matcher receives a neutral typed style only:
  *"experienced electronic music DJ, all-genre, open to any venue"*.
- **T+A (treatment):** matcher receives the same neutral style **plus** the
  uploaded audio clip. The backend's `audio_analyzer` (Gemini 2.5 Flash via
  OpenRouter) listens to the clip and returns a structured style read
  (genres, BPM, energy, mood, venue signals); the read is concatenated with
  the typed style and fed to the LLM venue matcher.

Same single-rater protocol as §9.3. Sample size is small (7 clips × 2
conditions × top-3 = 42 pairs); treat lift as a point estimate, not a
significance claim.

## Metrics

| Metric | Definition | Target |
|---|---|---|
| **Top-1 accuracy** | Fraction of clips where the matcher's #1 venue equals the source venue (the venue we sourced/created the clip "for"). Random baseline = 1/7 ≈ 14.3%. | T+A ≥ 70% |
| **Match Precision** | Average human rating (1–5) across the matcher's top-3 ranked venues, computed for each condition. | T+A ≥ 4.0/5.0 |
| **Lift** | (T+A) − (T) on each metric. The headline number for the demo deck. | Match-Precision lift ≥ 0.5 |

## Sourcing the audio clips

Drop **one ~30-second clip per venue** into `evals/audio_samples/`, named
`<venue_id>.mp3` (or `.wav`/`.m4a`/`.flac`/`.ogg`). The 7 venue IDs and the
sound profile each clip should target:

| `venue_id` | Venue (capacity, vibe) | Suggested track profile (one fit per clip) |
|---|---|---|
| `berghain-berlin` | BERGHAIN (1500, industrial / underground / legendary) | Dark techno, ~130–135 BPM, hypnotic, industrial textures |
| `the-nest` | THE NEST (300, intimate / underground / velvet) | Deep house or jazz-house, ~118–124 BPM, warm, low-key |
| `basement` | BASEMENT (600, industrial / raw / concrete) | Hard techno or industrial, ~135–145 BPM, raw, distorted |
| `the-archive-ibiza` | THE ARCHIVE (2000, immersive / cinematic / island) | Melodic / progressive techno, ~120–125 BPM, cinematic, euphoric |
| `fabric-london` | FABRIC LONDON (1600, underground / institution / bass) | Bass-driven UKG, garage, or DnB, sub-heavy |
| `amnesia-ibiza` | AMNESIA IBIZA (5000, massive / festival / ibiza) | Big-room festival house or main-stage techno, peak-time energy |
| `printworks` | PRINTWORKS (3000, warehouse / daylight / industrial) | Warehouse techno, ~130 BPM, anthemic, big-room industrial |

**Sources** (pick whichever is easiest):
- 30-second snippets from publicly available DJ mixes on SoundCloud /
  Mixcloud / YouTube (academic fair use is defensible for an evaluation
  exercise; do not redistribute).
- Pablo's own mixes/productions if any fit the profile.
- Lyria-generated clips as backup (cheap, reproducible, but somewhat
  circular: we'd be testing the matcher on audio that another
  OpenRouter model generated from a text prompt). If you go this route,
  document it in SPEC §9.4.

`evals/audio_samples/` is gitignored — the audio files don't ship with
the repo.

## Running the eval

```bash
# 1. Make sure the backend is running
python run.py

# 2. In a second window, with audio files in place:
python evals/audio_match_eval.py
```

Stage 1 writes:
- `evals/audio_results_full.csv` — every (clip, condition, rank) the
  matcher returned, with score and reasoning.
- `evals/audio_rate_me.csv` — same rows with a blank `human_rating`
  column. **Hide the matcher_score / matcher_reasoning columns** of
  `audio_results_full.csv` while you rate, so the score doesn't bias
  the rating.
- `evals/audio_analyses.json` — the structured Gemini reads for each
  clip (qualitative inspection).

Stage 2 — rate the pairs (~30 minutes, single-rater per the existing
protocol). For each row, listen to `audio_file` (in
`evals/audio_samples/`) and rate the (audio, matched_venue) fit 1–5:

- **1** — clear mismatch (wrong genre/vibe/scale)
- **3** — neutral, plausible
- **5** — exceptional fit

Stage 3 — compute metrics:

```bash
python evals/audio_compute_metrics.py
```

Writes `evals/audio_metrics.md` with the headline T-vs-T+A table,
per-clip top-1 picks, per-rank averages, and failure-mode candidates.
Paste the headline numbers into SPEC §9.4.

## Files (audio eval)

| File | Purpose |
|---|---|
| `audio_match_eval.py` | Stage 1: runs both conditions, writes the rate-me CSV |
| `audio_compute_metrics.py` | Stage 3: reads ratings, writes `audio_metrics.md` |
| `audio_samples/` | Your audio clips (gitignored) |
| `audio_results_full.csv` | (generated) all matcher outputs across both conditions |
| `audio_rate_me.csv` | (generated) blank rating sheet |
| `audio_analyses.json` | (generated) Gemini's structured reads per clip |
| `audio_metrics.md` | (generated) headline T vs T+A report |

---

# Seedance Prompt Structure eval (SPEC §9.5)

A deterministic, offline linter that verifies the rendered Seedance video
prompt continues to follow the official **Seedance 2.0 AI Handbook**. Costs
nothing (no API calls), runs in milliseconds, can be wired into CI later.

This is not a "did the video look good?" test — it's a regression guard for
the prompt structure itself. The motivation: an earlier free-prose prompt
hit several of the handbook's named anti-patterns (adjective soup, too many
camera moves, controlling everything equally). After restructuring per the
handbook's Single-Shot Skeleton, this eval makes sure a future agent doesn't
quietly revert it.

## What it checks per venue

For each seeded venue, the eval renders `build_seedance_prompt(...)` with
realistic stand-in inputs (performer = "Pablo", style = melodic techno, with
venue + 2 performer references) and runs 15 checks:

| Category | Check | Handbook reference |
|---|---|---|
| **Single-Shot Skeleton sections** (9 checks) | Format / Asset roles / Subject / Environment / Main action / Camera / Lighting / Sound / Style each present | p.7 |
| **Asset roles** | Uses R1/R2+ notation AND "Identity Sheet"/"Environment Sheet" terminology | p.5, p.11 |
| **Camera vocabulary** | At least one of: dolly, track, crane, pan, tilt, zoom, shallow focus, close-up, handheld, establishing shot | p.16 |
| **Lighting vocabulary** | At least one of: rim light, key light, fill light, backlight, soft/hard light, haze, golden hour, silhouette | p.16 |
| **Constraint vocabulary** | At least one of: avoid, maintain, preserve, limit, emphasize, exclude, frame, restrict, highlight | p.16 |
| **No banned anti-pattern phrases** | "premium editorial", "expressive crowd", "cinematic atmosphere" used as standalone style modifiers, etc. | p.14 |
| **One dominant camera move** | The Camera: section names ≤1 primary move verb (no "dolly + pan + zoom" stacks) | p.4 principle 2; p.14 anti-pattern |

## Running

```bash
# Default: pulls every seeded venue from the SQLite DB (auto-seeds if empty)
python evals/seedance_prompt_eval.py

# Or against canned stand-in venues (no DB required)
python evals/seedance_prompt_eval.py --no-db
```

Exits non-zero if any venue fails any check, so it can be wired into CI as
`python evals/seedance_prompt_eval.py --no-db` without external dependencies.

Writes a markdown report to `evals/seedance_prompt_metrics.md`.

## Files (Seedance prompt eval)

| File | Purpose |
|---|---|
| `seedance_prompt_eval.py` | The linter; renders prompts and runs the 15 checks per venue |
| `seedance_prompt_metrics.md` | (generated) per-venue + summary report |

---

# Seedance Video Output eval (SPEC §9.6)

The §9.5 linter validates the prompt **text**. This eval (§9.6) validates
the actual **video output** Seedance produces, by running real generations
against OpenRouter and scoring the resulting MP4s on a handbook-derived
rubric. The pair answers two related questions:

- §9.5: does the prompt follow the Seedance 2.0 AI Handbook's structure? (cheap, deterministic)
- §9.6: does that structure actually translate to good-looking video? (expensive, subjective)

## Design

For N chosen venues:
1. Submit one Seedance job per venue with: the venue's `image_url` as
   `input_references[0]` (Environment Sheet) and 1-3 of your performer
   photos as `input_references[1+]` (Identity Sheet).
2. Poll each job to completion (~140 s each).
3. Download the rendered MP4 to `evals/seedance_outputs/<venue_id>.mp4`.
4. Watch each clip and score it 1-5 on five handbook-aligned dimensions
   plus a yes/no constraints check.
5. Compute composite score + pass rate.

Single-rater protocol matching SPEC §9.3 / §9.4. N=3 venues fits inside a
$10 OpenRouter top-up; default is `--venues = first 3 seeded venues`.
Cost: N × ~$1.51 (Seedance 2.0 720p / 10 s).

## Rubric (handbook-aligned)

| Dimension | What you're rating (1-5) | Handbook reference |
|---|---|---|
| `identity_preservation` | Does the DJ in the video look like your performer photos? | p.9 — Image Reference role: "identity, wardrobe, palette" |
| `venue_fidelity` | Does the venue in the video match the seeded `image_url`? | p.5 principle 4 — "environment is active, not wallpaper" |
| `action_clarity` | Is there ONE clear, readable action throughout? | p.4 principle 1 — "one shot = one dominant readable action" |
| `camera_coherence` | Is the camera move coherent and singular (not erratic)? | p.4 principle 2 — "camera is not decoration" |
| `behavioral_realism` | Does the DJ's behavior look physically grounded (not AI-uncanny)? | p.4 principle 3 — "action must be physical" |
| `constraints_violated_yn` | Any text overlays, logos, captions, celebrity drift? | p.16 — constraint vocabulary; p.14 anti-pattern |

Targets:
- **Composite Score** (mean of the five 1-5 dimensions) ≥ 4.0 / 5.0
- **Pass Rate** (composite ≥ 4.0 AND constraints not violated) ≥ 70%

## Running

### Stage 1 — generate the videos

```bash
# Backend running (python run.py) and OPENROUTER_API_KEY funded.
# Drop performer photos somewhere on disk, then:
python evals/seedance_video_eval.py \
    --photos path/to/photo1.jpg path/to/photo2.jpg \
    --venues berghain-berlin the-nest amnesia-ibiza
```

The eval prints the cost estimate and asks for confirmation before
submitting jobs (use `--yes` to skip the prompt). Each job takes ~140 s
to render; the eval polls every 15 s up to 7.5 min per video.

### Stage 2 — rate the videos

Open `evals/seedance_video_rate_me.csv` in your spreadsheet tool. For
each row, watch the corresponding MP4 in `evals/seedance_outputs/` and
fill in the six rubric columns. Save the file as CSV.

### Stage 3 — compute metrics

```bash
python evals/seedance_video_compute_metrics.py
```

Writes `evals/seedance_video_metrics.md` with the headline composite +
pass-rate, per-dimension averages (each cross-referenced to the handbook
page), per-venue results, and failure-mode candidates. Paste the headline
into SPEC §9.6.

## Files (Seedance video eval)

| File | Purpose |
|---|---|
| `seedance_video_eval.py` | Stage 1 runner: submits + polls + downloads videos |
| `seedance_video_compute_metrics.py` | Stage 3 metrics (rubric → composite + pass rate) |
| `seedance_outputs/` | Rendered MP4s (gitignored — large files; .gitkeep ships) |
| `seedance_video_results_full.csv` | (generated) per-job submit/poll/download status + prompt + cost |
| `seedance_video_rate_me.csv` | (generated) blank rubric sheet |
| `seedance_video_metrics.md` | (generated) headline rubric report |
