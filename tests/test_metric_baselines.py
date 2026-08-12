"""Each measured metric against the pet's own history.

The problem this solves: cats suppress pain display around observers, so no
single clip catches them out. What leaks is the drift. Absolute published
thresholds (FGS ≥ 4/10, SRR > 30/min) only fire once an animal is ALREADY past
a cut-off — a stoic cat running 0, 0, 0, 2, 2, 3 on the grimace scale never
reaches 4, and before this the record said nothing at all.

The rules under test, all four of which exist to stop this becoming an alarm
machine:

  1. Only the clinically concerning direction raises. A calmer cat is not a
     finding, and neither is a MORE active dog.
  2. Statistical unusualness is not enough. A pet with a very consistent
     history has a tiny SD, so trivia sits several SD out — the change must
     also clear a floor in real units.
  3. Where a published absolute threshold exists it is quoted alongside,
     including (especially) when the pet is still under it.
  4. Instruments with different maximums never share a baseline.
"""
import sys, types, os, tempfile
from datetime import datetime, timedelta, timezone

for n in ['google', 'google.generativeai']:
    sys.modules[n] = types.ModuleType(n)
sys.modules['google'].generativeai = sys.modules['google.generativeai']
os.environ['DATA_DIR'] = tempfile.mkdtemp()

from app.services import pet_store

pet_store.init_db()

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  PASS {name}")
    else:
        fail += 1
        print(f"  FAIL {name} {detail}")


def hist(key, values, instrument=None, start_days_ago=60):
    """A synthetic history, oldest first, one observation a week."""
    t0 = datetime.now(timezone.utc) - timedelta(days=start_days_ago)
    rows = []
    for i, v in enumerate(values):
        row = {"created_at": (t0 + timedelta(days=7 * i)).isoformat(), key: v}
        if instrument:
            row["instrument"] = instrument
        rows.append(row)
    return rows


def metric(rows, key):
    return next((m for m in pet_store.compute_metric_trends(rows) if m["key"] == key), None)


FGS = "feline_grimace_scale"

# ── The reported scenario: a stoic cat, never past the published cut-off ─────
stoic = metric(hist("instrument_total", [0, 0, 0, 1, 0, 3], FGS), "instrument_total")
check("a masking cat's rise IS caught", stoic and stoic["flag"], stoic)
check("it reports the change against their own normal",
      "their usual" in stoic["reading"])
check("it quotes the published threshold it has NOT crossed",
      "Still below 4" in stoic["reading"] and "4/10" in stoic["reading"], stoic["reading"])
check("the instrument is labelled AI-estimated, not measured",
      stoic["kind"] == "ai_estimated")

# Same cat, still perfectly flat: nothing to say.
flat = metric(hist("instrument_total", [0, 0, 0, 0, 0, 0], FGS), "instrument_total")
check("a flat history raises nothing", flat and not flat["flag"])

# ── Guard 1: direction ───────────────────────────────────────────────────────
improving = metric(hist("instrument_total", [4, 4, 3, 4, 4, 0], FGS), "instrument_total")
check("a cat getting BETTER is never flagged", improving and not improving["flag"],
      improving)

sleepier = metric(hist("activity_level", [30, 28, 31, 29, 30, 9]), "activity_level")
check("a drop in activity is flagged (lethargy)", sleepier and sleepier["flag"], sleepier)
livelier = metric(hist("activity_level", [30, 28, 31, 29, 30, 90]), "activity_level")
check("a jump in activity is not", livelier and not livelier["flag"])
check("activity watches the downward direction", sleepier["concern"] == "down")

# ── Guard 2: a floor in real units ───────────────────────────────────────────
# Perfectly consistent history, then a trivial move. Several SD out and
# clinically nothing — this is the false alarm the floor exists to stop.
trivial = metric(hist("resp_rate_bpm", [18, 18, 17, 18, 18, 20]), "resp_rate_bpm")
check("a tiny move on a tight history does not raise",
      trivial and not trivial["flag"], trivial)
check("...even though it is statistically extreme",
      trivial and abs(trivial["deviation_sigma"]) >= 1.5, trivial)
check("the floor is the measurement error, and it is reported",
      trivial and trivial["min_change"] == 4.0)

# A perfectly flat history has no SD to compare against. The most consistent
# animals must not become the ones nothing can be detected in.
flatthen = metric(hist("resp_rate_bpm", [18, 18, 18, 18, 18, 36]), "resp_rate_bpm")
check("a flat history still catches a real jump", flatthen and flatthen["flag"], flatthen)
check("it does not pretend to a sigma it cannot compute",
      flatthen and flatthen["deviation_sigma"] is None)
check("and it says so in words instead",
      "every one of which was the same figure" in flatthen["reading"], flatthen["reading"])
check("a flat history still ignores a trivial move",
      not metric(hist("resp_rate_bpm", [18, 18, 18, 18, 18, 20]), "resp_rate_bpm")["flag"])

real = metric(hist("resp_rate_bpm", [18, 17, 19, 18, 18, 27]), "resp_rate_bpm")
check("a real rise in breathing rate raises", real and real["flag"], real)
check("SRR is labelled measured", real["kind"] == "measured")
check("it says the pet is still under the published 30/min",
      "Still below 30" in real["reading"], real["reading"])

past = metric(hist("resp_rate_bpm", [18, 17, 19, 18, 18, 36]), "resp_rate_bpm")
check("past the threshold, it says so instead",
      "past 30" in past["reading"], past["reading"])

# ── Guard 3: enough history, or nothing ──────────────────────────────────────
check("two observations are not a baseline",
      metric(hist("resp_rate_bpm", [18, 30]), "resp_rate_bpm") is None)
check("no observations, no metric",
      metric(hist("resp_rate_bpm", []), "resp_rate_bpm") is None)
check("a metric that was never recorded is absent, not zero",
      metric(hist("resp_rate_bpm", [18, 18, 18, 25]), "activity_level") is None)

# ── Guard 4: instruments with different maximums never mix ───────────────────
mixed = hist("instrument_total", [1, 1, 1], FGS) + hist("instrument_total", [9, 9, 9],
                                                        "glasgow_cmps_sf_subset")
got = metric(mixed, "instrument_total")
check("only rows on the latest instrument are compared",
      got is None or got["n"] == 2, got)

# ── Slope ────────────────────────────────────────────────────────────────────
climbing = metric(hist("cough_like_count", [0, 1, 2, 3, 4, 6]), "cough_like_count")
check("a rising cough count is flagged", climbing and climbing["flag"])
check("the slope is reported in units per week",
      climbing.get("slope_per_week", 0) > 0, climbing)

# ── It never diagnoses, and never invents a score ────────────────────────────
for m in pet_store.compute_metric_trends(
        hist("instrument_total", [0, 0, 0, 1, 0, 3], FGS)):
    lower = m["reading"].lower()
    check("no diagnosis language in the reading",
          not any(w in lower for w in ("disease", "diagnos", "suffering",
                                       "likely has", "indicates that")),
          m["reading"])
    check("no combined risk score is produced",
          not any(k in m for k in ("risk", "risk_score", "combined")))

# ── It reaches the trends payload and the red flags ──────────────────────────
pet = pet_store.create_pet({"name": "Stoic", "species": "cat"})
base = datetime.now(timezone.utc) - timedelta(days=42)
for i, (fgs, resp) in enumerate([(0, 18), (0, 17), (0, 19), (1, 18), (0, 18), (3, 27)]):
    aid = pet_store.log_analysis(
        pet["id"],
        {"overall_assessment": {"distress_score": 20, "zone": "green"},
         "instrument_scores": {"instrument": FGS, "total": fgs, "max_total": 10,
                               "items_scorable": 5},
         "_respiration": {"usable": True, "breaths_per_min": resp, "confidence": "high"}},
        media_type="video",
        observed_at=(base + timedelta(days=7 * i)).isoformat())

t = pet_store.compute_trends(pet["id"])
keys = {m["key"] for m in t["metrics"]}
check("trends carries per-metric baselines", {"instrument_total", "resp_rate_bpm"} <= keys, keys)
types_ = {f["type"] for f in t["red_flags"]}
check("a baseline change becomes a red flag",
      "instrument_total_baseline" in types_ and "resp_rate_bpm_baseline" in types_, types_)
check("the distress baseline still works as before",
      t["baseline"] is not None and t["latest"] is not None)
check("no absolute-threshold flag fired for this cat",
      "fgs_threshold" not in types_ and "srr_threshold" not in types_,
      "the whole point: they never crossed either published cut-off")

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
