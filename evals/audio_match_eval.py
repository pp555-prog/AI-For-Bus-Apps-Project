"""
NOCTURNE AI Evaluation — Audio-Driven Venue Match (paired comparison).

Tests the audio-input flow on /api/ai/demo-venue-match:
- Condition T   (control):   neutral typed style only.
- Condition T+A (treatment): same neutral style PLUS the uploaded audio clip.

For each of the 7 seeded venues, the eval expects ONE audio file at
`evals/audio_samples/<venue_id>.{mp3,wav,m4a,flac,ogg}`. Each clip should be a
~30-second sample sourced/curated to fit that specific venue's vibe (the
"intended venue" for that clip).

Usage:
    1. Make sure the backend is running (python run.py).
    2. Make sure OPENROUTER_API_KEY is set in .env (with credits — the audio
       analysis step is paid).
    3. Drop one audio file per venue into evals/audio_samples/ (see the
       audio_match section of evals/README.md for sourcing guidance).
    4. Run:  .\\.venv\\Scripts\\python.exe evals\\audio_match_eval.py

Outputs:
    evals/audio_results_full.csv  — one row per (clip, condition, rank). Has
                                    matcher_score and matcher_reasoning.
    evals/audio_rate_me.csv       — same rows but with a blank human_rating
                                    column. YOU fill this in 1-5 (does this
                                    venue fit this audio clip?).
    evals/audio_analyses.json     — the structured audio_analysis dicts the
                                    Gemini audio model returned, keyed by
                                    venue_id. For qualitative inspection.

After you fill in human_rating in audio_rate_me.csv, run
audio_compute_metrics.py to get the metrics report.
"""
from __future__ import annotations

import base64
import csv
import json
import sys
from pathlib import Path

import httpx

API_BASE = "http://localhost:8000"
TOP_N = 3
TIMEOUT_S = 180.0  # audio analysis can take 10-20s

EVALS_DIR = Path(__file__).resolve().parent
AUDIO_DIR = EVALS_DIR / "audio_samples"
RESULTS_FULL = EVALS_DIR / "audio_results_full.csv"
RATE_ME = EVALS_DIR / "audio_rate_me.csv"
ANALYSES_JSON = EVALS_DIR / "audio_analyses.json"

# Neutral typed style used in BOTH conditions, so the only varying signal in
# T+A is the audio.
NEUTRAL_STYLE = "experienced electronic music DJ, all-genre, open to any venue"

AUDIO_EXTS = {".mp3": "mp3", ".wav": "wav", ".m4a": "m4a", ".flac": "flac", ".ogg": "ogg"}


def discover_audio_files() -> dict[str, Path]:
    """Return {venue_id: audio_path} for files found in evals/audio_samples/."""
    if not AUDIO_DIR.exists():
        return {}
    files: dict[str, Path] = {}
    for entry in AUDIO_DIR.iterdir():
        if entry.suffix.lower() in AUDIO_EXTS and entry.is_file():
            files[entry.stem] = entry
    return files


def file_to_data_url(path: Path) -> str:
    fmt = AUDIO_EXTS[path.suffix.lower()]
    mime = "audio/mpeg" if fmt == "mp3" else f"audio/{fmt}"
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


def fetch_venues(client: httpx.Client) -> list[dict]:
    r = client.get(f"{API_BASE}/api/venues", timeout=TIMEOUT_S)
    r.raise_for_status()
    return r.json()


def call_demo_venue_match(client: httpx.Client, body: dict) -> dict:
    r = client.post(
        f"{API_BASE}/api/ai/demo-venue-match",
        json=body,
        timeout=TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()


def health_check(client: httpx.Client) -> None:
    try:
        r = client.get(f"{API_BASE}/api/venues", timeout=5.0)
        r.raise_for_status()
    except Exception as e:
        print(f"ERROR: backend not reachable at {API_BASE}: {e}")
        print("Start the backend with: python run.py")
        sys.exit(1)


def main() -> None:
    EVALS_DIR.mkdir(parents=True, exist_ok=True)

    audio_files = discover_audio_files()
    if not audio_files:
        print(f"ERROR: no audio files found under {AUDIO_DIR}/")
        print("Drop one ~30s clip per venue, named <venue_id>.mp3 (or .wav/.m4a/.flac/.ogg).")
        print("See the 'Audio-driven venue match eval' section of evals/README.md for")
        print("sourcing guidance and the venue list.")
        sys.exit(1)

    with httpx.Client() as client:
        health_check(client)

        venues = fetch_venues(client)
        venue_by_id = {v["id"]: v for v in venues}
        print(f"Fetched {len(venues)} venues; have audio for {len(audio_files)}.")

        missing = [vid for vid in venue_by_id if vid not in audio_files]
        extra = [vid for vid in audio_files if vid not in venue_by_id]
        if missing:
            print(f"  Missing audio for: {', '.join(missing)} (those venues will be skipped)")
        if extra:
            print(f"  Audio files without a matching venue: {', '.join(extra)} (ignored)")

        full_rows: list[dict] = []
        rate_rows: list[dict] = []
        analyses: dict[str, dict] = {}
        pair_id = 0

        for source_venue_id, audio_path in sorted(audio_files.items()):
            venue = venue_by_id.get(source_venue_id)
            if not venue:
                continue
            source_venue_name = venue.get("name", source_venue_id)
            data_url = file_to_data_url(audio_path)
            print(f"\n[{source_venue_name}] file={audio_path.name} ({audio_path.stat().st_size//1024} KB)")

            for condition in ("T", "T+A"):
                body = {
                    "performer_name": "Eval Performer",
                    "style": NEUTRAL_STYLE,
                }
                if condition == "T+A":
                    body["audio_data_url"] = data_url

                try:
                    resp = call_demo_venue_match(client, body)
                except Exception as e:
                    print(f"  ERROR on condition {condition}: {e}")
                    continue

                results = resp.get("results", [])[:TOP_N]
                interpretation = resp.get("interpretation")
                matcher_label = resp.get("matcher", "unknown")

                if condition == "T+A":
                    audio_analysis = resp.get("audio_analysis") or {}
                    analyses[source_venue_id] = {
                        "interpretation": interpretation,
                        "audio_analysis": audio_analysis,
                        "combined_style": resp.get("combined_style"),
                    }

                print(f"  [{condition}] matcher={matcher_label}; top-{len(results)}: " +
                      ", ".join(f"{r['venue']['id']}({r['score']})" for r in results))

                for rank, item in enumerate(results, start=1):
                    pair_id += 1
                    matched_venue = item.get("venue") or {}
                    matched_venue_id = matched_venue.get("id")
                    matched_venue_name = matched_venue.get("name", matched_venue_id)
                    score = item.get("score")
                    reasoning = (item.get("reasoning") or "").replace("\n", " ").strip()

                    full_rows.append({
                        "pair_id": pair_id,
                        "source_venue_id": source_venue_id,
                        "source_venue_name": source_venue_name,
                        "audio_file": audio_path.name,
                        "condition": condition,
                        "matcher": matcher_label,
                        "rank": rank,
                        "matched_venue_id": matched_venue_id,
                        "matched_venue_name": matched_venue_name,
                        "matcher_score": score,
                        "matcher_reasoning": reasoning,
                    })
                    rate_rows.append({
                        "pair_id": pair_id,
                        "source_venue_name": source_venue_name,
                        "audio_file": audio_path.name,
                        "condition": condition,
                        "rank": rank,
                        "matched_venue_name": matched_venue_name,
                        "human_rating": "",  # 1-5: does this venue fit this audio?
                    })

    if not full_rows:
        print("\nERROR: no pairs collected.")
        sys.exit(1)

    with open(RESULTS_FULL, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(full_rows[0].keys()))
        w.writeheader()
        w.writerows(full_rows)

    with open(RATE_ME, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rate_rows[0].keys()))
        w.writeheader()
        w.writerows(rate_rows)

    with open(ANALYSES_JSON, "w", encoding="utf-8") as f:
        json.dump(analyses, f, indent=2)

    print(f"\nDone. {len(full_rows)} pairs collected.")
    print(f"  Full results:  {RESULTS_FULL}")
    print(f"  Rate me here:  {RATE_ME}")
    print(f"  Audio reads:   {ANALYSES_JSON}")
    print("\nNEXT STEPS:")
    print(f"  1. Open {RATE_ME.name}.")
    print("  2. For each row, listen to the audio_file (in evals/audio_samples/) and")
    print("     rate the (audio, matched_venue) fit 1-5 in the human_rating column.")
    print("     Hide the matcher_score / matcher_reasoning columns of audio_results_full.csv")
    print("     while you rate, to keep ratings honest.")
    print("  3. Save as CSV and run: .\\.venv\\Scripts\\python.exe evals\\audio_compute_metrics.py")


if __name__ == "__main__":
    main()
