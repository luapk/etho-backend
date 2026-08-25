"""Visible body findings — the channel that was missing entirely.

Found in real testing: a dachshund with a markedly swollen face was analysed
and nothing was reported. The cause was architectural, not a tuning miss.

  1. Pass 1 asked about posture, position, framing and objects. Nothing asked
     what the ANIMAL looked like.
  2. Pass 2's schema had no field for a physical finding — every slot was
     behaviour, emotion or a pain instrument.
  3. The two-pass hallucination guard then made it certain: Pass 1 is a
     ground-truth lock that Pass 2 must honour, so a thing Pass 1 was never
     asked to look for is a thing Pass 2 is FORBIDDEN to raise.

And the reason it matters more than a missed feature: behaviour and body come
apart. A dog with a swollen face can wag, eat and play, so on behaviour alone
the tool returns green and actively reassures the guardian. That is the
false-reassurance failure, and it is the one that harms.
"""
import sys, types, os, tempfile

for n in ['google', 'google.generativeai']:
    sys.modules[n] = types.ModuleType(n)
sys.modules['google'].generativeai = sys.modules['google.generativeai']
os.environ.setdefault('DATA_DIR', tempfile.mkdtemp())

from app.services.gemini_service import (
    normalise_physical_observations, enforce_image_mode, _is_urgent_finding)
from app.prompts.ethological_prompt import ETHOLOGICAL_SYSTEM_PROMPT, PROMPT_VERSION

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  PASS {name}")
    else:
        fail += 1
        print(f"  FAIL {name} {detail}")


def result(obs, urgency="routine", score=15, zone="green"):
    return {
        "physical_observations": obs,
        "overall_assessment": {"distress_score": score, "zone": zone},
        "advisory": {"headline": "Continue monitoring", "urgency": urgency},
    }


SWOLLEN = {"finding": "Marked swelling of the left muzzle and below the left eye",
           "location": "left side of face", "asymmetric": True, "confidence": "high"}

# ── The reported case: a happy dog with a swollen face ───────────────────────
r = normalise_physical_observations(result([SWOLLEN]))
check("the finding survives", len(r["physical_observations"]) == 1)
check("facial swelling is urgent even without the model saying so",
      r["physical_observations"][0]["urgent"] is True)
check("urgency is floored at critical", r["advisory"]["urgency"] == "critical")
check("the distress score is NOT touched",
      r["overall_assessment"]["distress_score"] == 15
      and r["overall_assessment"]["zone"] == "green",
      "a fact about the body must not be laundered into a mood reading")
check("the advisory says how many findings there were",
      r["advisory"]["physical_finding_count"] == 1 and r["advisory"]["physical_urgent"] is True)

# ── The model's own flag is honoured too — two independent paths ─────────────
odd = {"finding": "Something that does not match any keyword", "urgent": True}
check("the model's urgent flag alone escalates",
      normalise_physical_observations(result([odd]))["advisory"]["urgency"] == "critical")

# ── Non-urgent findings still get a vet mention ──────────────────────────────
mild = {"finding": "Small bald patch on the right flank", "location": "right flank"}
m = normalise_physical_observations(result([mild]))
check("an ordinary finding is not marked urgent", m["physical_observations"][0]["urgent"] is False)
check("but it still lifts urgency to elevated", m["advisory"]["urgency"] == "elevated")

# ── A higher urgency set by the model is never lowered ───────────────────────
keep = normalise_physical_observations(result([mild], urgency="critical"))
check("an existing critical is never downgraded", keep["advisory"]["urgency"] == "critical")

# ── No findings changes nothing ──────────────────────────────────────────────
none = normalise_physical_observations(result([]))
check("no findings leaves urgency alone", none["advisory"]["urgency"] == "routine")
check("no findings adds no counters", "physical_finding_count" not in none["advisory"])
check("a missing key becomes an empty list, not None",
      normalise_physical_observations({"advisory": {}})["physical_observations"] == [])
check("junk entries are dropped",
      normalise_physical_observations(
          result(["a string", {}, {"finding": "   "}, SWOLLEN]))["physical_observations"]
      == [dict(SWOLLEN, urgent=True)])

# ── Every urgent presentation is actually matched ────────────────────────────
for phrase in ("swollen face", "laboured breathing", "distended abdomen", "collapse",
               "active bleeding", "not bearing weight", "straining to urinate",
               "pale gums", "bulging eye", "seizure"):
    check(f"'{phrase}' escalates", _is_urgent_finding({"finding": f"Dog shows {phrase}"}))

check("an ordinary finding does not escalate",
      not _is_urgent_finding({"finding": "Slightly dirty ears"}))

# ── A photo must keep them: it is often the BEST evidence ────────────────────
img = enforce_image_mode(result([SWOLLEN]))
check("image mode keeps physical findings", len(img["physical_observations"]) == 1,
      "an owner photographs the thing that looks wrong — a still is the evidence")
check("image mode still strips audio", img["audio_analysis"]["vocalizations_detected"] == []
      if img.get("audio_analysis") else True)

# ── The prompt asks, and asks correctly ──────────────────────────────────────
check("prompt version bumped for the schema change",
      tuple(int(x) for x in PROMPT_VERSION.split(".")) >= (6, 6), PROMPT_VERSION)
check("prompt has a physical observations section",
      "PHYSICAL OBSERVATIONS" in ETHOLOGICAL_SYSTEM_PROMPT)
check("prompt forbids diagnosing",
      "DESCRIBE, NEVER DIAGNOSE" in ETHOLOGICAL_SYSTEM_PROMPT)
check("prompt protects breed-normal conformation",
      "BREED-NORMAL ANATOMY IS NOT A FINDING" in ETHOLOGICAL_SYSTEM_PROMPT)
check("prompt says an empty list is the normal answer",
      "RETURN AN EMPTY LIST" in ETHOLOGICAL_SYSTEM_PROMPT)
check("prompt keeps findings out of the distress score",
      "independent of the distress score" in ETHOLOGICAL_SYSTEM_PROMPT.lower())
check("prompt tells it to compare left with right",
      "COMPARE LEFT WITH RIGHT" in ETHOLOGICAL_SYSTEM_PROMPT)
check("prompt names facial swelling as urgent",
      "Swelling of the face" in ETHOLOGICAL_SYSTEM_PROMPT)

# Pass 1 is the lock. If it does not look, Pass 2 may not report.
import inspect
from app.services import gemini_service
src = inspect.getsource(gemini_service.run_scene_verification)
check("Pass 1 asks about body condition for VIDEO and IMAGE",
      src.count("visible_body_condition") == 2, src.count("visible_body_condition"))
check("Pass 1 also warns off breed-normal anatomy",
      "Breed-normal anatomy is NOT a finding" in src)

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
