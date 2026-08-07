"""
Ask the Gemini API which models this key can reach, and recommend one.

Upgrading the analysis model is a deliberate act for a longitudinal record —
this script is step 1 of that process:

    1. PYTHONPATH=. python scripts/check_models.py       # see what's available
    2. set GEMINI_MODEL=<recommended> in Railway
    3. PYTHONPATH=. python scripts/repeatability_study.py --media-dir ./clips
       (confirm score consistency before trusting new trend data)

Usage:
    GEMINI_API_KEY=... PYTHONPATH=. python scripts/check_models.py
    ... --prefer pro           # rank Pro tier first (max reasoning)
    ... --prefer flash-lite    # cheapest tier
    ... --include-preview      # consider preview/experimental models
    ... --quiet                # print only the recommended id (for scripting)
"""

import argparse
import os
import sys

from app.services.model_selector import (
    STABLE_DEFAULT, list_available_models, rank_models,
)


def main():
    ap = argparse.ArgumentParser(description="Discover and rank Gemini models")
    ap.add_argument("--prefer", default="flash",
                    choices=["flash", "pro", "flash-lite"],
                    help="Tier to rank first (default flash: the cost/latency "
                         "fit for per-clip video analysis)")
    ap.add_argument("--include-preview", action="store_true",
                    help="Consider preview/experimental models (they get "
                         "deprecated without notice — not for production)")
    ap.add_argument("--quiet", action="store_true",
                    help="Print only the recommended model id")
    args = ap.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY not set — needed to query available models.")

    try:
        available = list_available_models()
    except Exception as e:
        sys.exit(f"Could not reach the Gemini API: {e}")

    ranked = rank_models(available, prefer_tier=args.prefer,
                         include_preview=args.include_preview)
    if not ranked:
        sys.exit("No suitable multimodal models found for this API key.")

    best = ranked[0]["id"]
    if args.quiet:
        print(best)
        return

    current = os.environ.get("GEMINI_MODEL", STABLE_DEFAULT)

    print(f"\n{len(available)} models reachable; "
          f"{len(ranked)} suitable for video analysis "
          f"(tier preference: {args.prefer})\n")
    print(f"{'':2} {'model':<44} {'tier':<11} {'ver':<6} {'notes'}")
    print("-" * 88)
    for i, info in enumerate(ranked[:12]):
        notes = []
        if info["preview"]:
            notes.append("preview — deprecates without notice")
        if info["dated"]:
            notes.append("pinned snapshot")
        if info["id"] == current:
            notes.append("CURRENTLY CONFIGURED")
        mark = "→" if i == 0 else " "
        ver = f"{info['version'][0]}.{info['version'][1]}"
        print(f"{mark:2} {info['id']:<44} {info['tier']:<11} {ver:<6} "
              f"{', '.join(notes)}")
    if len(ranked) > 12:
        print(f"   … and {len(ranked) - 12} more")

    print("-" * 88)
    print(f"\nRecommended: {best}")
    if best == current:
        print("Already configured — nothing to change.")
    else:
        print(f"Currently configured: {current}")
        print(f"\nTo upgrade:")
        print(f"  1. set  GEMINI_MODEL={best}  (Railway → Variables)")
        print(f"  2. verify consistency before trusting new trend data:")
        print(f"     PYTHONPATH=. python scripts/repeatability_study.py "
              f"--media-dir ./clips")
        print(f"  Rollback at any time: GEMINI_MODEL={current}")
    print("\nNote: stored analyses record the model that produced them, so "
          "past observations stay interpretable across upgrades.\n")


if __name__ == "__main__":
    main()
