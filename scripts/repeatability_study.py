"""
Test-retest repeatability study for the analysis pipeline.

For a longitudinal instrument, consistency matters as much as accuracy: if
the same clip scores 42 today and 55 tomorrow, trend slopes and baseline
deviations are noise. This script runs each media file through the real
pipeline N times and reports per-clip mean, SD, range, and coefficient of
variation for the distress score and instrument total — plus how often the
zone classification flips.

Usage:
    GEMINI_API_KEY=... PYTHONPATH=. python scripts/repeatability_study.py \\
        --media-dir ./test_clips --runs 5

Interpreting results (rules of thumb):
    distress SD <= 5 points   good — trend math is trustworthy
    distress SD 5-10          acceptable — flags at 1.5 SD still meaningful
    distress SD > 10          problem — lower Pass 2 temperature and retest
    zone flips on same clip   should be rare; frequent flips = UX whiplash

Costs real Gemini API calls: files x runs analyses. Start small (3 clips,
3 runs). Uses the exact production path (analyze_video), including YOLO and
audio when available.
"""

import argparse
import json
import os
import statistics
import sys

from app.services.gemini_service import analyze_video, GEMINI_MODEL

MEDIA_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".jpg", ".jpeg", ".png", ".webp"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def main():
    ap = argparse.ArgumentParser(description="Test-retest repeatability study")
    ap.add_argument("--media-dir", required=True, help="Directory of clips/photos")
    ap.add_argument("--runs", type=int, default=5, help="Analyses per file (default 5)")
    ap.add_argument("--out", default="repeatability_results.json", help="Raw results JSON")
    args = ap.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY not set — this study runs the real pipeline.")

    files = sorted(
        f for f in os.listdir(args.media_dir)
        if os.path.splitext(f)[1].lower() in MEDIA_EXTS
    )
    if not files:
        sys.exit(f"No media files found in {args.media_dir}")

    print(f"Model: {GEMINI_MODEL} | files: {len(files)} | runs each: {args.runs}")
    print(f"Total analyses: {len(files) * args.runs}\n")

    raw = {}
    for fname in files:
        path = os.path.join(args.media_dir, fname)
        kind = "image" if os.path.splitext(fname)[1].lower() in IMAGE_EXTS else "video"
        raw[fname] = []
        for run in range(1, args.runs + 1):
            print(f"[{fname}] run {run}/{args.runs}...")
            result = analyze_video(path, media_kind=kind)
            if result.get("error"):
                print(f"  ! error: {result.get('message')}")
                raw[fname].append({"error": result.get("message")})
                continue
            oa = result.get("overall_assessment", {})
            ins = result.get("instrument_scores", {})
            raw[fname].append({
                "distress": oa.get("distress_score"),
                "zone": oa.get("zone"),
                "primary_state": oa.get("primary_state"),
                "instrument_total": ins.get("total"),
                "species": result.get("species"),
                "breed": result.get("breed_detected"),
            })

    with open(args.out, "w") as f:
        json.dump({"model": GEMINI_MODEL, "runs": args.runs, "results": raw}, f, indent=1)

    # ── Report ──
    print(f"\n{'='*72}")
    print(f"{'file':<28} {'n':>2} {'mean':>6} {'SD':>5} {'range':>9} {'CV%':>5} "
          f"{'zone flips':>10} {'instr SD':>8}")
    print("-" * 72)
    worst_sd = 0.0
    for fname, runs in raw.items():
        scores = [r["distress"] for r in runs if r.get("distress") is not None]
        zones = [r["zone"] for r in runs if r.get("zone")]
        instr = [r["instrument_total"] for r in runs if r.get("instrument_total") is not None]
        if len(scores) < 2:
            print(f"{fname:<28} insufficient successful runs")
            continue
        mean = statistics.mean(scores)
        sd = statistics.stdev(scores)
        worst_sd = max(worst_sd, sd)
        cv = sd / mean * 100 if mean else 0
        flips = len(set(zones)) - 1
        isd = f"{statistics.stdev(instr):.2f}" if len(instr) >= 2 else "—"
        print(f"{fname:<28} {len(scores):>2} {mean:>6.1f} {sd:>5.1f} "
              f"{min(scores):>4}-{max(scores):<4} {cv:>5.1f} {flips:>10} {isd:>8}")

    print("-" * 72)
    verdict = ("GOOD (SD <= 5: trend math trustworthy)" if worst_sd <= 5 else
               "ACCEPTABLE (SD 5-10: flags still meaningful)" if worst_sd <= 10 else
               "PROBLEM (SD > 10: lower Pass 2 temperature and retest)")
    print(f"Worst per-clip SD: {worst_sd:.1f} → {verdict}")
    print(f"Raw results saved to {args.out}")


if __name__ == "__main__":
    main()
