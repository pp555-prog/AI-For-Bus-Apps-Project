# NOCTURNE — AI Evaluation

This directory holds the offline evaluation harness for the Claude-powered vibe matching engine. It implements the protocol defined in `SPEC.docx` Section 9.

## What it measures

| Metric | Definition | Target |
|---|---|---|
| **Match Precision** | Average human relevance rating (1–5) across all rated (venue, DJ) pairs | ≥ 4.0 / 5.0 |
| **Rank Accuracy** | Fraction of venues where Claude's top-1 DJ is also the human's top pick | ≥ 70% |

## Running the eval

### Stage 1 — collect Claude's predictions

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

- `evals/results_full.csv` — every pair Claude returned, with its score and reasoning
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

## Files

| File | Purpose |
|---|---|
| `run_eval.py` | Stage 1: queries Claude for each venue, writes the rate-me CSV |
| `compute_metrics.py` | Stage 3: reads the filled-in ratings, writes `metrics.md` |
| `results_full.csv` | (generated) Claude's outputs — preserved for the metrics computation |
| `rate_me.csv` | (generated) blank rating sheet for the human rater |
| `metrics.md` | (generated) final report — the numbers that go into SPEC §9.3 |
