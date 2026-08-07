"""
Breed weight reference and screening assessment.

Compares a pet's recorded weight against typical adult ranges for their
breed. IMPORTANT FRAMING: this is a screening aid, not a clinical judgement.
Published breed ranges are broad, sex- and build-dependent, and say nothing
about an individual's frame. The clinical standard is Body Condition Score
(BCS, 9-point scale) assessed hands-on by a vet — every output of this
module says so. A pet can be within breed range and overweight for their
frame, or outside it and perfectly healthy.

Ranges are typical adult weights in kg (sexes combined; males usually sit in
the upper half). Sources: breed-club and veterinary reference ranges,
rounded conservatively.
"""

REFERENCE_VERSION = "1.0"

# species -> normalized breed key -> (min_kg, max_kg)
BREED_WEIGHT_KG = {
    "dog": {
        "labrador": (25, 36), "golden retriever": (25, 34),
        "german shepherd": (22, 40), "french bulldog": (8, 14),
        "bulldog": (18, 25), "beagle": (8, 14),
        "standard poodle": (18, 32), "miniature poodle": (5, 9),
        "toy poodle": (2, 4), "chihuahua": (1.5, 3),
        "dachshund": (7, 15), "miniature dachshund": (4, 6),
        "yorkshire terrier": (2, 3.2), "shih tzu": (4, 7.5),
        "pomeranian": (1.4, 3.2), "cavalier king charles": (5.9, 8.2),
        "border collie": (12, 20), "australian shepherd": (16, 32),
        "cocker spaniel": (12, 16), "boxer": (25, 32),
        "rottweiler": (35, 60), "doberman": (27, 45),
        "great dane": (45, 90), "husky": (16, 27),
        "corgi": (10, 14), "jack russell": (6, 8),
        "maltese": (3, 4), "pug": (6, 8),
        "boston terrier": (5.4, 11), "bernese mountain": (31, 52),
        "staffordshire bull terrier": (11, 17), "pit bull": (14, 27),
        "shiba inu": (8, 10), "akita": (32, 59),
        "whippet": (11, 19), "greyhound": (27, 40),
        "samoyed": (16, 30), "bichon frise": (5.4, 8.2),
        "havanese": (3.2, 6), "springer spaniel": (18, 25),
    },
    "cat": {
        "domestic shorthair": (3.5, 5.5), "domestic longhair": (3.5, 5.5),
        "siamese": (2.5, 5.5), "maine coon": (4, 8.5),
        "persian": (3, 5.5), "ragdoll": (4.5, 9),
        "bengal": (3.6, 6.8), "british shorthair": (3.2, 7.7),
        "sphynx": (3.5, 5), "russian blue": (3.5, 6),
        "abyssinian": (3, 5), "scottish fold": (2.7, 6),
        "norwegian forest": (3.6, 9), "burmese": (3, 6),
        "devon rex": (2.3, 4.5), "oriental": (3, 5.5),
    },
}

# Species-level fallback when the breed is unknown/unmatched. Cats cluster
# tightly enough for a useful default; dogs (1.5-90 kg across breeds) do not.
SPECIES_FALLBACK_KG = {"cat": (3.5, 5.5)}

_BCS_NOTE = (
    "Breed ranges are a rough screen only — body condition score (BCS) "
    "assessed hands-on by a vet is the definitive measure."
)


def _normalize(text: str) -> str:
    return "".join(c for c in (text or "").lower() if c.isalnum() or c == " ").strip()


def find_reference(species: str, breed: str):
    """Match a breed string to a reference range. Substring match both ways so
    'Labrador Retriever' hits 'labrador' and 'poodle' hits 'standard poodle'
    only when exact keys fail. Returns (matched_key, (min,max)) or (None, None)."""
    table = BREED_WEIGHT_KG.get(_normalize(species), {})
    b = _normalize(breed)
    if not b:
        return None, None
    if b in table:
        return b, table[b]
    for key, rng in table.items():
        if key in b:
            return key, rng
    for key, rng in table.items():
        if b in key:
            return key, rng
    return None, None


def assess_weight(species: str, breed: str, weight_kg) -> dict:
    """Screening comparison of weight vs typical adult breed range.
    Never diagnoses; always points to BCS."""
    if weight_kg is None:
        return {"status": "no_weight_recorded", "note": _BCS_NOTE,
                "reference_version": REFERENCE_VERSION}

    matched, rng = find_reference(species, breed)
    source = "breed"
    if rng is None:
        rng = SPECIES_FALLBACK_KG.get(_normalize(species))
        source = "species_typical" if rng else None
    if rng is None:
        return {"status": "no_reference",
                "weight_kg": weight_kg,
                "note": ("No reference range for this breed — mixed or uncommon "
                         "breeds vary too widely for a useful screen. " + _BCS_NOTE),
                "reference_version": REFERENCE_VERSION}

    lo, hi = rng
    if weight_kg < lo:
        status = "below_range"
        pct = round((lo - weight_kg) / lo * 100, 1)
    elif weight_kg > hi:
        status = "above_range"
        pct = round((weight_kg - hi) / hi * 100, 1)
    else:
        status = "within_range"
        pct = 0.0

    return {
        "status": status,
        "weight_kg": weight_kg,
        "reference_range_kg": [lo, hi],
        "reference_source": source,
        "matched_breed": matched,
        "percent_outside_range": pct,
        "note": ("Typical adult range, sexes combined (males usually upper "
                 "half). " + _BCS_NOTE),
        "reference_version": REFERENCE_VERSION,
    }
