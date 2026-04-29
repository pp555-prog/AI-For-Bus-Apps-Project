"""
NOCTURNE AI Evaluation — Seedance Video Output: compute rubric metrics.

Reads:
    evals/seedance_video_results_full.csv  — submit/poll/download outcomes from
                                              seedance_video_eval.py
    evals/seedance_video_rate_me.csv       — human ratings (1-5 + yes/no)

Writes:
    evals/seedance_video_metrics.md        — handbook-aligned rubric report.
                                              Headline numbers go into SPEC §9.6.

Metrics:
    - Per-dimension average (1-5) across all rated videos.
    - Composite score = mean of the five 1-5 dimensions.
    - Pass rate = fraction of videos with composite >= 4.0 AND constraints
      not violated (the constraints_violated_yn column == "no").
    - Per-venue breakdown (each video's composite + pass/fail).
    - Failure-mode candidates (videos with composite < 3.0 or constraints
      violated).

Targets (mirroring SPEC §9.3 thresholds where applicable):
    - Composite Score >= 4.0 / 5.0 average across all rated videos.
    - Pass Rate >= 70%.

Usage:
    python evals/seedance_video_compute_metrics.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path
from statistics import mean

EVALS_DIR = Path(__file__).resolve().parent
RESULTS_FULL = EVALS_DIR / "seedance_video_results_full.csv"
RATE_ME = EVALS_DIR / "seedance_video_rate_me.csv"
METRICS_MD = EVALS_DIR / "seedance_video_metrics.md"

DIMENSIONS = [
    "identity_preservation",
    "venue_fidelity",
    "action_clarity",
    "camera_coherence",
    "behavioral_realism",
]

TARGET_COMPOSITE = 4.0
TARGET_PASS_RATE = 0.70


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        print(f"ERROR: missing {path}", file=sys.stderr)
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
        v = int(s)
    except ValueError:
        return None
    return v if 1 <= v <= 5 else None


def parse_yesno(raw: str | None) -> bool | None:
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if s in ("yes", "y", "true", "1"):
        return True
    if s in ("no", "n", "false", "0"):
        return False
    return None


def main() -> int:
    full = load_rows(RESULTS_FULL)
    rated = load_rows(RATE_ME)

    full_by_id = {r["pair_id"]: r for r in full}

    # Build per-video rating dicts, keyed by pair_id
    per_video: list[dict] = []
    for r in rated:
        pid = r["pair_id"]
        scores = {dim: parse_int(r.get(dim)) for dim in DIMENSIONS}
        violated = parse_yesno(r.get("constraints_violated_yn"))
        full_row = full_by_id.get(pid, {})
        per_video.append({
            "pair_id": pid,
            "venue_id": r.get("venue_id") or full_row.get("venue_id", ""),
            "venue_name": r.get("venue_name") or full_row.get("venue_name", ""),
            "video_file": r.get("video_file", ""),
            "scores": scores,
            "constraints_violated": violated,
        })

    # Filter to videos with all five dimensions rated
    complete = [v for v in per_video if all(v["scores"][d] is not None for d in DIMENSIONS)]
    incomplete = [v for v in per_video if v not in complete]

    if not complete:
        print("ERROR: no videos have all five rubric dimensions filled in.", file=sys.stderr)
        print(f"Open {RATE_ME} and rate each row 1-5.", file=sys.stderr)
        return 1

    # Compute composites
    for v in complete:
        v["composite"] = round(mean(v["scores"][d] for d in DIMENSIONS), 2)
        v["passed"] = (v["composite"] >= TARGET_COMPOSITE) and (v["constraints_violated"] is False)

    # Aggregate
    per_dim_avg = {d: round(mean(v["scores"][d] for v in complete), 2) for d in DIMENSIONS}
    composite_avg = round(mean(v["composite"] for v in complete), 2)
    pass_count = sum(1 for v in complete if v["passed"])
    pass_rate = pass_count / len(complete)
    constraint_violations = sum(1 for v in complete if v["constraints_violated"])

    # Failure-mode candidates: composite < 3.0 OR constraints violated
    low_composite = sorted(
        (v for v in complete if v["composite"] < 3.0 or v["constraints_violated"]),
        key=lambda v: (v["constraints_violated"] is False, v["composite"]),
    )

    # Write report
    with open(METRICS_MD, "w", encoding="utf-8") as f:
        f.write("# NOCTURNE Seedance Video Output Eval Results\n\n")
        f.write(f"- Videos rated: **{len(complete)}**")
        if incomplete:
            f.write(f" (skipping {len(incomplete)} with incomplete ratings)")
        f.write("\n\n")

        f.write("## Headline\n\n")
        f.write("| Metric | Score | Target | Result |\n")
        f.write("|---|---|---|---|\n")
        f.write(f"| Composite Score (1-5) | **{composite_avg:.2f}** | ≥ {TARGET_COMPOSITE:.2f} | "
                f"{'✅ PASS' if composite_avg >= TARGET_COMPOSITE else '❌ MISS'} |\n")
        f.write(f"| Pass Rate | **{pass_rate*100:.1f}%** ({pass_count}/{len(complete)}) | "
                f"≥ {TARGET_PASS_RATE*100:.0f}% | "
                f"{'✅ PASS' if pass_rate >= TARGET_PASS_RATE else '❌ MISS'} |\n")
        f.write(f"| Constraint Violations | {constraint_violations}/{len(complete)} | 0 | "
                f"{'✅ PASS' if constraint_violations == 0 else '❌ MISS'} |\n\n")

        f.write("## Per-dimension averages (handbook-aligned)\n\n")
        f.write("| Dimension | Average (1-5) | Handbook reference |\n")
        f.write("|---|---|---|\n")
        f.write(f"| identity_preservation | {per_dim_avg['identity_preservation']:.2f} | p.9 Image Reference (identity) |\n")
        f.write(f"| venue_fidelity | {per_dim_avg['venue_fidelity']:.2f} | p.5 principle 4 (environment is active) |\n")
        f.write(f"| action_clarity | {per_dim_avg['action_clarity']:.2f} | p.4 principle 1 (one dominant readable action) |\n")
        f.write(f"| camera_coherence | {per_dim_avg['camera_coherence']:.2f} | p.4 principle 2 (camera serves story) |\n")
        f.write(f"| behavioral_realism | {per_dim_avg['behavioral_realism']:.2f} | p.4 principle 3 (action must be physical) |\n\n")

        f.write("## Per-venue results\n\n")
        f.write("| Venue | Composite | Constraints | Pass | Notes |\n")
        f.write("|---|---|---|---|---|\n")
        for v in complete:
            score_breakdown = " / ".join(f"{v['scores'][d]}" for d in DIMENSIONS)
            badge = "✅" if v["passed"] else "❌"
            cv = "violated" if v["constraints_violated"] else "ok"
            f.write(f"| {v['venue_name']} ({v['venue_id']}) | **{v['composite']:.2f}** ({score_breakdown}) | {cv} | {badge} | |\n")
        f.write("\n*Composite breakdown order: identity / venue / action / camera / realism*\n\n")

        f.write("## Failure-mode candidates (composite < 3.0 OR constraints violated)\n\n")
        if low_composite:
            for v in low_composite:
                f.write(f"- **{v['venue_name']}** (composite {v['composite']:.2f}, "
                        f"constraints {'violated' if v['constraints_violated'] else 'ok'}) — "
                        f"video: `{v['video_file']}`\n")
        else:
            f.write("- None — every rated video scored ≥ 3.0 with constraints intact.\n")
        f.write("\n## Notes\n\n")
        f.write("- Run from: evals/seedance_video_eval.py + evals/seedance_video_compute_metrics.py\n")
        f.write("- Protocol: evals/README.md (Seedance Video Output eval section)\n")
        f.write("- Handbook citations on the per-dimension table map each rubric item back to\n")
        f.write("  a Seedance 2.0 AI Handbook principle.\n")
        f.write("- Sample size is small (one video per chosen venue, single rater); composite\n")
        f.write("  and pass rate are point estimates, not statistically significant.\n")

    # Console summary
    print(f"\n=== Composite Score: {composite_avg:.2f} / 5.00 (target ≥ {TARGET_COMPOSITE:.2f})")
    print(f"=== Pass Rate: {pass_rate*100:.1f}% ({pass_count}/{len(complete)}, target ≥ {TARGET_PASS_RATE*100:.0f}%)")
    print(f"=== Constraint violations: {constraint_violations}/{len(complete)}")
    print(f"\nReport: {METRICS_MD}")
    return 0 if (composite_avg >= TARGET_COMPOSITE and pass_rate >= TARGET_PASS_RATE) else 1


if __name__ == "__main__":
    raise SystemExit(main())
