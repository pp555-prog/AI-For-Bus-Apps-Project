"""
NOCTURNE AI Evaluation — Audio-Driven Match: compute paired metrics.

Reads:
    evals/audio_results_full.csv  — matcher outputs from audio_match_eval.py
    evals/audio_rate_me.csv       — human ratings (1-5) you filled in

Writes:
    evals/audio_metrics.md        — paired comparison report. Headline numbers
                                    go into SPEC.docx Section 9.4.

Metrics:
    - Top-1 accuracy: fraction of clips where the matcher's #1 venue == the
      audio's source venue (the venue we sourced the clip "for"). Random
      baseline = 1 / number_of_venues.
    - Match Precision: average human rating across the matcher's top-N
      ranked venues. Computed once for T (control) and once for T+A
      (treatment).
    - Lift: (T+A) - (T) on each metric. Point estimate, no significance
      test (N is small — this is a class-project eval).

Usage:
    .\\.venv\\Scripts\\python.exe evals\\audio_compute_metrics.py
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

EVALS_DIR = Path(__file__).resolve().parent
RESULTS_FULL = EVALS_DIR / "audio_results_full.csv"
RATE_ME = EVALS_DIR / "audio_rate_me.csv"
METRICS_MD = EVALS_DIR / "audio_metrics.md"

TARGET_MATCH_PRECISION = 4.0
TARGET_LIFT = 0.5  # T+A should beat T by at least 0.5 of a 1-5 point


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        print(f"ERROR: missing {path}")
        sys.exit(1)
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse_int(raw: str | None) -> int | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def main() -> None:
    full = load_rows(RESULTS_FULL)
    rated = load_rows(RATE_ME)

    full_by_id = {r["pair_id"]: r for r in full}

    human_ratings: dict[str, int] = {}
    for r in rated:
        v = parse_int(r.get("human_rating"))
        if v is None or v < 1 or v > 5:
            continue
        human_ratings[r["pair_id"]] = v

    if not human_ratings:
        print("ERROR: no valid 1-5 human ratings in audio_rate_me.csv.")
        sys.exit(1)

    print(f"Loaded {len(full)} matcher pairs; {len(human_ratings)} have human ratings.")

    # Group by condition
    by_condition: dict[str, list[dict]] = defaultdict(list)
    for r in full:
        by_condition[r["condition"]].append(r)

    # --- Top-1 accuracy per condition --------------------------------------
    # For each (condition, source_venue_id), check if the rank-1 row's
    # matched_venue_id == source_venue_id.
    top1_correct: dict[str, int] = {"T": 0, "T+A": 0}
    top1_total: dict[str, int] = {"T": 0, "T+A": 0}
    top1_table: list[dict] = []

    by_clip_condition: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in full:
        by_clip_condition[(r["source_venue_id"], r["condition"])].append(r)

    source_venues = sorted({r["source_venue_id"] for r in full})
    for sv in source_venues:
        row = {"source_venue_id": sv}
        for cond in ("T", "T+A"):
            picks = sorted(by_clip_condition.get((sv, cond), []), key=lambda x: int(x["rank"]))
            if not picks:
                row[f"{cond}_top1"] = ""
                row[f"{cond}_correct"] = ""
                continue
            top1_id = picks[0]["matched_venue_id"]
            row[f"{cond}_top1"] = top1_id
            correct = (top1_id == sv)
            row[f"{cond}_correct"] = "yes" if correct else "no"
            top1_total[cond] += 1
            if correct:
                top1_correct[cond] += 1
        top1_table.append(row)

    top1_acc = {
        c: (top1_correct[c] / top1_total[c]) if top1_total[c] else None
        for c in ("T", "T+A")
    }

    # --- Match Precision per condition -------------------------------------
    # Average human rating across all rated rows in that condition.
    precisions: dict[str, float | None] = {}
    rated_counts: dict[str, int] = {}
    for cond in ("T", "T+A"):
        ratings = [
            human_ratings[r["pair_id"]]
            for r in by_condition[cond]
            if r["pair_id"] in human_ratings
        ]
        rated_counts[cond] = len(ratings)
        precisions[cond] = mean(ratings) if ratings else None

    # --- Per-rank breakdown (T+A) ------------------------------------------
    rank_breakdown: list[dict] = []
    for rank in (1, 2, 3):
        row = {"rank": rank}
        for cond in ("T", "T+A"):
            ratings = [
                human_ratings[r["pair_id"]]
                for r in by_condition[cond]
                if int(r["rank"]) == rank and r["pair_id"] in human_ratings
            ]
            row[f"{cond}_n"] = len(ratings)
            row[f"{cond}_avg"] = round(mean(ratings), 2) if ratings else None
        rank_breakdown.append(row)

    # --- Lift --------------------------------------------------------------
    def lift(a: float | None, b: float | None) -> float | None:
        if a is None or b is None:
            return None
        return round(b - a, 3)

    precision_lift = lift(precisions["T"], precisions["T+A"])
    top1_lift = lift(top1_acc["T"], top1_acc["T+A"])

    # --- Failure-mode candidates -------------------------------------------
    low_rated = sorted(
        [(pid, r) for pid, r in human_ratings.items() if r <= 2],
        key=lambda x: x[1],
    )[:10]

    # --- Write report ------------------------------------------------------
    with open(METRICS_MD, "w", encoding="utf-8") as f:
        f.write("# NOCTURNE Audio-Driven Match Eval Results\n\n")
        f.write(f"- Audio clips evaluated: **{len(source_venues)}**\n")
        f.write(f"- Pairs collected: {len(full)} (T={top1_total['T']*3 if top1_total['T'] else 0}, T+A={top1_total['T+A']*3 if top1_total['T+A'] else 0} approx)\n")
        f.write(f"- Pairs rated: {len(human_ratings)} (T={rated_counts['T']}, T+A={rated_counts['T+A']})\n\n")

        f.write("## Headline\n\n")
        f.write("| Metric | T (typed style only) | T+A (style + audio) | Lift |\n")
        f.write("|---|---|---|---|\n")
        f.write(f"| Top-1 accuracy | {_fmt_pct(top1_acc['T'])} | {_fmt_pct(top1_acc['T+A'])} | {_fmt_pp(top1_lift)} |\n")
        f.write(f"| Match Precision (1-5) | {_fmt_num(precisions['T'])} | {_fmt_num(precisions['T+A'])} | {_fmt_num(precision_lift)} |\n")
        f.write(f"| Random top-1 baseline | {_fmt_pct(1 / max(len(source_venues),1))} | — | — |\n\n")

        f.write("**Targets**\n\n")
        f.write(f"- Match Precision (T+A) ≥ {TARGET_MATCH_PRECISION:.2f}/5.00\n")
        f.write(f"- Lift (T+A) - (T) ≥ {TARGET_LIFT:.2f} on Match Precision (audio adds signal)\n\n")

        f.write("## Per-clip top-1 picks\n\n")
        f.write("| Source venue | T top-1 | T correct | T+A top-1 | T+A correct |\n")
        f.write("|---|---|---|---|---|\n")
        for row in top1_table:
            f.write(f"| {row['source_venue_id']} | {row.get('T_top1','')} | {row.get('T_correct','')} | {row.get('T+A_top1','')} | {row.get('T+A_correct','')} |\n")
        f.write("\n")

        f.write("## Per-rank average human rating\n\n")
        f.write("| Rank | T n | T avg | T+A n | T+A avg |\n")
        f.write("|---|---|---|---|---|\n")
        for row in rank_breakdown:
            f.write(f"| {row['rank']} | {row['T_n']} | {_fmt_num(row['T_avg'])} | {row['T+A_n']} | {_fmt_num(row['T+A_avg'])} |\n")
        f.write("\n")

        f.write("## Failure-mode candidates (rated ≤ 2)\n\n")
        if low_rated:
            for pid, rating in low_rated:
                row = full_by_id.get(pid, {})
                f.write(f"- **pair {pid}** (rating {rating}, condition {row.get('condition')}): "
                        f"{row.get('source_venue_name')} → {row.get('matched_venue_name')} "
                        f"(rank {row.get('rank')}, score {row.get('matcher_score')}). "
                        f"Reasoning: {row.get('matcher_reasoning','')[:200]}\n")
        else:
            f.write("- None — no pairs were rated ≤ 2.\n")
        f.write("\n## Notes\n\n")
        f.write("- Run from: evals/audio_match_eval.py + evals/audio_compute_metrics.py\n")
        f.write("- Protocol: `evals/README.md` (audio-match section)\n")
        f.write("- Results section: SPEC.docx §9.4\n")
        f.write("- Sample size is small (one clip per venue, two conditions). Treat lift\n")
        f.write("  as a point estimate; do not claim statistical significance.\n")

    # --- Console summary ---------------------------------------------------
    print(f"\n=== Top-1 accuracy ===")
    print(f"  T:    {_fmt_pct(top1_acc['T'])}")
    print(f"  T+A:  {_fmt_pct(top1_acc['T+A'])}")
    print(f"  Lift: {_fmt_pp(top1_lift)}")
    print(f"\n=== Match Precision (1-5) ===")
    print(f"  T:    {_fmt_num(precisions['T'])}")
    print(f"  T+A:  {_fmt_num(precisions['T+A'])}")
    print(f"  Lift: {_fmt_num(precision_lift)}")
    print(f"\nReport written to {METRICS_MD}")


def _fmt_num(v: float | None) -> str:
    return f"{v:.2f}" if v is not None else "—"


def _fmt_pct(v: float | None) -> str:
    return f"{v*100:.1f}%" if v is not None else "—"


def _fmt_pp(v: float | None) -> str:
    return f"{v*100:+.1f} pp" if v is not None else "—"


if __name__ == "__main__":
    main()
