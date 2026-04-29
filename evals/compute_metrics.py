"""
NOCTURNE AI Evaluation — Stage 2: compute Match Precision and Rank Accuracy
from the human ratings in rate_me.csv.

Usage:
    .\\.venv\\Scripts\\python.exe evals\\compute_metrics.py

Inputs:
    evals/rate_me.csv       — human ratings (1-5) you filled in
    evals/results_full.csv  — Claude's scores and ranks (from run_eval.py)

Outputs:
    evals/metrics.md        — final report. Paste these numbers into
                              SPEC.docx Section 9.3.
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

EVALS_DIR = Path(__file__).resolve().parent
RESULTS_FULL = EVALS_DIR / "results_full.csv"
RATE_ME = EVALS_DIR / "rate_me.csv"
METRICS_MD = EVALS_DIR / "metrics.md"

TARGET_MATCH_PRECISION = 4.0   # average human rating, 1-5
TARGET_RANK_ACCURACY = 0.70    # fraction of venues where Claude's top-1 = human's top-1


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        print(f"ERROR: missing {path}")
        sys.exit(1)
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    full = load_rows(RESULTS_FULL)
    rated = load_rows(RATE_ME)

    # Index full results by pair_id
    full_by_id = {r["pair_id"]: r for r in full}

    # Parse ratings
    human_ratings: dict[str, int] = {}  # pair_id -> rating
    skipped = 0
    for r in rated:
        pid = r["pair_id"]
        raw = (r.get("human_rating") or "").strip()
        if not raw:
            skipped += 1
            continue
        try:
            v = int(raw)
        except ValueError:
            print(f"WARNING: pair {pid} has non-integer rating '{raw}', skipping")
            skipped += 1
            continue
        if v < 1 or v > 5:
            print(f"WARNING: pair {pid} rating {v} outside 1-5, skipping")
            skipped += 1
            continue
        human_ratings[pid] = v

    if not human_ratings:
        print("ERROR: no valid human ratings found in rate_me.csv.")
        print("Open the file, fill in the human_rating column with values 1-5, save, and re-run.")
        sys.exit(1)

    rated_count = len(human_ratings)
    total_count = len(full)
    print(f"Rated {rated_count}/{total_count} pairs (skipped {skipped}).")

    # Match Precision = average human rating across all rated pairs
    match_precision = mean(human_ratings.values())

    # Rank Accuracy = for each venue, did the human's top-rated DJ from the
    # top-3 set match Claude's rank-1 DJ? Computed across venues that have
    # ratings for all of their top-3.
    venue_ranks: dict[str, list[tuple[int, str, int]]] = defaultdict(list)
    # venue_id -> list of (claude_rank, dj_id, human_rating)
    for pid, rating in human_ratings.items():
        f = full_by_id.get(pid)
        if not f:
            continue
        venue_ranks[f["venue_id"]].append((int(f["claude_rank"]), f["dj_id"], rating))

    venue_agreements: list[bool] = []
    venue_results: list[dict] = []
    for venue_id, rows in venue_ranks.items():
        if len(rows) < 2:
            # Need at least 2 to compare; skip venues with too few ratings
            continue
        # Claude's top-1 dj_id
        claude_top = next((dj for r, dj, _ in rows if r == 1), None)
        # Human's top dj_id (highest human rating; ties broken by Claude's rank order)
        rows_sorted = sorted(rows, key=lambda x: (-x[2], x[0]))
        human_top = rows_sorted[0][1]
        agreement = (claude_top == human_top)
        venue_agreements.append(agreement)
        venue_results.append({
            "venue_id": venue_id,
            "claude_top": claude_top,
            "human_top": human_top,
            "agreement": agreement,
        })

    if not venue_agreements:
        rank_accuracy = None
    else:
        rank_accuracy = sum(1 for a in venue_agreements if a) / len(venue_agreements)

    # Failure-mode notes — list the lowest-rated pairs
    low_rated = sorted(
        [(pid, r) for pid, r in human_ratings.items() if r <= 2],
        key=lambda x: x[1]
    )[:5]

    # Write report
    with open(METRICS_MD, "w", encoding="utf-8") as f:
        f.write("# NOCTURNE Eval Results\n\n")
        f.write(f"- Pairs rated: **{rated_count}** of {total_count}\n")
        f.write(f"- Venues with comparable rankings: **{len(venue_agreements)}**\n\n")
        f.write("## Match Precision\n\n")
        f.write(f"- Score: **{match_precision:.2f} / 5.00**\n")
        f.write(f"- Target: ≥ {TARGET_MATCH_PRECISION:.2f}\n")
        f.write(f"- Result: {'✅ PASS' if match_precision >= TARGET_MATCH_PRECISION else '❌ MISS'}\n\n")
        f.write("## Rank Accuracy\n\n")
        if rank_accuracy is None:
            f.write("- Score: insufficient data (need ratings for >=2 DJs per venue)\n\n")
        else:
            f.write(f"- Score: **{rank_accuracy*100:.1f}%** ({sum(venue_agreements)} of {len(venue_agreements)} venues)\n")
            f.write(f"- Target: ≥ {TARGET_RANK_ACCURACY*100:.0f}%\n")
            f.write(f"- Result: {'✅ PASS' if rank_accuracy >= TARGET_RANK_ACCURACY else '❌ MISS'}\n\n")
        f.write("## Per-venue agreement\n\n")
        f.write("| Venue | Claude top-1 | Human top-1 | Agreement |\n")
        f.write("|---|---|---|---|\n")
        for vr in venue_results:
            f.write(f"| {vr['venue_id']} | {vr['claude_top']} | {vr['human_top']} | {'✅' if vr['agreement'] else '❌'} |\n")
        f.write("\n## Failure-mode candidates (rated ≤ 2)\n\n")
        if low_rated:
            for pid, rating in low_rated:
                row = full_by_id.get(pid, {})
                f.write(f"- **pair {pid}** (rating {rating}): {row.get('venue_name')} → {row.get('dj_name')} "
                        f"(Claude score {row.get('claude_score')}). Reasoning: {row.get('claude_reasoning', '')[:200]}\n")
        else:
            f.write("- None — no pairs were rated 2 or below.\n")
        f.write("\n## Notes\n\n")
        f.write("- Run from: evals/run_eval.py + evals/compute_metrics.py\n")
        f.write("- See SPEC.docx Section 9 for the eval plan and target rationale.\n")

    print(f"\n=== Match Precision: {match_precision:.2f} / 5.00 (target >= {TARGET_MATCH_PRECISION:.2f})")
    if rank_accuracy is not None:
        print(f"=== Rank Accuracy:   {rank_accuracy*100:.1f}% (target >= {TARGET_RANK_ACCURACY*100:.0f}%)")
    print(f"\nReport written to {METRICS_MD}")
    print(f"Open it, copy the numbers into SPEC.docx Section 9.3.")


if __name__ == "__main__":
    main()
