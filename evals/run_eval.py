"""
NOCTURNE AI Evaluation — Stage 1: collect Claude's top-3 matches per venue.

Usage:
    1. Make sure the backend is running (python run.py).
    2. Make sure ANTHROPIC_API_KEY is set in .env.
    3. Run:  .\\.venv\\Scripts\\python.exe evals\\run_eval.py

Outputs:
    evals/results_full.csv — every (venue, DJ) pair Claude returned in its
                             top-3, plus its score and reasoning. Used by
                             compute_metrics.py later.
    evals/rate_me.csv      — same pairs but with a blank `human_rating`
                             column. YOU fill this in (1-5 relevance).
                             To keep ratings honest, hide the
                             claude_score and claude_reasoning columns
                             before rating.

After you fill in human_rating in rate_me.csv, run compute_metrics.py.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import httpx

API_BASE = "http://localhost:8000"
TOP_N = 3            # how many of Claude's matches to record per venue
TIMEOUT_S = 60.0     # Claude calls can be slow on cold start

EVALS_DIR = Path(__file__).resolve().parent
RESULTS_FULL = EVALS_DIR / "results_full.csv"
RATE_ME = EVALS_DIR / "rate_me.csv"


def print_vibe_match_error(context: str, exc: Exception) -> None:
    print(f"ERROR: {context}: {exc}")
    if isinstance(exc, httpx.HTTPStatusError):
        response = exc.response
        print(f"  HTTP status: {response.status_code}")
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        if detail:
            print(f"  Response: {detail}")
        if response.status_code == 503:
            print("  Most likely cause: ANTHROPIC_API_KEY is missing or invalid in .env.")


def venue_to_query(venue: dict) -> str:
    """Turn a venue profile into a natural-language vibe-match query.

    Uses the actual NOCTURNE Venue schema: name, city, capacity, vibe_tags,
    description. Older field names (vibe_keywords, location, etc.) are kept as
    fallbacks for forward compatibility.
    """
    name = venue.get("name", "our venue")
    city = venue.get("city") or venue.get("location")
    capacity = venue.get("capacity")
    vibe_tags = venue.get("vibe_tags") or venue.get("vibe_keywords") or []
    description = venue.get("description")

    parts = [f"I am booking a DJ for {name}."]
    if city:
        parts.append(f"Located in {city}.")
    if capacity:
        parts.append(f"Capacity is roughly {capacity} people.")
    if description:
        parts.append(description.strip())
    if vibe_tags:
        parts.append(f"The vibe we want is: {', '.join(vibe_tags)}.")
    parts.append("Recommend the best-fit DJs from your roster.")
    return " ".join(parts)


def fetch_venues(client: httpx.Client) -> list[dict]:
    r = client.get(f"{API_BASE}/api/venues", timeout=TIMEOUT_S)
    r.raise_for_status()
    return r.json()


def fetch_dj(client: httpx.Client, dj_id: str) -> dict:
    r = client.get(f"{API_BASE}/api/djs/{dj_id}", timeout=TIMEOUT_S)
    r.raise_for_status()
    return r.json()


def call_vibe_match(client: httpx.Client, query: str) -> dict:
    r = client.post(
        f"{API_BASE}/api/ai/vibe-match",
        json={"query": query},
        timeout=TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()


def normalize_matches(resp: dict) -> list[dict]:
    """Support the live API response shape without changing eval CSV output."""
    if "matches" in resp:
        return resp.get("matches", [])

    normalized = []
    for item in resp.get("results", []):
        dj = item.get("dj") or {}
        normalized.append({
            "dj_id": dj.get("id"),
            "score": item.get("score"),
            "reasoning": item.get("reasoning"),
        })
    return normalized


def health_check(client: httpx.Client) -> None:
    try:
        r = client.get(f"{API_BASE}/api/venues", timeout=5.0)
        r.raise_for_status()
    except Exception as e:
        print(f"ERROR: backend not reachable at {API_BASE}: {e}")
        print("Start the backend with: python run.py")
        sys.exit(1)

    try:
        resp = call_vibe_match(client, "Quick health check: recommend one DJ for a small house night.")
        matches = normalize_matches(resp)
        if not matches:
            print("ERROR: vibe-match health check returned no matches.")
            print("Most likely cause: backend is running but /api/ai/vibe-match is not returning usable results.")
            print("Check ANTHROPIC_API_KEY in .env and the backend logs.")
            sys.exit(1)
    except Exception as e:
        print_vibe_match_error("vibe-match health check failed", e)
        print("Most likely causes: backend not running, ANTHROPIC_API_KEY missing, or /api/ai/vibe-match returning 503.")
        sys.exit(1)


def main() -> None:
    EVALS_DIR.mkdir(parents=True, exist_ok=True)

    with httpx.Client() as client:
        health_check(client)

        venues = fetch_venues(client)
        print(f"Fetched {len(venues)} venues.")

        full_rows: list[dict] = []
        rate_rows: list[dict] = []
        pair_id = 0

        for v in venues:
            venue_id = v.get("id")
            venue_name = v.get("name", venue_id)
            query = venue_to_query(v)

            print(f"\n[{venue_name}] querying Claude...")
            try:
                resp = call_vibe_match(client, query)
            except Exception as e:
                print_vibe_match_error("calling vibe-match", e)
                continue

            matches = normalize_matches(resp)[:TOP_N]
            if not matches:
                print(f"  WARNING: no matches returned for {venue_name}")
                continue

            for rank, m in enumerate(matches, start=1):
                pair_id += 1
                dj_id = m.get("dj_id")
                claude_score = m.get("score")
                claude_reasoning = (m.get("reasoning") or "").replace("\n", " ").strip()

                # Look up DJ name for the rate sheet
                try:
                    dj = fetch_dj(client, dj_id)
                    dj_name = dj.get("name", dj_id)
                    dj_bio = (dj.get("bio") or "").replace("\n", " ").strip()
                except Exception:
                    dj_name = dj_id
                    dj_bio = ""

                full_rows.append({
                    "pair_id": pair_id,
                    "venue_id": venue_id,
                    "venue_name": venue_name,
                    "dj_id": dj_id,
                    "dj_name": dj_name,
                    "claude_rank": rank,
                    "claude_score": claude_score,
                    "claude_reasoning": claude_reasoning,
                })
                rate_rows.append({
                    "pair_id": pair_id,
                    "venue_name": venue_name,
                    "dj_name": dj_name,
                    "dj_bio_short": dj_bio[:200],
                    "venue_query": query[:200],
                    "human_rating": "",  # YOU fill this in: 1-5
                })
                print(f"  rank {rank}: {dj_name} (score={claude_score})")

    if not full_rows:
        print("\nERROR: eval collected 0 rows; CSV files were not written.")
        print("Most likely causes:")
        print(f"  - Backend is not running at {API_BASE}")
        print("  - ANTHROPIC_API_KEY is missing or invalid in .env")
        print("  - POST /api/ai/vibe-match is returning 503 or no usable matches")
        print("Start the backend, confirm /api/ai/vibe-match works, then re-run:")
        print("  .\\.venv\\Scripts\\python.exe evals\\run_eval.py")
        sys.exit(1)

    # Write CSVs
    with open(RESULTS_FULL, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(full_rows[0].keys()))
        w.writeheader()
        w.writerows(full_rows)

    with open(RATE_ME, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rate_rows[0].keys()))
        w.writeheader()
        w.writerows(rate_rows)

    print(f"\nDone. {len(full_rows)} pairs collected.")
    print(f"  Full results: {RESULTS_FULL}")
    print(f"  Rate me here: {RATE_ME}")
    print("\nNEXT STEPS:")
    print(f"  1. Open {RATE_ME.name} in Excel.")
    print(f"  2. For each row, rate the (venue, DJ) match 1-5 in the human_rating column:")
    print(f"     1 = bad fit, 3 = neutral, 5 = great fit")
    print(f"  3. Save the file (keep it as CSV).")
    print(f"  4. Run: .\\.venv\\Scripts\\python.exe evals\\compute_metrics.py")


if __name__ == "__main__":
    main()
