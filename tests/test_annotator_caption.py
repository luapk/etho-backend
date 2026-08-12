"""What the bounding box says.

The overlay box is the one place a guardian sees a measurement and an AI
reading touching each other, so its caption has two jobs and must not confuse
them:

  1. It must never print a non-answer. "unknown 22%" was the literal label on
     a correctly-detected cat, because the caption was built from
     `breed_detected` and the model declines to name a breed more often than
     not. The species is never unknown — it is what put the box there.
  2. The behaviour line is an estimate and the detection line is measured, and
     they are drawn differently for that reason. These tests cover the strings;
     the drawing is checked by eye.
"""
import sys, types, os, tempfile

# cv2 is a heavy native dep and none of the string logic touches it.
cv2 = types.ModuleType("cv2")
cv2.FONT_HERSHEY_SIMPLEX = 0
cv2.LINE_AA = 16
cv2.getTextSize = lambda *a, **k: ((10, 10), 0)
for name in ("rectangle", "putText", "line", "circle", "imwrite", "imread"):
    setattr(cv2, name, lambda *a, **k: None)
sys.modules["cv2"] = cv2
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())

from app.services.video_annotator import _subject_tag, _state_phrase

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  PASS {name}")
    else:
        fail += 1
        print(f"  FAIL {name} {detail}")


# ── The reported bug: the box read "unknown" ──────────────────────────────
for miss in ("unknown", "Unknown", "unclear", "mixed breed", "n/a", "", None):
    tag = _subject_tag({"species": "cat", "breed_detected": miss})
    check(f"breed {miss!r} never reaches the box", tag == "Cat", f"got {tag!r}")

check("named breed is kept",
      _subject_tag({"species": "cat", "breed_detected": "Russian Blue"})
      == "Russian Blue cat")
check("breed that already names the species isn't doubled",
      _subject_tag({"species": "dog", "breed_detected": "Sheepdog"}) == "Sheepdog")
check("species missing falls back to a true word",
      _subject_tag({"breed_detected": "unknown"}) == "Pet")

# ── The behaviour line ────────────────────────────────────────────────────
check("pet_state is preferred over the event description",
      _state_phrase({"pet_state": "Alert and watching",
                     "event_description": "Cat turns toward door"})
      == "Alert and watching")
check("falls back to the event description",
      _state_phrase({"event_description": "Settling onto the sofa"})
      == "Settling onto the sofa")
check("no event, no claim", _state_phrase(None) == "")
check("empty event, no claim", _state_phrase({"pet_state": "   "}) == "")

long_sentence = ("Relaxed and content, showing no signs of tension while "
                 "resting in a familiar spot")
short = _state_phrase({"pet_state": long_sentence})
check("a sentence is cut to its first clause", short == "Relaxed and content",
      f"got {short!r}")
check("a clause with no punctuation is still capped",
      len(_state_phrase({"pet_state": "watching the window with total unblinking focus"})) <= 34)
check("the cap is marked, not silent",
      _state_phrase({"pet_state": "watching the window with total unblinking focus"}).endswith("..."))
check("first letter is raised",
      _state_phrase({"pet_state": "grooming calmly"}).startswith("G"))

# Hershey fonts render anything non-ASCII as '?', which would put a literal
# question mark on the animal.
check("non-ASCII is dropped rather than drawn as '?'",
      "?" not in _state_phrase({"pet_state": "Café nap — settled"}))

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
