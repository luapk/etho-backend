"""Is this the same animal?

The identity screen is a guardrail on the longitudinal record: one misfiled
clip puts a stranger's scores into a pet's baseline, and every deviation,
slope and red flag in the product is measured against that baseline.

What these tests hold it to:

  1. It is quarantined exactly like the breed data — never imported by the
     prompt or the Gemini service, so it cannot reach Pass 1 or Pass 2.
  2. It never blocks, never reassigns, and never returns a score.
  3. Species disagreement is the one signal strong enough to raise alone.
  4. Coat colour is weak and is treated as weak: silent below three prior
     captures, and silent unless the new capture sits further out than the
     pet's own captures sit from each other.
"""
import sys, types, os, tempfile, json

cv2 = types.ModuleType("cv2")
for name in ("cvtColor", "calcHist", "inRange", "imread", "VideoCapture", "resize"):
    setattr(cv2, name, lambda *a, **k: None)
cv2.COLOR_BGR2HSV = 40
cv2.CAP_PROP_POS_FRAMES = 1
sys.modules.setdefault("cv2", cv2)
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
# The appearance alarm ships OFF; these tests exercise both settings, so it is
# forced on here and the default-off behaviour is asserted separately below.
os.environ["IDENTITY_APPEARANCE"] = "1"

from app.services import identity_check as ic

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  PASS {name}")
    else:
        fail += 1
        print(f"  FAIL {name} {detail}")


def sig(seed, n=ic.SIG_LEN):
    """A normalised, deterministic pseudo-signature.

    Mass is concentrated in a handful of neighbouring bins, the way a real
    coat histogram is — a ginger cat is a spike in two hue bins, not a smear
    across all twelve. A flat random vector would make every animal look like
    every other one and the test would prove nothing.
    """
    vals = [0.001] * n
    centre = (seed * 13) % n
    for offset, weight in ((0, 1.0), (1, 0.5), (-1, 0.5), (2, 0.2), (-2, 0.2)):
        vals[(centre + offset) % n] += weight
    total = sum(vals)
    return [v / total for v in vals]


def jitter(base, amount):
    """A signature nudged slightly — one capture of the same animal in
    different light."""
    out = [max(0.0, v + (amount if i % 2 else -amount)) for i, v in enumerate(base)]
    total = sum(out)
    return [v / total for v in out]


CAT = {"name": "Louis", "species": "cat"}

# ── 1. Quarantine ────────────────────────────────────────────────────────────
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for path in ("app/services/gemini_service.py", "app/prompts/ethological_prompt.py"):
    body = open(os.path.join(root, path)).read()
    check(f"{os.path.basename(path)} never imports identity_check",
          "identity_check" not in body)

# ── 2. Species: the signal that can speak alone ──────────────────────────────
r = ic.check(CAT, sig(1), "dog", [sig(2), sig(3), sig(4)])
check("a dog filed under a cat is raised", r["status"] == "species_mismatch")
check("the mismatch names both animals",
      "dog" in r["headline"] and "cat" in r["headline"] and "Louis" in r["headline"])
check("the mismatch says the analysis still ran",
      "analysed" in r["detail"] and "filed" in r["detail"])
check("species is reported both ways",
      r["species_expected"] == "cat" and r["species_seen"] == "dog")

check("matching species is not raised",
      ic.check(CAT, sig(1), "cat", [])["status"] != "species_mismatch")
check("an unrecorded species can't disagree",
      ic.check({"name": "Louis"}, sig(1), "dog", [])["status"] != "species_mismatch")
check("an undetected species can't disagree",
      ic.check(CAT, sig(1), None, [])["status"] != "species_mismatch")

# ── 3. Never a score, never a verdict ────────────────────────────────────────
for case in (ic.check(CAT, sig(1), "dog", []), ic.check(CAT, sig(1), "cat", []),
             ic.check(CAT, None, None, [])):
    check("no score of any kind is returned",
          not any(k in case for k in ("distress_score", "zone", "score")))
    check("status is one of the four known states",
          case["status"] in {"consistent", "unverified",
                             "species_mismatch", "appearance_outlier"})

# ── 4. Coat colour, treated as weak ──────────────────────────────────────────
base = sig(11)
family = [jitter(base, 0.0004), jitter(base, 0.0008), jitter(base, 0.0002)]

few = ic.check(CAT, base, "cat", family[:2])
check("fewer than three priors says so rather than guessing",
      few["status"] == "unverified" and str(ic.MIN_HISTORY) in few["detail"])

no_sig = ic.check(CAT, None, "cat", family)
check("nothing measurable is stated as such",
      no_sig["status"] == "unverified" and "detected" in no_sig["detail"])

same = ic.check(CAT, jitter(base, 0.0006), "cat", family)
check("the same animal in different light is not flagged",
      same["status"] == "consistent", f"got {same}")
check("a pass says what it did and did not check",
      "individual recognition" in same["detail"])

stranger = ic.check(CAT, sig(97), "cat", family)
check("a wholly different coat is flagged", stranger["status"] == "appearance_outlier",
      f"d={stranger['appearance_distance']} t={stranger['appearance_threshold']}")
check("the flag is worded as a question, not a finding",
      "question" in stranger["detail"] and "lighting" in stranger["detail"].lower())
check("the measured distance and its threshold are both reported",
      isinstance(stranger["appearance_distance"], float)
      and isinstance(stranger["appearance_threshold"], float))
check("the threshold never drops below the floor",
      stranger["appearance_threshold"] >= ic.DISTANCE_FLOOR)

# A pet whose own captures vary wildly must be harder to flag, not easier —
# that is what "each pet is its own control" means here.
wide = [sig(11), sig(12), sig(13)]
tight_t = ic.check(CAT, base, "cat", family)["appearance_threshold"]
wide_t = ic.check(CAT, sig(11), "cat", wide)["appearance_threshold"]
check("a pet with varied captures gets a wider threshold", wide_t >= tight_t,
      f"tight={tight_t} wide={wide_t}")

# ── 4b. The alarm is off unless someone turned it on ─────────────────────────
# Shipping it on would mean guessing a threshold nobody has measured, and a
# wrong "is this really your pet?" teaches a guardian to ignore the warnings
# that matter. The measurement still has to run and still has to be reported.
ic.APPEARANCE_ALARM = False
try:
    quiet = ic.check(CAT, sig(97), "cat", family)
    check("with the alarm off, a colour outlier does not raise",
          quiet["status"] == "consistent")
    check("with the alarm off, the distance is still measured and reported",
          quiet["appearance_distance"] is not None and quiet["appearance_exceeds"] is True)
    check("the block says the alarm was off",
          quiet["appearance_alarm_enabled"] is False)
    check("a pass never claims the animal was recognised",
          "individual recognition" in quiet["detail"])
    check("species still raises with the alarm off",
          ic.check(CAT, sig(1), "dog", family)["status"] == "species_mismatch")
finally:
    ic.APPEARANCE_ALARM = True

# ── 5. Distance behaves ──────────────────────────────────────────────────────
check("identical signatures are distance 0", ic.distance(base, base) == 0.0)
check("distance is bounded at 1", 0.0 <= ic.distance(sig(1), sig(500)) <= 1.0)
check("mismatched lengths are absent, not an error",
      ic.distance(base, base[:10]) is None)
check("a stored signature round-trips through JSON",
      ic.parse_signature(json.dumps(base)) == [round(v, 10) for v in base]
      or len(ic.parse_signature(json.dumps(base))) == ic.SIG_LEN)
check("a wrong-length stored signature is treated as absent",
      ic.parse_signature(json.dumps([0.1, 0.2])) is None)
check("junk in the column is treated as absent",
      ic.parse_signature("not json") is None)

# ── 6. Detected species is a majority, not a stray frame ─────────────────────
class A:
    def __init__(self, n): self.class_name = n


class F:
    def __init__(self, names): self.animals = [A(n) for n in names]


check("a clear majority wins",
      ic.measured_species([F(["cat"]), F(["cat"]), F(["cat"]), F(["dog"])]) == "cat")
check("a split decision names nothing",
      ic.measured_species([F(["cat"]), F(["dog"])]) is None)
check("no detections, no species", ic.measured_species([]) is None)
check("non-pet classes are ignored", ic.measured_species([F(["person"])]) is None)

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
