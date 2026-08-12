#!/usr/bin/env python3
"""
Calibrate the coat-colour half of the identity screen against real data.

The species check needs no calibration — the detector either says cat or it
says dog. The coat-colour check does, and it has not had any: DISTANCE_FLOOR
in identity_check.py is a conservative guess, chosen so the screen stays quiet
rather than cry wolf, and it should be replaced with a number measured from
actual captures before anyone leans on it.

This is the same posture as scripts/validate_respiration.py: the measurement
ships, and the script that proves it is worth trusting ships beside it.

What it does: for every pet with stored signatures, measure how far that pet's
own captures sit from each other (within-pet), and how far they sit from other
pets' captures (between-pet). Those two distributions are the whole question.
If they overlap, the check cannot work at any threshold and should be turned
off; if they separate, the gap between them is where the floor belongs.

    PYTHONPATH=. python scripts/validate_identity.py
    PYTHONPATH=. python scripts/validate_identity.py --data-dir /data

Needs at least two pets with three captures each to say anything useful.
"""
import argparse
import os
import sys


def percentile(values, p):
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", help="Overrides DATA_DIR for this run")
    args = ap.parse_args()
    if args.data_dir:
        os.environ["DATA_DIR"] = args.data_dir

    from app.services import pet_store, identity_check

    pets = pet_store.list_pets()
    groups = {}
    for pet in pets:
        sigs = pet_store.coat_signatures(pet["id"], limit=500)
        if len(sigs) >= 2:
            groups[pet["name"]] = sigs

    if len(groups) < 2:
        print("Not enough data. Need at least two pets with two or more stored")
        print("captures each. Signatures are only recorded for uploads analysed")
        print("after this feature shipped — keep using the app and re-run.")
        for pet in pets:
            print(f"  {pet['name']}: {len(pet_store.coat_signatures(pet['id']))} signatures")
        return 1

    within, between = [], []
    names = list(groups)
    for i, a in enumerate(names):
        for x in range(len(groups[a])):
            for y in range(x + 1, len(groups[a])):
                d = identity_check.distance(groups[a][x], groups[a][y])
                if d is not None:
                    within.append(d)
        for b in names[i + 1:]:
            for sa in groups[a]:
                for sb in groups[b]:
                    d = identity_check.distance(sa, sb)
                    if d is not None:
                        between.append(d)

    print(f"\nPets: {', '.join(f'{n} ({len(groups[n])})' for n in names)}")
    print(f"Within-pet pairs:  {len(within)}")
    print(f"Between-pet pairs: {len(between)}\n")

    if not within or not between:
        print("No comparable pairs. Nothing to conclude.")
        return 1

    w95 = percentile(within, 0.95)
    b05 = percentile(between, 0.05)
    print(f"  Within-pet   median {percentile(within, 0.5):.3f}   95th {w95:.3f}")
    print(f"  Between-pet  median {percentile(between, 0.5):.3f}    5th {b05:.3f}")
    print(f"  Current DISTANCE_FLOOR: {identity_check.DISTANCE_FLOOR}\n")

    if b05 > w95:
        suggested = round((w95 + b05) / 2, 2)
        print(f"  SEPARATED. The two distributions don't overlap.")
        print(f"  Set DISTANCE_FLOOR = {suggested} (midway between "
              f"{w95:.3f} and {b05:.3f}).")
        if not (w95 <= identity_check.DISTANCE_FLOOR <= b05):
            print(f"  The current floor is OUTSIDE that gap and should be moved.")
    else:
        print("  OVERLAPPING. Some of this pet's own captures sit further apart")
        print("  than captures of different animals do, so no threshold can")
        print("  separate them. On this data the coat-colour check cannot work —")
        print("  the honest move is to leave the floor high (quiet) or drop the")
        print("  appearance signal and keep only the species check.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
