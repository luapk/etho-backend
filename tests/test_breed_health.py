"""Breed predisposition context and the capture plan it drives.

The tests that matter here are the containment ones. Population base rates are
useful at the edges of this tool and corrosive in its middle, so most of what
follows checks that breed data stays where it was put: out of the prompts, out
of the scores, and off any pet whose breed a human hasn't confirmed.
"""
import sys, types, os, tempfile

for n in ['google', 'google.generativeai']:
    sys.modules[n] = types.ModuleType(n)
sys.modules['google'].generativeai = sys.modules['google.generativeai']
os.environ['DATA_DIR'] = tempfile.mkdtemp()

from app.services import breed_health as B
from app.services import pet_store, vet_report

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  PASS {name}")
    else:
        fail += 1
        print(f"  FAIL {name} {detail}")


# ── Containment: the prompt must never see any of this ──
import app.services.gemini_service as G                       # noqa: E402
import app.prompts.ethological_prompt as P                    # noqa: E402

prompt_text = (P.ETHOLOGICAL_SYSTEM_PROMPT + G._IMAGE_MODE_ADDENDUM).lower()
for term in ["mmvd", "mitral", "boas", "predispos", "hypertrophic",
             "cardiomyopathy", "dysplasia", "vetcompass"]:
    check(f"prompt free of '{term}'", term not in prompt_text,
          "breed priors must never reach Gemini — it would see what it was told to expect")

src = open(os.path.join(os.path.dirname(__file__), "..", "app",
                        "services", "gemini_service.py")).read()
check("gemini_service does not import breed_health", "breed_health" not in src)

# ── Guardian-confirmed breeds only ──
check("no breed → no context", B.lookup("dog", None)["predispositions"] == [])
check("empty breed → no context", B.lookup("dog", "")["predispositions"] == [])
check("unknown breed → no context",
      B.lookup("dog", "Wibblehound")["predispositions"] == [])
check("no breed still returns the disclaimer",
      "NOT findings about this animal" in B.lookup("dog", None)["disclaimer"])

# ── Conformation inheritance ──
check("pug is brachycephalic", "brachycephalic" in B.conformations("dog", "Pug"))
check("dachshund is chondrodystrophic",
      "chondrodystrophic" in B.conformations("dog", "Dachshund"))
check("shih tzu is both",
      set(B.conformations("dog", "Shih Tzu")) >= {"brachycephalic", "chondrodystrophic"})
check("persian cat is brachycephalic",
      "brachycephalic" in B.conformations("cat", "Persian"))
check("whippet has no risk conformation",
      B.conformations("dog", "Whippet") == ["sighthound"])

# ── Lookup combines conformation and breed risks, without duplicates ──
ckcs = B.lookup("dog", "Cavalier King Charles Spaniel")
conds = [p["condition"] for p in ckcs["predispositions"]]
check("cavalier gets its cardiac risk",
      any("mitral" in c.lower() for c in conds), conds)
check("cavalier also inherits brachycephalic risks",
      any("BOAS" in c for c in conds), conds)
check("no duplicate conditions", len(conds) == len(set(conds)), conds)
check("every entry cites a source",
      all(p.get("source") for p in ckcs["predispositions"]))

# ── Honesty about coverage ──
dachs = B.lookup("dog", "Dachshund")
ivdd = [p for p in dachs["predispositions"] if "IVDD" in p["condition"]][0]
check("IVDD admits Etho can't screen gait",
      "cannot assess" in ivdd["unobservable_reason"].lower(), ivdd)
check("bloat refuses to be used as a triage tool",
      any("emergency vet" in p.get("unobservable_reason", "")
          for p in B.lookup("dog", "Great Dane")["predispositions"]))
for sp, breed in [("dog", "Pug"), ("dog", "Labrador"), ("cat", "Maine Coon"),
                  ("cat", "Persian")]:
    for p in B.lookup(sp, breed)["predispositions"]:
        has_coverage = bool(p.get("observable")) or bool(p.get("unobservable_reason"))
        check(f"{breed}/{p['condition'][:28]} states its coverage", has_coverage, p)
        for o in p.get("observable", []):
            check(f"{breed}/{o} is a real measurement", o in B.OBSERVABLE, o)

# ── Capture plan ──
plan = B.capture_plan("cat", "Maine Coon", [])
ids = [s["id"] for s in plan["plan"]]
check("HCM breed is asked for sleeping clips", "sleeping_clip" in ids, ids)
check("sleeping clip is the top ask", plan["plan"][0]["id"] == "sleeping_clip", ids)
check("plan says it's breed-driven", plan["driven_by_breed"] is True)
check("sleeping ask carries the right context tag",
      plan["plan"][0]["context_tag"] == "sleeping_baseline")
check("sleeping ask names the measurement, not the disease",
      "respiratory rate" in plan["plan"][0]["measures"].lower())
check("plan disclaims it's about the pet",
      "not a claim about this pet" in plan["note"])

unknown = B.capture_plan("dog", None, [])
check("unknown breed still asks for a baseline",
      [s["id"] for s in unknown["plan"]] == ["weekly_baseline"])
check("unknown breed plan isn't breed-driven", unknown["driven_by_breed"] is False)

# Prior work is acknowledged rather than repeated blindly.
hist = [{"resp_rate_bpm": 22, "created_at": "2026-07-01T00:00:00+00:00",
         "context": "sleeping_baseline", "breed_detected": "Maine Coon"},
        {"resp_rate_bpm": 24, "created_at": "2026-07-08T00:00:00+00:00",
         "context": "sleeping_baseline", "breed_detected": "Maine Coon"}]
p2 = B.capture_plan("cat", "Maine Coon", hist)
srr = [s for s in p2["plan"] if s["id"] == "sleeping_clip"][0]
check("plan counts SRR clips already done", srr["done_count"] == 2, srr)
check("plan reports when SRR was last measured",
      srr["last_measured"] == "2026-07-08T00:00:00+00:00")

# ── breed_detected is a suggestion, never an input ──
check("single detection is not enough to suggest",
      B.suggest_breed([{"breed_detected": "Beagle"}]) == (None, 0))
check("agreement across captures suggests",
      B.suggest_breed([{"breed_detected": "Beagle"}, {"breed_detected": "Beagle"}])
      == ("Beagle", 2))
check("'unknown' is not a breed",
      B.suggest_breed([{"breed_detected": "unknown"}] * 3) == (None, 0))
check("confirmed breed suppresses the suggestion",
      B.capture_plan("dog", "Beagle", [{"breed_detected": "Beagle"}] * 3)
      ["breed_suggestion"] is None)
check("unconfirmed breed offers the suggestion",
      B.capture_plan("dog", None, [{"breed_detected": "Beagle"}] * 3)
      ["breed_suggestion"] == {"breed": "Beagle", "seen_in": 3})

# ── End to end: the vet report, and scores left alone ──
pet_store.init_db()
pug = pet_store.create_pet({"name": "Otto", "species": "dog", "breed": "Pug"})
plain = pet_store.create_pet({"name": "Nia", "species": "dog"})
for pid in (pug["id"], plain["id"]):
    for i in range(3):
        pet_store.log_analysis(
            pid, {"overall_assessment": {"distress_score": 40, "zone": "yellow"},
                  "breed_detected": "Pug"},
            media_type="video", source_filename=f"{i}.mp4", file_size_bytes=1)

check("breed does not change stored scores",
      [h["distress_score"] for h in pet_store.get_history(pug["id"])]
      == [h["distress_score"] for h in pet_store.get_history(plain["id"])],
      "a breed prior must never move a distress score")

rep = vet_report.build_report(pug["id"])
md = vet_report.render_markdown(rep)
check("report carries breed context", bool(rep["breed_context"]["predispositions"]))
check("breed section is labelled population data",
      "population data — NOT observations of this animal" in md)
check("breed section states Etho's limits", "Can Etho screen for it?" in md)
check("breed section is cited", "VetCompass" in md)
check("breed section says it didn't touch the analysis",
      "influenced any score" in md)

rep2 = vet_report.build_report(plain["id"])
md2 = vet_report.render_markdown(rep2)
check("no confirmed breed → no breed section in the report",
      "Breed Context" not in md2)
check("unconfirmed breed report still builds", "Pre-Consultation" in md2)

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
