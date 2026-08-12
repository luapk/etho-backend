"""
Breed predisposition context, and the capture plan it drives.

WHAT THIS IS NOT
================
This module never says anything about the animal in front of it. A breed
predisposition is a POPULATION BASE RATE — a fact about a group — and it is
neither measured from this pet nor estimated from their footage. It is a third
kind of claim, and mixing it into either existing column would silently turn
"Cavaliers commonly develop mitral valve disease" into "your Cavalier has
mitral valve disease".

Three rules hold that line, and none of them are negotiable:

1. **Nothing here ever reaches Gemini.** Not Pass 1, not Pass 2. Telling the
   model "this breed is prone to BOAS" makes it see BOAS — the same failure
   mode that got human-keypoint pose estimation switched off. Pass 1 is a
   ground-truth lock and Pass 2 is required to honour it, so a prior injected
   upstream becomes a mandatory hallucination. Breed context lives strictly
   downstream of a finished analysis.

2. **Nothing here ever moves a score.** The moment a distress number reflects
   breed rather than the animal, the pet stops being its own control and the
   entire longitudinal design collapses.

3. **Guardian-confirmed breeds only.** `breed_detected` is the model's guess
   from a video frame. Layering veterinary epidemiology onto a guess compounds
   two error rates and presents the result as knowledge. Callers must pass the
   profile's `breed` field, which a human typed or confirmed.

WHAT IT IS FOR
==============
Two things, in order of value.

**Driving capture.** Most predispositions on this list are invisible to us.
A few are not: cardiac and airway disease both show up in resting respiratory
rate, which `respiration_service.py` already measures, against a published
threshold. So a Cavalier's MMVD risk is not rendered as a warning — it becomes
"film them asleep once a week", which produces a real measurement. A base rate
that generates evidence is worth having; one that only generates worry is not.

**Vet-report context.** A cited appendix, clearly separated from the
observations, so the guardian arrives having asked the right question.

Every entry declares what Etho can observe about it, and entries we can
observe NOTHING about say so explicitly rather than being quietly omitted —
a guardian who reads "Dachshunds are prone to IVDD" needs to know this app
cannot screen for it.

Sources are UK primary-care and breed-club veterinary literature. VetCompass
in particular is UK first-opinion presentation data: geography, era and
referral patterns all apply, cat coverage is thinner than dog, and none of it
is a substitute for an examination.
"""

from .breed_reference import _normalize

REFERENCE_VERSION = "1.0"

# ── What Etho can actually measure, and what it can't ────────────────────────
# Keys used by predisposition entries. Anything not in here is unobservable to
# this tool and must be labelled as such.
OBSERVABLE = {
    "srr": {
        "label": "Sleeping respiratory rate",
        "how": "Measured from chest motion in clips tagged as sleeping.",
        "context": "sleeping_baseline",
        "threshold": "Published home-screening threshold: > 30 breaths/min sustained.",
    },
    "cough": {
        "label": "Cough-like sound events",
        "how": "Counted by the acoustic analysis in any clip with audio.",
        "context": None,
        "threshold": "Heuristic screen — a count, not a diagnosis.",
    },
    "activity": {
        "label": "Activity level",
        "how": "Derived from whole-frame and bounding-box motion in any clip.",
        "context": None,
        "threshold": "Compared against this pet's own history, not a population norm.",
    },
    "weight": {
        "label": "Body weight trend",
        "how": "From weights you log, against typical adult breed range.",
        "context": None,
        "threshold": "Body condition score by a vet remains the clinical standard.",
    },
    "facial": {
        "label": "Facial grimace scoring",
        "how": "Scored from clear, close, front-on stills.",
        "context": None,
        "threshold": "Feline Grimace Scale: published threshold >= 4/10 (cats only).",
    },
}

# Things this tool explicitly cannot screen for, and why. Stated so a
# predisposition never implies coverage we don't have.
_NO_GAIT = ("Etho cannot assess this. Per-limb gait, stride length and "
            "weight-bearing symmetry need animal-trained pose estimation or a "
            "force plate — neither of which this tool has.")
_NO_INTERNAL = ("Etho cannot assess this. It is diagnosed by imaging or "
                "bloodwork, and nothing visible in a video screens for it.")
_NO_AUSCULT = ("Etho cannot hear a heart murmur. What it can track is resting "
               "respiratory rate, which is the standard at-home measure once "
               "heart disease is known about.")

# ── Conformation ─────────────────────────────────────────────────────────────
# Structural vulnerabilities created by breeding for appearance. Applied at the
# conformation level so a breed not on the list still inherits its type's risks.
CONFORMATION = {
    "dog": {
        "brachycephalic": ["french bulldog", "bulldog", "pug", "boston terrier",
                           "boxer", "shih tzu", "cavalier king charles",
                           "pekingese", "lhasa apso"],
        "chondrodystrophic": ["dachshund", "miniature dachshund", "basset hound",
                              "corgi", "shih tzu", "beagle"],
        "giant": ["great dane", "irish wolfhound", "mastiff", "saint bernard",
                  "newfoundland", "bernese mountain", "rottweiler"],
        "sighthound": ["greyhound", "whippet", "saluki", "borzoi"],
    },
    "cat": {
        "brachycephalic": ["persian", "exotic shorthair", "himalayan",
                           "british shorthair", "scottish fold"],
    },
}

CONFORMATION_RISKS = {
    ("dog", "brachycephalic"): [
        {"condition": "Brachycephalic obstructive airway syndrome (BOAS)",
         "category": "respiratory",
         "note": "Shortened skull crowds the soft tissues of the airway. Flat-faced "
                 "breeds show markedly elevated rates of airway and ocular disease "
                 "compared with mesocephalic and crossbred dogs.",
         "observable": ["srr", "cough"],
         "source": "O'Neill et al. (2023), VetCompass, PLOS ONE 18(7): e0288081"},
        {"condition": "Corneal ulceration and eye-surface disease",
         "category": "ocular",
         "note": "Prominent eyes and incomplete blink increase exposure injury.",
         "observable": [],
         "unobservable_reason": "Etho cannot examine the eye surface. Any squinting, "
                                "discharge or rubbing needs a vet the same day.",
         "source": "O'Neill et al. (2022), VetCompass, PLOS ONE 17(1): e0260538"},
        {"condition": "Skin fold dermatitis",
         "category": "dermatological",
         "note": "Facial and tail folds trap moisture.",
         "observable": [],
         "unobservable_reason": "Etho cannot see inside skin folds.",
         "source": "O'Neill et al. (2023), VetCompass, PLOS ONE 18(7): e0288081"},
    ],
    ("dog", "chondrodystrophic"): [
        {"condition": "Intervertebral disc disease (IVDD)",
         "category": "neurological",
         "note": "Long back and shortened limbs load the spine; disc extrusion "
                 "can cause sudden pain or hind-limb weakness.",
         "observable": ["activity"],
         "unobservable_reason": _NO_GAIT,
         "source": "Breed-conformation veterinary literature"},
    ],
    ("dog", "giant"): [
        {"condition": "Gastric dilatation-volvulus (bloat)",
         "category": "emergency",
         "note": "Deep-chested breeds are at risk. Bloat is a surgical emergency "
                 "within hours — retching without producing, a swollen abdomen, "
                 "or sudden restlessness means an emergency vet now, not an app.",
         "observable": [],
         "unobservable_reason": "Etho must never be used to assess a suspected "
                                "bloat. It is time-critical: call an emergency vet "
                                "immediately rather than filming anything.",
         "source": "Breed-conformation veterinary literature"},
        {"condition": "Osteosarcoma and earlier age-related decline",
         "category": "oncological",
         "note": "Larger breeds age biologically faster than small ones, bringing "
                 "age-related disease forward.",
         "observable": ["activity", "weight"],
         "unobservable_reason": _NO_INTERNAL,
         "source": "Canine epigenetic-ageing and body-size literature"},
    ],
}

# ── Breed-specific inherited predispositions ─────────────────────────────────
BREED_RISKS = {
    "dog": {
        "cavalier king charles": [
            {"condition": "Myxomatous mitral valve disease (MMVD), early onset",
             "category": "cardiac",
             "note": "The breed's defining health issue, often appearing years "
                     "earlier than in other breeds.",
             "observable": ["srr", "cough", "activity"],
             "unobservable_reason": _NO_AUSCULT,
             "source": "Breed-specific cardiology literature"},
        ],
        "dachshund": [
            {"condition": "Myxomatous mitral valve disease (MMVD)",
             "category": "cardiac",
             "note": "Common in the breed from middle age.",
             "observable": ["srr", "cough"],
             "unobservable_reason": _NO_AUSCULT,
             "source": "Breed-specific cardiology literature"},
        ],
        "german shepherd": [
            {"condition": "Hip dysplasia and degenerative joint disease",
             "category": "orthopaedic",
             "note": "Polygenic; radiographic scoring schemes exist for breeding stock.",
             "observable": ["activity"],
             "unobservable_reason": _NO_GAIT,
             "source": "Canine hip dysplasia genetics literature"},
            {"condition": "Degenerative myelopathy (SOD1 variants)",
             "category": "neurological",
             "note": "A DNA test exists for the known risk variants.",
             "observable": [],
             "unobservable_reason": _NO_GAIT,
             "source": "SOD1 canine degenerative myelopathy literature"},
        ],
        "labrador": [
            {"condition": "Hip and elbow dysplasia",
             "category": "orthopaedic",
             "note": "Weight control is the single most effective owner-side measure.",
             "observable": ["activity", "weight"],
             "unobservable_reason": _NO_GAIT,
             "source": "Canine hip dysplasia genetics literature"},
        ],
        "doberman": [
            {"condition": "Dilated cardiomyopathy (DCM)",
             "category": "cardiac",
             "note": "Often silent until advanced; screening is by echocardiography "
                     "and Holter monitoring.",
             "observable": ["srr", "activity"],
             "unobservable_reason": _NO_AUSCULT,
             "source": "Canine DCM polygenic-risk literature"},
        ],
        "boxer": [
            {"condition": "Arrhythmogenic cardiomyopathy",
             "category": "cardiac",
             "note": "Screened by Holter monitoring.",
             "observable": ["srr", "activity"],
             "unobservable_reason": _NO_AUSCULT,
             "source": "Canine cardiomyopathy literature"},
        ],
        "great dane": [
            {"condition": "Dilated cardiomyopathy (DCM)",
             "category": "cardiac",
             "note": "Common in giant breeds.",
             "observable": ["srr", "activity"],
             "unobservable_reason": _NO_AUSCULT,
             "source": "Canine DCM literature"},
        ],
    },
    "cat": {
        "maine coon": [
            {"condition": "Hypertrophic cardiomyopathy (HCM)",
             "category": "cardiac",
             "note": "A DNA test exists for known MYBPC3 variants; echocardiography "
                     "is the diagnostic standard.",
             "observable": ["srr", "activity"],
             "unobservable_reason": _NO_AUSCULT,
             "source": "Feline HCM genetics literature"},
        ],
        "ragdoll": [
            {"condition": "Hypertrophic cardiomyopathy (HCM)",
             "category": "cardiac",
             "note": "A breed-specific variant is recognised.",
             "observable": ["srr", "activity"],
             "unobservable_reason": _NO_AUSCULT,
             "source": "Feline HCM genetics literature"},
        ],
        "persian": [
            {"condition": "Polycystic kidney disease (PKD)",
             "category": "renal",
             "note": "A DNA test exists; ultrasound confirms.",
             "observable": ["weight", "activity"],
             "unobservable_reason": _NO_INTERNAL,
             "source": "Feline PKD genetics literature"},
        ],
        "british shorthair": [
            {"condition": "Hypertrophic cardiomyopathy (HCM)",
             "category": "cardiac",
             "note": "Recognised in the breed.",
             "observable": ["srr"],
             "unobservable_reason": _NO_AUSCULT,
             "source": "Feline HCM literature"},
        ],
        "sphynx": [
            {"condition": "Hypertrophic cardiomyopathy (HCM)",
             "category": "cardiac",
             "note": "Recognised in the breed.",
             "observable": ["srr"],
             "unobservable_reason": _NO_AUSCULT,
             "source": "Feline HCM literature"},
        ],
    },
}

DISCLAIMER = (
    "Population context only. These are conditions reported more often in this "
    "breed than in the general population — NOT findings about this animal, and "
    "not a prediction. Most pets of any breed never develop their breed's "
    "typical conditions. Nothing here is derived from this pet's footage."
)


def _match(table: dict, breed: str):
    """Substring match both ways, mirroring breed_reference.find_reference so a
    breed resolves the same way in both modules."""
    b = _normalize(breed)
    if not b:
        return None
    if b in table:
        return b
    for key in table:
        if key in b:
            return key
    for key in table:
        if b in key:
            return key
    return None


def conformations(species: str, breed: str) -> list:
    """Conformation types this breed belongs to (a breed can have several —
    a Shih Tzu is both brachycephalic and chondrodystrophic)."""
    b = _normalize(breed)
    if not b:
        return []
    found = []
    for conf, breeds in CONFORMATION.get(_normalize(species), {}).items():
        if any(k in b or b in k for k in breeds):
            found.append(conf)
    return found


def lookup(species: str, breed: str) -> dict:
    """Population predispositions for a GUARDIAN-CONFIRMED breed.

    Returns an empty result for an unknown or missing breed rather than
    guessing — silence is the correct output when we don't know the breed.
    """
    sp = _normalize(species)
    out = {
        "breed": breed or None,
        "species": species,
        "matched": None,
        "conformations": [],
        "predispositions": [],
        "disclaimer": DISCLAIMER,
        "reference_version": REFERENCE_VERSION,
    }
    if not breed:
        return out

    risks = []
    confs = conformations(sp, breed)
    out["conformations"] = confs
    for conf in confs:
        risks.extend(CONFORMATION_RISKS.get((sp, conf), []))

    key = _match(BREED_RISKS.get(sp, {}), breed)
    if key:
        out["matched"] = key
        risks.extend(BREED_RISKS[sp][key])

    # De-duplicate by condition (a breed can inherit the same risk twice).
    seen = set()
    for r in risks:
        if r["condition"] not in seen:
            seen.add(r["condition"])
            out["predispositions"].append(r)
    return out


def suggest_breed(history: list, min_agreement: int = 2):
    """The breed the model keeps detecting, offered for a human to confirm.

    This is the ONLY sanctioned use of `breed_detected`: as a suggestion a
    guardian ratifies, never as an input to breed context. Requires agreement
    across several analyses, because one confident guess from one frame is
    exactly the kind of thing that shouldn't become a profile fact.

    Returns (breed, times_seen) or (None, 0).
    """
    counts = {}
    for h in history or []:
        b = (h.get("breed_detected") or "").strip()
        if not b or b.lower() in ("unknown", "mixed", "n/a"):
            continue
        counts[b] = counts.get(b, 0) + 1
    if not counts:
        return None, 0
    breed, seen = max(counts.items(), key=lambda kv: kv[1])
    return (breed, seen) if seen >= min_agreement else (None, 0)


def capture_plan(species: str, breed: str, history: list = None) -> dict:
    """What is worth filming for THIS pet, and why.

    The whole point of the module. Rather than warning a guardian about a
    condition, work out which measurements Etho actually has that relate to it,
    and ask for the footage that produces them. A prior that generates evidence
    earns its place; one that only generates worry does not.

    `history` (rows from pet_store.get_history) is used to skip suggestions the
    guardian is already acting on and to say when a measurement last happened.
    """
    history = history or []
    ctx = lookup(species, breed)
    plan = []

    wanted = {}
    for risk in ctx["predispositions"]:
        for obs in risk.get("observable", []):
            wanted.setdefault(obs, []).append(risk["condition"])

    # Sleeping clips: the highest-value ask, because SRR is a real measurement
    # against a published threshold and it is the at-home screen for exactly
    # the cardiac and airway conditions that dominate this list.
    if "srr" in wanted:
        srr_rows = [h for h in history if h.get("resp_rate_bpm") is not None]
        last = srr_rows[-1]["created_at"] if srr_rows else None
        plan.append({
            "id": "sleeping_clip",
            "priority": 1,
            "action": "Film them asleep, about a minute, camera propped still",
            "why": ("Their breed is associated with " + _join(wanted["srr"]) +
                    ". Etho can't hear a heart or see inside a chest — but "
                    "resting breathing rate is the measurement vets ask owners "
                    "to take at home for exactly these conditions, and it needs "
                    "them properly asleep."),
            "measures": OBSERVABLE["srr"]["label"],
            "threshold": OBSERVABLE["srr"]["threshold"],
            "context_tag": "sleeping_baseline",
            "last_measured": last,
            "done_count": len(srr_rows),
        })

    if "weight" in wanted:
        plan.append({
            "id": "weight_log",
            "priority": 2,
            "action": "Log their weight monthly",
            "why": ("Weight trend is one of the clearest signals in " +
                    _join(wanted["weight"]) + ", and it's the measure an owner "
                    "can influence most directly."),
            "measures": OBSERVABLE["weight"]["label"],
            "threshold": OBSERVABLE["weight"]["threshold"],
            "context_tag": None,
            "last_measured": None,
            "done_count": 0,
        })

    # Baseline video is worth asking for regardless of breed: everything
    # longitudinal depends on knowing what this animal's ordinary day looks like.
    baseline_rows = [h for h in history if h.get("context") == "weekly_baseline"]
    plan.append({
        "id": "weekly_baseline",
        "priority": 3 if wanted else 1,
        "action": "A short clip of an ordinary day, weekly",
        "why": ("Everything else is measured against their own normal, so the "
                "normal has to be recorded first."),
        "measures": "Distress baseline, activity level, vocal acoustics",
        "threshold": "Compared only against this pet's own history.",
        "context_tag": "weekly_baseline",
        "last_measured": baseline_rows[-1]["created_at"] if baseline_rows else None,
        "done_count": len(baseline_rows),
    })

    plan.sort(key=lambda p: p["priority"])
    suggested, seen = (None, 0)
    if not ctx["breed"]:
        suggested, seen = suggest_breed(history)

    return {
        "breed_known": bool(ctx["breed"]),
        "breed": ctx["breed"],
        # Offered for confirmation, never used as though it were confirmed.
        "breed_suggestion": ({"breed": suggested, "seen_in": seen}
                             if suggested else None),
        "conformations": ctx["conformations"],
        "driven_by_breed": bool(wanted),
        "plan": plan,
        "note": ("Suggestions are based on conditions reported more often in "
                 "this breed. They are not a claim about this pet."),
        "reference_version": REFERENCE_VERSION,
    }


def _join(items: list) -> str:
    """'A', 'A and B', 'A, B and C' — conditions read as prose, not a list."""
    items = list(dict.fromkeys(items))
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]
