"""Trend wording for pet parents, and still-image mode.

Two rules under test:

  1. A trend reading must never alarm a guardian whose pet has never left the
     calm band, and must never call ordinary variation a trend.
  2. A photograph must not produce claims that require duration or sound.
"""
import sys, types, os, tempfile

for n in ['google', 'google.generativeai']:
    sys.modules[n] = types.ModuleType(n)
sys.modules['google'].generativeai = sys.modules['google.generativeai']
os.environ['DATA_DIR'] = tempfile.mkdtemp()

from datetime import datetime, timedelta, timezone
from app.services import pet_store
from app.services.gemini_service import enforce_image_mode

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  PASS {name}")
    else:
        fail += 1
        print(f"  FAIL {name} {detail}")


R = pet_store._trend_reading


def slope_block(pts_week, span, exceeds):
    return {"points_per_week": pts_week, "span_weeks": span,
            "total_change": pts_week * span, "exceeds_variation": exceeds,
            "direction": "rising" if pts_week > 1 else "easing" if pts_week < -1 else "steady",
            "n": 6}


# ── The reported complaint: rising line, everything green ──
calm_rising = R([10, 14, 18, 22, 26, 30], slope_block(3.0, 6, True))
check("calm band never says worsening",
      "worsen" not in (calm_rising["headline"] + calm_rising["detail"]).lower(),
      calm_rising)
check("calm band keeps a calm tone", calm_rising["tone"] == "calm", calm_rising)
check("calm band still mentions the rise",
      "up" in calm_rising["detail"].lower(), calm_rising)
check("calm band reassures explicitly",
      "calm range" in calm_rising["detail"], calm_rising)

# ── Flat and calm ──
settled = R([12, 15, 11, 14, 13, 12], slope_block(0.1, 6, False))
check("settled reads as settled", settled["headline"] == "Settled", settled)
check("settled is calm", settled["tone"] == "calm")

# ── Drift smaller than the pet's own variation is not a trend ──
noise = R([10, 30, 12, 28, 15, 25], slope_block(1.5, 6, False))
check("sub-variation drift isn't called a trend",
      noise["headline"] == "Settled", noise)

# ── Genuine rise into the moderate band ──
moderate = R([20, 30, 38, 45, 52, 58], slope_block(6.0, 6, True))
check("moderate rise is flagged", moderate["headline"] == "Trending up", moderate)
check("moderate rise is watch, not attention", moderate["tone"] == "watch", moderate)
check("moderate rise still avoids 'worsening'",
      "worsen" not in moderate["detail"].lower())

# ── Elevated is never softened ──
elevated = R([30, 45, 60, 70, 75, 80], slope_block(9.0, 6, True))
check("elevated says elevated", elevated["headline"] == "Elevated", elevated)
check("elevated demands attention", elevated["tone"] == "attention", elevated)

# An elevated recent reading outranks a falling slope.
falling_but_high = R([95, 90, 85, 80, 75, 72], slope_block(-4.0, 6, True))
check("falling slope doesn't hide a red reading",
      falling_but_high["tone"] == "attention", falling_but_high)

# ── Improvement is allowed to sound like good news ──
easing = R([60, 52, 45, 40, 36, 34], slope_block(-5.0, 6, True))
check("easing reads as easing", easing["headline"] == "Easing", easing)
check("easing is calm", easing["tone"] == "calm")

# ── Too little data ──
thin = R([20, 25, 22], None)
check("thin history says so", thin["headline"] == "Building their picture", thin)
check("thin history is calm", thin["tone"] == "calm")
thin_red = R([20, 25, 90], None)
check("thin history still surfaces an elevated reading",
      thin_red["tone"] == "attention", thin_red)
check("no observations is safe", R([])["tone"] == "calm")

# ── No reading anywhere may use the scary word ──
for name, rd in [("calm_rising", calm_rising), ("settled", settled),
                 ("moderate", moderate), ("elevated", elevated),
                 ("easing", easing), ("thin", thin)]:
    text = (rd["headline"] + " " + rd["detail"]).lower()
    check(f"{name} avoids 'worsening'/'deteriorat'",
          "worsen" not in text and "deteriorat" not in text, text)

# ── compute_trends wires the reading in ──
pet_store.init_db()
pet = pet_store.create_pet({"name": "Reading Test", "species": "dog"})
base = datetime.now(timezone.utc) - timedelta(weeks=6)
for i, score in enumerate([10, 14, 18, 22, 26, 30]):
    pet_store.log_analysis(
        pet["id"], {"overall_assessment": {"distress_score": score, "zone": "green"}},
        media_type="video", source_filename=f"{i}.mp4", file_size_bytes=1,
        observed_at=(base + timedelta(weeks=i)).isoformat(),
    )
t = pet_store.compute_trends(pet["id"])
check("trends carry a reading", isinstance(t.get("reading"), dict))
check("slope direction is neutral wording",
      t["slope"]["direction"] in ("rising", "easing", "steady"), t["slope"])
check("slope reports total change", "total_change" in t["slope"])
check("slope reports whether it beats variation", "exceeds_variation" in t["slope"])
check("all-green history reads calm", t["reading"]["tone"] == "calm", t["reading"])

# ── Image mode is enforced, not merely requested ──
# A model handed a photo but still emitting video-shaped output.
bad = {
    "audio_analysis": {
        "vocalizations_detected": [{"type": "bark", "timestamp": "0:03"}],
        "environmental_sounds": ["door closing"],
        "solicitation_purr_detected": True,
    },
    "timeline": [
        {"timestamp": "0:00", "distress_score": 30, "zone": "green"},
        {"timestamp": "0:05", "distress_score": 55, "zone": "yellow"},
        {"timestamp": "0:11", "distress_score": 70, "zone": "red"},
    ],
    "interpret_lines": [
        {"timestamp": "0:02", "pet_pov": "Something moved over there"},
        {"timestamp": "0:09", "pet_pov": "I want to leave now"},
    ],
    "video_type": "single_shot",
}
clean = enforce_image_mode(bad)
check("invented vocalizations removed",
      clean["audio_analysis"]["vocalizations_detected"] == [])
check("invented environmental sounds removed",
      clean["audio_analysis"]["environmental_sounds"] == [])
check("purr claim cleared", clean["audio_analysis"]["solicitation_purr_detected"] is False)
check("absence of audio is explained", "no audio" in
      clean["audio_analysis"]["not_applicable"].lower())
check("timeline collapsed to one moment", len(clean["timeline"]) == 1, clean["timeline"])
check("timeline stamped at zero", clean["timeline"][0]["timestamp"] == "0:00")
check("the surviving entry is the first, not a fabricated blend",
      clean["timeline"][0]["distress_score"] == 30)
check("one POV line only", len(clean["interpret_lines"]) == 1)
check("POV line stamped at zero", clean["interpret_lines"][0]["timestamp"] == "0:00")
check("media type corrected", clean["video_type"] == "single_image")

# Already-correct output must pass through untouched.
good = {"audio_analysis": {"vocalizations_detected": [], "environmental_sounds": [],
                           "solicitation_purr_detected": False},
        "timeline": [{"timestamp": "0:00", "distress_score": 21, "zone": "green"}],
        "interpret_lines": [{"timestamp": "0:00", "pet_pov": "This spot is warm"}]}
out = enforce_image_mode(dict(good))
check("valid still output survives", out["timeline"] == good["timeline"]
      and out["interpret_lines"] == good["interpret_lines"])

# Missing sections must not crash the clamp.
check("empty result is safe", enforce_image_mode({})["video_type"] == "single_image")
check("null sections are safe",
      enforce_image_mode({"timeline": [], "audio_analysis": None})["timeline"] == [])

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
