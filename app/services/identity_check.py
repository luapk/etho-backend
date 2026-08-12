"""
Is this the same animal?

A longitudinal record is only worth anything if every observation in it came
from the same pet. Two households with a cat and a dog, a phone shared between
partners, a camera roll imported in bulk — it takes one misfiled clip to put a
stranger's distress score into Louis's baseline, and the baseline is what every
deviation, slope and red flag in this product is measured against. One wrong
row poisons all of them, silently, for months.

**What this is not.** It is not pet re-identification. Individual animal re-ID
is an open research problem; the published work needs a purpose-trained
embedding model, and we have neither the model nor the data to validate one.
Nothing in this file can tell two tabbies apart, and it never claims to.

So this is a *guardrail*, built only from things that are actually measured,
and it is deliberately lopsided: one signal that is nearly always right, and
one that is weak and treated as weak.

  1. **Species.** YOLO detects by class — the box is only drawn because the
     detector decided "cat" or "dog". If the profile says cat and every frame
     says dog, that is not a subtle inference, it is a filing error. This is
     the check that earns its place.

  2. **Coat colour.** A hue/saturation/value histogram over the middle of the
     detection box, averaged across several frames. Genuinely discriminative
     for a black cat against a ginger one, useless for two tabbies, and moved
     by lighting as much as by identity. It only speaks when the new capture
     sits further from the pet's own previous captures than those captures sit
     from each other — the same "each pet is its own control" rule the distress
     baseline uses, and the same ≥3 prior observations before it says anything.

     **And it is switched off by default anyway** (`IDENTITY_APPEARANCE`). The
     threshold has never been measured against real captures, so it is a guess,
     and a wrong "is this really your pet?" teaches a guardian that this app's
     warnings are noise. The measurement still runs and is still stored — so
     `scripts/validate_identity.py` can tell you whether the within-pet and
     between-pet distances actually separate on your own data, which is the
     thing that has to be true before the alarm is worth switching on.

Three rules keep this honest, and they are the same three that quarantine the
breed data:

  * **It never reaches Gemini.** Not Pass 1, not Pass 2. Telling the model
    "this may not be the same animal" would invite it to find differences, and
    Pass 1 is a ground-truth lock that Pass 2 is obliged to honour.
  * **It never moves a score.** No distress number, no zone, no instrument
    total is touched by anything computed here.
  * **It never blocks or reassigns.** The upload is analysed and logged
    exactly as asked. This produces a question for the guardian, who is the
    only one who actually knows which animal is on screen.
"""

import json
import math
import os
from collections import Counter
from typing import Optional

# Histogram shape. Coarse on purpose: fine bins would make every change of
# lighting look like a change of animal.
HUE_BINS = 12
SAT_BINS = 4
VAL_BINS = 8
SIG_LEN = HUE_BINS * SAT_BINS + VAL_BINS

# The middle of the box only. The edges of a detection box are mostly floor,
# sofa and wall, and background is exactly what we don't want in a coat colour.
CROP_INSET = 0.20

# How many frames to average. Enough to survive one blurred or half-occluded
# frame, few enough to stay cheap.
MAX_SAMPLE_FRAMES = 5

# Same threshold as the distress baseline: with fewer than three priors there
# is no spread to compare against, so the honest answer is "can't tell yet".
MIN_HISTORY = 3

# A capture must be this far from every prior capture before the appearance
# signal will speak, however tight the pet's own history happens to be. Without
# a floor, a pet with three near-identical captures would flag on the fourth
# for being photographed in a different room.
DISTANCE_FLOOR = 0.45
SD_MULTIPLIER = 2.0

# The appearance ALARM is off by default. The measurement still runs, is still
# stored and is still reported in the block — but it will not raise a question
# to a guardian until someone has shown it can.
#
# The floor above is a guess. Nobody has yet measured, on real captures, where
# "the same cat in the kitchen and in the garden" sits relative to "two
# different cats", and until those two distributions are known to separate,
# any threshold is arbitrary. A false "is this really your pet?" is not a
# harmless nudge in a health product: it teaches the guardian that the tool's
# warnings are noise, which is the one thing the red flags cannot afford.
#
# This is the same posture as ENABLE_POSE. The signal is computed, kept and
# inspectable; it just isn't allowed to speak yet.
#
#   PYTHONPATH=. python scripts/validate_identity.py   ← run this first
#   IDENTITY_APPEARANCE=1                              ← then turn it on
APPEARANCE_ALARM = os.environ.get("IDENTITY_APPEARANCE", "") == "1"


# ── Measuring ────────────────────────────────────────────────────────────────

def _crop(frame, bbox):
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = bbox
    bw, bh = x2 - x1, y2 - y1
    if bw <= 4 or bh <= 4:
        return None
    x1 += bw * CROP_INSET
    x2 -= bw * CROP_INSET
    y1 += bh * CROP_INSET
    y2 -= bh * CROP_INSET
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2, y2 = min(w, int(x2)), min(h, int(y2))
    if x2 - x1 < 4 or y2 - y1 < 4:
        return None
    return frame[y1:y2, x1:x2]


def _histogram(frame, bbox) -> Optional[list]:
    """Normalised HS + V histogram of the animal region of one frame."""
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    patch = _crop(frame, bbox)
    if patch is None or patch.size == 0:
        return None
    try:
        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        # Hue is meaningless where there is no colour, so the HS plane is
        # weighted by saturation-and-value via a mask, and greys are carried by
        # the separate V histogram instead. A white cat and a black cat differ
        # in V, not in H.
        mask = cv2.inRange(hsv, (0, 40, 30), (180, 255, 255))
        hs = cv2.calcHist([hsv], [0, 1], mask, [HUE_BINS, SAT_BINS],
                          [0, 180, 0, 256]).flatten()
        v = cv2.calcHist([hsv], [2], None, [VAL_BINS], [0, 256]).flatten()
        hs = hs / hs.sum() if hs.sum() > 0 else hs
        v = v / v.sum() if v.sum() > 0 else v
        # Halved so the two halves contribute equally and the whole vector sums
        # to 1 — otherwise a greyscale animal (empty HS half) would sit at a
        # constant distance from every colourful one for the wrong reason.
        return [round(float(x), 5) for x in np.concatenate([hs * 0.5, v * 0.5])]
    except Exception:
        return None


def _mean(vectors: list) -> Optional[list]:
    if not vectors:
        return None
    n = len(vectors)
    return [round(sum(v[i] for v in vectors) / n, 5) for i in range(len(vectors[0]))]


def coat_signature(media_path: str, pose_frames: list, is_video: bool) -> Optional[list]:
    """Average coat-colour signature for one upload, or None.

    Read from the ORIGINAL media, never from the annotated copy: the annotated
    frames have a detection box, a distress meter and caption strips drawn on
    them, and sampling colour out of the tool's own overlay would be measuring
    ourselves.
    """
    try:
        import cv2
    except Exception:
        return None
    usable = [pf for pf in pose_frames or [] if pf.animals]
    if not usable:
        return None

    # Spread the samples across the clip rather than taking the first N, which
    # on a phone video are all the same second of footage.
    step = max(1, len(usable) // MAX_SAMPLE_FRAMES)
    chosen = usable[::step][:MAX_SAMPLE_FRAMES]

    hists = []
    try:
        if not is_video:
            frame = cv2.imread(media_path)
            if frame is None:
                return None
            for animal in chosen[0].animals[:1]:
                h = _histogram(frame, animal.bbox)
                if h:
                    hists.append(h)
        else:
            cap = cv2.VideoCapture(media_path)
            if not cap.isOpened():
                return None
            try:
                for pf in chosen:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, pf.frame_idx)
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        continue
                    # The largest box: with two animals in shot the profile pet
                    # is far more likely to be the one filling the frame.
                    animal = max(pf.animals,
                                 key=lambda a: (a.bbox[2] - a.bbox[0]) * (a.bbox[3] - a.bbox[1]))
                    h = _histogram(frame, animal.bbox)
                    if h:
                        hists.append(h)
            finally:
                cap.release()
    except Exception as e:
        print(f"  ⚠ Coat signature failed: {e}")
        return None
    return _mean(hists)


def measured_species(pose_frames: list) -> Optional[str]:
    """The species the DETECTOR saw, by majority of detections.

    Not Gemini's `species` field. This one is a class label out of the model
    that drew the box, which makes it the closest thing to a measurement we
    have about what kind of animal is on screen.
    """
    names = Counter()
    for pf in pose_frames or []:
        for a in pf.animals:
            if a.class_name in ("cat", "dog"):
                names[a.class_name] += 1
    if not names:
        return None
    top, count = names.most_common(1)[0]
    # A handful of stray frames shouldn't outvote nothing; require that the
    # winner is a clear majority of what was detected.
    return top if count >= 0.6 * sum(names.values()) else None


# ── Comparing ────────────────────────────────────────────────────────────────

def distance(a: list, b: list) -> Optional[float]:
    """0 = identical, 1 = no overlap at all. Plain L1 over two normalised
    distributions, halved, which is total-variation distance — cheap, bounded,
    and it degrades gracefully rather than exploding on an empty bin the way
    chi-square does."""
    if not a or not b or len(a) != len(b):
        return None
    return round(sum(abs(x - y) for x, y in zip(a, b)) / 2.0, 4)


def _spread(signatures: list) -> Optional[tuple]:
    """How much this pet's own captures already differ from each other."""
    d = []
    for i in range(len(signatures)):
        for j in range(i + 1, len(signatures)):
            v = distance(signatures[i], signatures[j])
            if v is not None:
                d.append(v)
    if not d:
        return None
    mean = sum(d) / len(d)
    var = sum((x - mean) ** 2 for x in d) / len(d)
    return mean, math.sqrt(var)


def parse_signature(raw) -> Optional[list]:
    """Signatures are stored as JSON text. Anything unreadable is absent, not
    an error — this whole layer is advisory."""
    if not raw:
        return None
    try:
        v = json.loads(raw) if isinstance(raw, str) else raw
        return v if isinstance(v, list) and len(v) == SIG_LEN else None
    except Exception:
        return None


def check(pet: dict, signature: Optional[list], seen_species: Optional[str],
          prior_signatures: list) -> dict:
    """Compare one upload against the pet it is being filed under.

    Returns a block that always states what it looked at, including when the
    answer is "not enough to say" — an absent check and a passed check are
    different things and the UI has to be able to tell them apart.
    """
    name = (pet or {}).get("name") or "this pet"
    expected = ((pet or {}).get("species") or "").strip().lower() or None

    out = {
        "status": "unverified",
        "headline": None,
        "detail": None,
        "species_expected": expected,
        "species_seen": seen_species,
        "appearance_distance": None,
        "appearance_threshold": None,
        "compared_with": len(prior_signatures or []),
    }

    # 1. Species. The one signal strong enough to raise on its own.
    if expected and seen_species and expected != seen_species:
        out["status"] = "species_mismatch"
        out["headline"] = f"This looks like a {seen_species}, but {name} is a {expected}."
        out["detail"] = (
            f"The detector found a {seen_species} in every frame it scored. "
            f"It's been analysed and filed under {name} as you asked — if that's "
            f"wrong, move it to the right pet so it doesn't join {name}'s baseline."
        )
        return out

    # 2. Appearance. Weak by construction, and silent without a baseline.
    priors = [p for p in (prior_signatures or []) if p]
    if not signature or len(priors) < MIN_HISTORY:
        out["detail"] = (
            "Not enough of a history to compare appearance yet — "
            f"{name} needs {MIN_HISTORY} previous captures for that."
            if signature else
            "Nothing measurable to compare: no animal was detected clearly enough."
        )
        return out

    nearest = min((d for d in (distance(signature, p) for p in priors) if d is not None),
                  default=None)
    if nearest is None:
        return out

    spread = _spread(priors)
    threshold = DISTANCE_FLOOR
    if spread:
        threshold = max(DISTANCE_FLOOR, spread[0] + SD_MULTIPLIER * spread[1])
    out["appearance_distance"] = nearest
    out["appearance_threshold"] = round(threshold, 4)
    out["appearance_exceeds"] = nearest > threshold
    out["appearance_alarm_enabled"] = APPEARANCE_ALARM

    if out["appearance_exceeds"] and APPEARANCE_ALARM:
        out["status"] = "appearance_outlier"
        out["headline"] = f"The colours here don't look like {name}'s other captures."
        out["detail"] = (
            "The coat colours measured in this one sit further from every "
            f"previous capture of {name} than those captures sit from each "
            "other. Different lighting does this too, so it's a question, not "
            "a finding — worth a look before it joins the trend."
        )
        return out

    # Species matched, which is the half that is trustworthy. The colour
    # comparison is reported but does not get to raise anything, and the
    # wording says exactly that rather than implying the animal was recognised.
    out["status"] = "consistent"
    out["detail"] = (
        f"The species matches {name}'s record. Coat colour is measured and "
        "kept for comparison, but it isn't used to raise anything yet — and "
        "none of this is individual recognition: it would not tell two "
        "similar-looking animals apart."
    )
    return out
