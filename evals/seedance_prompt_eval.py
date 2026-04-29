"""
NOCTURNE AI Evaluation — Seedance Prompt Structure (SPEC §9.5).

Deterministic, offline check that the rendered Seedance video prompt continues
to follow the official Seedance 2.0 AI Handbook. Costs nothing (no API calls);
runs in milliseconds. Treat it as a regression linter — if a future change
quietly reverts the prompt to free prose, this eval fails.

Checks per the handbook:
  - Single-Shot Skeleton sections present (p.7): Format, Asset roles,
    Subject, Environment, Main action, Camera, Lighting, Sound, Style.
  - Asset roles use R1/R2+ notation with the "Sheet" terminology (p.5).
  - Camera vocabulary includes a concrete move (p.16): dolly / track /
    crane / pan / tilt / zoom / close-up / handheld / etc.
  - Lighting vocabulary includes a concrete term (p.16): rim / key / fill /
    backlight / haze / silhouette / golden hour / etc.
  - Constraint vocabulary present (p.16): preserve / avoid / maintain /
    limit / exclude / etc.
  - No banned anti-pattern phrases (p.14): "premium editorial", "expressive
    crowd", "cinematic atmosphere" used as standalone style modifiers, etc.

Renders the prompt for every seeded venue with realistic stand-in inputs
(performer = "Pablo", style text = "melodic techno", with venue + 2 performer
references). Reports pass/fail per venue and exits non-zero if any check
fails so this can later be wired into CI.

Usage:
    python evals/seedance_prompt_eval.py              # uses real seed venues
    python evals/seedance_prompt_eval.py --no-db      # uses canned stand-in venues
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Ensure project root on sys.path so `backend.*` imports resolve when run
# from inside evals/.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.models import Venue
from backend.services.seedance_prompt import build_seedance_prompt

EVALS_DIR = Path(__file__).resolve().parent
REPORT_PATH = EVALS_DIR / "seedance_prompt_metrics.md"


# ── Handbook checks ─────────────────────────────────────────────────────────

REQUIRED_SECTIONS = [
    ("Format/Goal", r"\bFormat:"),
    ("Asset roles", r"\bAsset roles:"),
    ("Subject", r"\bSubject:"),
    ("Environment", r"\bEnvironment:"),
    ("Main action", r"\bMain action:"),
    ("Camera", r"\bCamera:"),
    ("Lighting", r"\bLighting:"),
    ("Sound", r"\bSound:"),
    ("Style", r"\bStyle:"),
]

CAMERA_VOCAB = [
    "dolly", "track", "crane", "pan", "tilt", "zoom",
    "shallow focus", "establishing shot", "close-up", "handheld",
    "medium close-up",
]

LIGHTING_VOCAB = [
    "rim light", "soft light", "hard light", "ambient light",
    "backlight", "key light", "fill light", "silhouette",
    "golden hour", "haze",
]

CONSTRAINT_VOCAB = [
    "avoid", "maintain", "preserve", "limit",
    "emphasize", "exclude", "frame", "restrict", "highlight",
]

# Banned phrases (the actual anti-patterns we burned ourselves on, plus a few
# adjective-soup terms the handbook explicitly calls out on p.14).
BANNED_PHRASES = [
    "premium editorial",
    "expressive crowd",
    "cinematic atmosphere",
    "venue-specific lighting",
    "ethereal vibe",
    "atmospheric depth",
]


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


def check_required_sections(prompt: str) -> list[CheckResult]:
    return [
        CheckResult(
            name=f"section: {label}",
            passed=bool(re.search(pat, prompt)),
            detail="" if re.search(pat, prompt) else f"missing pattern {pat!r}",
        )
        for label, pat in REQUIRED_SECTIONS
    ]


def check_asset_roles(prompt: str) -> CheckResult:
    has_r1 = bool(re.search(r"\bR1\b", prompt))
    has_role = "Identity Sheet" in prompt or "Environment Sheet" in prompt
    passed = has_r1 and has_role
    return CheckResult(
        name="asset roles use R1/R2+ + Sheet terminology",
        passed=passed,
        detail="" if passed else f"R1 present={has_r1}, Sheet term present={has_role}",
    )


def check_vocabulary(prompt: str, name: str, vocab: list[str]) -> CheckResult:
    lower = prompt.lower()
    hits = [term for term in vocab if term in lower]
    passed = bool(hits)
    return CheckResult(
        name=f"{name} vocabulary present",
        passed=passed,
        detail=f"matched: {hits}" if passed else f"none of {vocab[:5]}... found",
    )


def check_no_banned_phrases(prompt: str) -> CheckResult:
    lower = prompt.lower()
    found = [p for p in BANNED_PHRASES if p in lower]
    passed = not found
    return CheckResult(
        name="no banned anti-pattern phrases",
        passed=passed,
        detail="" if passed else f"banned phrases found: {found}",
    )


def check_one_camera_move(prompt: str) -> CheckResult:
    """Heuristic: Camera section should describe ONE dominant move, not many.

    We look at the Camera: line and count distinct primary camera-move verbs
    (handbook says one). Allowing the move + a focus/close-up qualifier is OK.
    """
    m = re.search(r"Camera:\s*(.+?)(?:\.\s|$)", prompt)
    if not m:
        return CheckResult(name="camera: one dominant move", passed=False, detail="no Camera: section")
    seg = m.group(1).lower()
    primary_moves = ["dolly", "track", "crane", "pan", "tilt", "zoom", "handheld"]
    hits = [v for v in primary_moves if v in seg]
    passed = len(hits) <= 1
    return CheckResult(
        name="camera: one dominant move",
        passed=passed,
        detail=f"primary moves found: {hits}",
    )


# ── Venue sources ──────────────────────────────────────────────────────────

CANNED_VENUES: list[Venue] = [
    Venue(id="berghain-berlin", name="BERGHAIN", city="Berlin",
          capacity=1500, vibe_tags=["industrial", "underground", "legendary"],
          description="The legendary institution of Berlin techno culture.",
          image_url="https://example.com/berghain.jpg"),
    Venue(id="the-nest", name="THE NEST", city="London",
          capacity=300, vibe_tags=["intimate", "underground", "velvet"],
          description="Warmly lit underground jazz and electronic club.",
          image_url="https://example.com/the-nest.jpg"),
    Venue(id="amnesia-ibiza", name="AMNESIA IBIZA", city="Ibiza",
          capacity=5000, vibe_tags=["massive", "festival", "ibiza"],
          description="One of the most famous super-clubs in the world.",
          image_url=None),  # exercises the no-venue-ref branch
]


async def fetch_venues_from_db() -> list[Venue]:
    """Pull seeded venues straight from the SQLite DB, no backend required."""
    from backend.database import get_db, init_db
    from backend.seed import seed as run_seed

    await init_db()
    await run_seed()
    db = await get_db()
    try:
        rows = await db.execute_fetchall("SELECT * FROM venues")
        venues = [Venue(**dict(row)) for row in rows]
    finally:
        await db.close()
    return venues


# ── Runner ──────────────────────────────────────────────────────────────────

def run_checks_on(prompt: str) -> list[CheckResult]:
    results: list[CheckResult] = []
    results.extend(check_required_sections(prompt))
    results.append(check_asset_roles(prompt))
    results.append(check_vocabulary(prompt, "camera", CAMERA_VOCAB))
    results.append(check_vocabulary(prompt, "lighting", LIGHTING_VOCAB))
    results.append(check_vocabulary(prompt, "constraint", CONSTRAINT_VOCAB))
    results.append(check_no_banned_phrases(prompt))
    results.append(check_one_camera_move(prompt))
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-db", action="store_true",
                        help="Use canned stand-in venues instead of seeded DB")
    args = parser.parse_args()

    if args.no_db:
        venues = CANNED_VENUES
        source_label = "canned stand-in venues"
    else:
        try:
            venues = asyncio.run(fetch_venues_from_db())
            source_label = "seeded SQLite DB"
        except Exception as exc:  # noqa: BLE001
            print(f"WARNING: failed to load seeded venues ({exc}); falling back to canned set.")
            venues = CANNED_VENUES
            source_label = "canned stand-in venues (DB unavailable)"

    print(f"Source: {source_label}; testing {len(venues)} venues.\n")

    all_results: list[tuple[str, list[CheckResult]]] = []
    failures = 0

    for v in venues:
        # Render prompt with realistic stand-in inputs
        prompt = build_seedance_prompt(
            performer_name="Pablo",
            venue=v,
            style_text="melodic techno, cinematic house, warm late-night energy",
            has_venue_ref=bool(v.image_url),
            performer_ref_count=2,
        )
        results = run_checks_on(prompt)
        passed_n = sum(1 for r in results if r.passed)
        total_n = len(results)
        status = "PASS" if passed_n == total_n else "FAIL"
        print(f"[{status}] {v.id} ({passed_n}/{total_n})")
        for r in results:
            mark = "  OK  " if r.passed else "  ❌  "
            extra = f" — {r.detail}" if r.detail and not r.passed else ""
            print(f"  {mark}{r.name}{extra}")
        if passed_n != total_n:
            failures += 1
        all_results.append((v.id, results))
        print()

    # Write report
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# NOCTURNE Seedance Prompt Eval Results\n\n")
        f.write(f"Source: {source_label}; {len(venues)} venues tested.\n\n")
        f.write("## Per-venue results\n\n")
        for vid, rs in all_results:
            passed = sum(1 for r in rs if r.passed)
            total = len(rs)
            badge = "✅ PASS" if passed == total else "❌ FAIL"
            f.write(f"### {vid} — {badge} ({passed}/{total})\n\n")
            for r in rs:
                mark = "✅" if r.passed else "❌"
                f.write(f"- {mark} {r.name}")
                if r.detail and not r.passed:
                    f.write(f" — {r.detail}")
                elif r.detail:
                    f.write(f" — {r.detail}")
                f.write("\n")
            f.write("\n")
        f.write(f"## Summary\n\n")
        f.write(f"- Venues passing all checks: **{len(venues) - failures}/{len(venues)}**\n")
        f.write(f"- Venues with at least one failure: **{failures}**\n")

    print(f"Report: {REPORT_PATH}")
    print(f"\nSummary: {len(venues) - failures}/{len(venues)} venues passed all checks.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
