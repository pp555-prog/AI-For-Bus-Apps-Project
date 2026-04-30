"""
NOCTURNE AI Evaluation — Seedance Video Output (SPEC §9.6).

Validates that the handbook-structured prompt + venue conditioning actually
produces good-looking video, not just a prompt that passes the §9.5 linter.

The §9.5 eval is a deterministic linter on the prompt text.
THIS eval (§9.6) is the expensive companion: it actually generates videos
through OpenRouter and asks a human rater to score them against the
handbook's principles.

Workflow:
    1. Backend running (python run.py) and OPENROUTER_API_KEY funded.
    2. Drop performer photos somewhere on disk (1-3 JPG/PNG/WEBP files).
    3. Run:
         python evals/seedance_video_eval.py \
             --photos path/to/photo1.jpg path/to/photo2.jpg \
             --venues berghain-berlin the-nest amnesia-ibiza
       (default --venues = first 3 seeded venues; cost = N × ~$1.51)
    4. Eval submits one Seedance job per venue, polls each to completion,
       downloads the MP4s into evals/seedance_outputs/<venue_id>.mp4, and
       writes:
         - seedance_video_results_full.csv (job ids, prompt sent, status)
         - seedance_video_rate_me.csv (one row per video; YOU fill in
           the rubric columns 1-5 after watching each clip)
    5. Watch each MP4 in evals/seedance_outputs/ and rate it on the
       handbook rubric in the rate-me CSV.
    6. Run evals/seedance_video_compute_metrics.py to produce the headline
       report.

Rubric (handbook-aligned, all 1-5 unless noted):
    - identity_preservation: rate 3 neutral; real-person references are blocked (SPEC §9.6)
    - venue_fidelity: does the venue look like the venue reference? (handbook p.4 principle 4: environment is active)
    - action_clarity: is there ONE clear readable action? (handbook p.4 principle 1)
    - camera_coherence: is the camera move coherent and singular? (handbook p.4 principle 2)
    - behavioral_realism: does the DJ's behavior look physically grounded? (handbook p.4 principle 3)
    - constraints_violated_yn: any text/logos/captions/celebrity drift? (yes/no — yes is bad)
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import pathlib
import sys
import time
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVALS_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = EVALS_DIR / "seedance_outputs"
RESULTS_FULL = EVALS_DIR / "seedance_video_results_full.csv"
RATE_ME = EVALS_DIR / "seedance_video_rate_me.csv"

DEFAULT_API = "http://localhost:8000"
POLL_INTERVAL = 15  # seconds
MAX_POLLS = 30      # 7.5 min ceiling per video
COST_PER_CLIP = 1.51  # USD, Seedance 2.0 720p/10s


def read_openrouter_key() -> str | None:
    """Pull OPENROUTER_API_KEY from .env (not from the runtime env, since
    the user's shell may not have it loaded). Used to authenticate the
    OpenRouter content URL when downloading the rendered video."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENROUTER_API_KEY"):
            return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    return None


def encode_image(path: Path, max_dim: int = 1024, quality: int = 85) -> str:
    """Encode an image as a JPEG data URL, resizing to <= max_dim on the long edge.

    OpenRouter's video endpoint accepts data URLs but appears to silently fail
    when the request body is large (multi-MB photos send back a 200 with
    `id: null`, no polling URL). Resizing to ~1024 px JPEG quality 85 keeps
    each data URL under ~250 KB. Performer photos are not forwarded by the
    backend under the current real-person image moderation constraint, but the
    resize path is kept for reproducible eval inputs and future provider paths.
    """
    if not path.exists():
        raise FileNotFoundError(path)
    try:
        from io import BytesIO

        from PIL import Image
    except ImportError:
        # Fallback: ship the raw bytes. Caller should expect failures on
        # large photos; install Pillow for the resize path.
        ext = path.suffix.lower().lstrip(".")
        mime_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}
        mime = mime_map.get(ext, "jpeg")
        b64 = base64.b64encode(path.read_bytes()).decode()
        print(f"  WARNING: Pillow not installed; sending {path.name} unresized "
              f"({len(b64)*3//4//1024} KB raw, {len(b64)//1024} KB base64). "
              f"Install with: .\\.venv\\Scripts\\pip.exe install Pillow")
        return f"data:image/{mime};base64,{b64}"

    img = Image.open(path)
    orig_size = img.size
    if img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    if max(w, h) > max_dim:
        ratio = max_dim / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    raw_bytes = buf.getvalue()
    b64 = base64.b64encode(raw_bytes).decode()
    print(f"  encoded {path.name}: {orig_size[0]}x{orig_size[1]} -> "
          f"{img.size[0]}x{img.size[1]}, {len(raw_bytes)//1024} KB JPEG, "
          f"{len(b64)//1024} KB base64")
    return f"data:image/jpeg;base64,{b64}"


def fetch_venues(client: httpx.Client, api: str) -> list[dict]:
    r = client.get(f"{api}/api/venues", timeout=30)
    r.raise_for_status()
    return r.json()


def submit_video(client: httpx.Client, api: str, body: dict) -> dict:
    r = client.post(f"{api}/api/ai/demo-performance-video", json=body, timeout=60)
    if r.status_code >= 400:
        # Surface the upstream error body — when the backend wraps an
        # OpenRouter failure as a 502, the actual upstream message lives in
        # `detail` and that's what we need to debug.
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        raise httpx.HTTPStatusError(
            f"HTTP {r.status_code}: {str(detail)[:600]}",
            request=r.request, response=r,
        )
    return r.json()


def poll_video(client: httpx.Client, api: str, job_id: str) -> dict:
    r = client.get(f"{api}/api/ai/demo-performance-video/{job_id}", timeout=30)
    r.raise_for_status()
    return r.json()


def download_video(url: str, dest: Path, openrouter_key: str | None, api_base: str = DEFAULT_API) -> None:
    # As of 2026-04-30 the backend's polling endpoint downloads the OpenRouter
    # MP4 server-side and returns a local path like /assets/generated/...mp4
    # so the browser can play it without Bearer auth. For the eval that
    # local path needs to be turned into a full URL via the configured API base.
    if url.startswith("/"):
        url = f"{api_base.rstrip('/')}{url}"
    headers = {}
    if "openrouter.ai" in url and openrouter_key:
        headers["Authorization"] = f"Bearer {openrouter_key}"
    with httpx.Client(timeout=180, follow_redirects=True) as c:
        r = c.get(url, headers=headers)
        r.raise_for_status()
        dest.write_bytes(r.content)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seedance video output eval (SPEC §9.6)")
    parser.add_argument("--photos", nargs="+", required=True,
                        help="Paths to performer photos (1-3 JPG/PNG/WEBP)")
    parser.add_argument("--venues", nargs="+", default=None,
                        help="Venue IDs to test (default: first 3 seeded venues)")
    parser.add_argument("--style", default="melodic techno, cinematic late-night energy",
                        help="Performer style description")
    parser.add_argument("--performer-name", default="Pablo")
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--yes", action="store_true",
                        help="Skip the cost-confirmation prompt")
    args = parser.parse_args()

    photo_paths = [Path(p) for p in args.photos][:3]
    for p in photo_paths:
        if not p.exists():
            print(f"ERROR: photo not found: {p}", file=sys.stderr)
            return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    openrouter_key = read_openrouter_key()
    if not openrouter_key:
        print("WARNING: OPENROUTER_API_KEY not found in .env — video downloads will likely fail.")

    with httpx.Client() as client:
        # Health check + venue fetch
        try:
            all_venues = fetch_venues(client, args.api)
        except Exception as e:
            print(f"ERROR: backend unreachable at {args.api}: {e}", file=sys.stderr)
            return 1

        venues_by_id = {v["id"]: v for v in all_venues}
        if args.venues:
            missing = [vid for vid in args.venues if vid not in venues_by_id]
            if missing:
                print(f"ERROR: unknown venue IDs: {missing}", file=sys.stderr)
                return 1
            venues = [venues_by_id[vid] for vid in args.venues]
        else:
            venues = all_venues[:3]

        # Cost confirmation
        n = len(venues)
        cost = n * COST_PER_CLIP
        print(f"\nWill submit {n} Seedance video jobs.")
        print(f"  Performer: {args.performer_name}; style: {args.style!r}")
        print(f"  Photos: {[p.name for p in photo_paths]}")
        print(f"  Venues: {[v['id'] for v in venues]}")
        print(f"  Estimated cost: ${cost:.2f} (${COST_PER_CLIP:.2f} × {n})")
        if not args.yes:
            confirm = input("Proceed? [y/N]: ").strip().lower()
            if confirm != "y":
                print("Aborted.")
                return 0

        # Encode photos once
        try:
            photo_data_urls = [encode_image(p) for p in photo_paths]
        except FileNotFoundError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1

        full_rows: list[dict] = []
        rate_rows: list[dict] = []
        pair_id = 0

        for v in venues:
            pair_id += 1
            vid = v["id"]
            vname = v.get("name", vid)
            print(f"\n[{vname}] submitting Seedance job...")
            try:
                submit_resp = submit_video(client, args.api, {
                    "performer_name": args.performer_name,
                    "style": args.style,
                    "venue_id": vid,
                    "image_data_urls": photo_data_urls,
                })
            except Exception as e:
                print(f"  ERROR submitting: {e}")
                full_rows.append({
                    "pair_id": pair_id, "venue_id": vid, "venue_name": vname,
                    "status": "submit_failed", "error": str(e),
                    "job_id": "", "video_path": "",
                })
                continue

            job_id = submit_resp.get("job_id") or ""
            if not job_id:
                # Surface the raw response so we can diagnose why no job_id came back
                # (fallback path? OpenRouter content moderation? unexpected response shape?)
                print("  WARNING: submit returned no job_id. Full response:")
                print(f"    {json.dumps(submit_resp, indent=2, default=str)[:800]}")
                full_rows.append({
                    "pair_id": pair_id, "venue_id": vid, "venue_name": vname,
                    "status": submit_resp.get("status", "no_job_id"),
                    "error": "submit returned no job_id; raw response: "
                             + json.dumps(submit_resp, default=str)[:400],
                    "job_id": "", "video_path": "",
                })
                continue
            print(f"  job_id={job_id}, polling every {POLL_INTERVAL}s (max {MAX_POLLS} polls)...")

            final: dict | None = None
            t0 = time.time()
            for i in range(MAX_POLLS):
                time.sleep(POLL_INTERVAL)
                try:
                    status_resp = poll_video(client, args.api, job_id)
                except Exception as e:
                    print(f"  poll {i+1}: ERROR {e}")
                    continue
                status = status_resp.get("status")
                elapsed = time.time() - t0
                print(f"  poll {i+1} t={elapsed:.0f}s: status={status}")
                if status in ("completed", "failed", "error"):
                    final = status_resp
                    break

            if not final:
                print("  TIMED OUT")
                full_rows.append({
                    "pair_id": pair_id, "venue_id": vid, "venue_name": vname,
                    "status": "timeout", "error": "polling timed out",
                    "job_id": job_id, "video_path": "",
                })
                continue

            if final.get("status") != "completed":
                err = final.get("note") or final.get("status")
                print(f"  ENDED with status={final.get('status')}: {err}")
                full_rows.append({
                    "pair_id": pair_id, "venue_id": vid, "venue_name": vname,
                    "status": final.get("status", "unknown"),
                    "error": str(err),
                    "job_id": job_id, "video_path": "",
                })
                continue

            video_url = final.get("video_url") or ""
            if not video_url:
                full_rows.append({
                    "pair_id": pair_id, "venue_id": vid, "venue_name": vname,
                    "status": "no_video_url", "error": "completed but no video_url",
                    "job_id": job_id, "video_path": "",
                })
                continue

            dest = OUTPUT_DIR / f"{vid}.mp4"
            try:
                download_video(video_url, dest, openrouter_key, args.api)
                size_kb = dest.stat().st_size // 1024
                print(f"  downloaded -> {dest} ({size_kb} KB)")
            except Exception as e:
                print(f"  download failed: {e}")
                full_rows.append({
                    "pair_id": pair_id, "venue_id": vid, "venue_name": vname,
                    "status": "download_failed", "error": str(e),
                    "job_id": job_id, "video_path": "",
                })
                continue

            full_rows.append({
                "pair_id": pair_id, "venue_id": vid, "venue_name": vname,
                "status": "completed", "error": "",
                "job_id": job_id, "video_path": str(dest.relative_to(PROJECT_ROOT)),
            })
            rate_rows.append({
                "pair_id": pair_id,
                "venue_id": vid,
                "venue_name": vname,
                "video_file": dest.name,
                "identity_preservation": "",
                "venue_fidelity": "",
                "action_clarity": "",
                "camera_coherence": "",
                "behavioral_realism": "",
                "constraints_violated_yn": "",
            })

    # Write CSVs
    if full_rows:
        with open(RESULTS_FULL, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(full_rows[0].keys()))
            w.writeheader()
            w.writerows(full_rows)
    if rate_rows:
        with open(RATE_ME, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rate_rows[0].keys()))
            w.writeheader()
            w.writerows(rate_rows)

    completed = sum(1 for r in full_rows if r["status"] == "completed")
    print(f"\nDone. {completed}/{len(full_rows)} videos completed and downloaded.")
    print(f"  Videos:        {OUTPUT_DIR}/")
    print(f"  Full results:  {RESULTS_FULL}")
    print(f"  Rate me here:  {RATE_ME}")
    print("\nNEXT STEPS:")
    print(f"  1. Watch each MP4 in {OUTPUT_DIR.relative_to(PROJECT_ROOT)}/")
    print(f"  2. Open {RATE_ME.name} and fill in the rubric columns:")
    print("       identity_preservation     RATE 3 NEUTRAL ON ALL ROWS — N/A under SPEC §9.6:")
    print("                                 hosted video models block real-person photos")
    print("                                 ('InputImageSensitiveContentDetected.PrivacyInformation'),")
    print("                                 so the rendered DJ is a generic stand-in by design.")
    print("       venue_fidelity            1-5 (1=generic club, 5=clearly the same room as the venue ref)")
    print("       action_clarity            1-5 (1=chaotic/multiple actions, 5=single dominant action)")
    print("       camera_coherence          1-5 (1=erratic/multiple moves, 5=single smooth move; for")
    print("                                 Multi-Shot prompts, score the per-beat camera moves as a unit)")
    print("       behavioral_realism        1-5 (1=AI-uncanny/wrong hands, 5=natural physical performance)")
    print("       constraints_violated_yn   yes/no (text, logos, captions, celebrity drift?)")
    print(f"  3. Run: python evals/seedance_video_compute_metrics.py")
    return 0 if completed == len(full_rows) and full_rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
