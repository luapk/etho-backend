"""
Validate the sleeping respiratory-rate (SRR) extractor against manual counts.

The SRR feature must not be trusted until this study passes on REAL sleeping
clips. Breathing is visible to the eye, so ground truth is cheap: watch each
clip, count breaths for a timed window, convert to breaths/min.

Setup:
    1. Collect sleeping-pet clips (30-60s, camera propped still) in a folder.
    2. Create counts.csv in that folder:  filename,manual_bpm
           miso_sleeping_1.mp4,22
           bruno_nap.mp4,16
    3. Run:
           PYTHONPATH=. python scripts/validate_respiration.py --media-dir ./srr_clips

Verdict guide:
    MAE <= 2 bpm   excellent — clinically useful
    MAE <= 3 bpm   acceptable for screening (state the error bound in docs)
    MAE  > 3 bpm   do not ship a number; keep the feature flagged experimental

No API keys needed — this is pure signal processing.
"""

import argparse
import csv
import os
import sys

from app.services.respiration_service import RespirationService


def main():
    ap = argparse.ArgumentParser(description="SRR extractor validation study")
    ap.add_argument("--media-dir", required=True,
                    help="Folder of sleeping clips + counts.csv (filename,manual_bpm)")
    args = ap.parse_args()

    counts_path = os.path.join(args.media_dir, "counts.csv")
    if not os.path.exists(counts_path):
        sys.exit(f"Missing {counts_path} — create it with lines: filename,manual_bpm")

    truth = {}
    with open(counts_path) as f:
        for row in csv.reader(f):
            if len(row) >= 2 and row[0].strip() and not row[0].startswith("#"):
                try:
                    truth[row[0].strip()] = float(row[1])
                except ValueError:
                    pass
    if not truth:
        sys.exit("counts.csv contained no usable rows")

    svc = RespirationService()
    if not svc.available:
        sys.exit("Respiration service unavailable (needs cv2 + scipy)")

    print(f"\n{'file':<32} {'manual':>7} {'measured':>9} {'err':>6} {'conf':>7} {'note'}")
    print("-" * 78)
    errors = []
    rejected = 0
    for fname, manual in sorted(truth.items()):
        path = os.path.join(args.media_dir, fname)
        if not os.path.exists(path):
            print(f"{fname:<32} {'—':>7} {'missing file'}")
            continue
        r = svc.analyze(path)
        if r["usable"]:
            err = r["breaths_per_min"] - manual
            errors.append(abs(err))
            print(f"{fname:<32} {manual:>7.1f} {r['breaths_per_min']:>9.1f} "
                  f"{err:>+6.1f} {r['confidence']:>7}")
        else:
            rejected += 1
            print(f"{fname:<32} {manual:>7.1f} {'refused':>9} {'':>6} {'':>7} {r['reason']}")

    print("-" * 78)
    if not errors:
        sys.exit("No clips produced a measurement — check clip quality/stillness.")
    mae = sum(errors) / len(errors)
    worst = max(errors)
    print(f"n={len(errors)} measured, {rejected} refused | "
          f"MAE {mae:.2f} bpm | worst {worst:.1f} bpm")
    verdict = ("EXCELLENT (MAE <= 2): clinically useful" if mae <= 2 else
               "ACCEPTABLE (MAE <= 3): ship with stated error bound" if mae <= 3 else
               "NOT READY (MAE > 3): keep experimental, do not surface numbers")
    print(f"Verdict: {verdict}")
    print("\nNote: refusals on non-still clips are CORRECT behaviour, not "
          "failures — the extractor must decline rather than guess.")


if __name__ == "__main__":
    main()
