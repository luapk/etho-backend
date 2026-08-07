import sys, types, os, tempfile

for name in ['google', 'google.generativeai', 'cv2']:
    m = types.ModuleType(name); sys.modules[name] = m
sys.modules['google'].generativeai = sys.modules['google.generativeai']
os.environ['DATA_DIR'] = tempfile.mkdtemp()

from app.services import pet_store, vet_report
from app.services.breed_reference import assess_weight, find_reference
import app.main as M
from fastapi.testclient import TestClient

client = TestClient(M.app)
ok = fail = 0
def check(name, cond, detail=""):
    global ok, fail
    if cond: ok += 1; print(f"  PASS {name}")
    else: fail += 1; print(f"  FAIL {name} {detail}")

# ── Breed reference ──
check("exact match", find_reference("dog", "labrador")[0] == "labrador")
check("substring match 'Labrador Retriever'", find_reference("dog", "Labrador Retriever")[0] == "labrador")
check("cat match 'Maine Coon cross'", find_reference("cat", "Maine Coon cross")[0] == "maine coon")
check("unknown breed no ref", find_reference("dog", "Etho Hound")[1] is None)

a = assess_weight("dog", "Labrador Retriever", 30)
check("lab 30kg within", a["status"] == "within_range")
a = assess_weight("dog", "Labrador Retriever", 42)
check("lab 42kg above + pct", a["status"] == "above_range" and a["percent_outside_range"] > 0, a)
a = assess_weight("cat", "unknown moggy", 7.5)
check("cat fallback species range", a["status"] == "above_range" and a["reference_source"] == "species_typical", a)
a = assess_weight("dog", "mystery mix", 20)
check("dog no fallback → no_reference", a["status"] == "no_reference")
check("BCS note everywhere", "BCS" in a["note"] or "body condition" in a["note"].lower())
check("no weight recorded", assess_weight("dog", "pug", None)["status"] == "no_weight_recorded")

# ── Weight endpoints ──
pet = client.post("/api/pets", json={"name": "Rex", "species": "dog",
                                     "breed": "Labrador Retriever"}).json()["pet"]
pid = pet["id"]
r = client.post(f"/api/pets/{pid}/weights", json={"weight_kg": 29.0, "recorded_at": "2026-06-01T09:00:00+00:00"})
check("weight logged", r.status_code == 200 and r.json()["weight_assessment"]["status"] == "within_range")
client.post(f"/api/pets/{pid}/weights", json={"weight_kg": 33.5, "recorded_at": "2026-07-01T09:00:00+00:00", "note": "after diet change"})
r = client.post(f"/api/pets/{pid}/weights", json={"weight_kg": 38.0, "recorded_at": "2026-08-01T09:00:00+00:00"})
check("latest above range", r.json()["weight_assessment"]["status"] == "above_range")
check("profile weight synced", client.get(f"/api/pets/{pid}").json()["pet"]["weight_kg"] == 38.0)
check("pet detail has assessment", client.get(f"/api/pets/{pid}").json()["weight_assessment"]["status"] == "above_range")
r = client.get(f"/api/pets/{pid}/weights")
check("weights listed chronologically", [w["weight_kg"] for w in r.json()["weights"]] == [29.0, 33.5, 38.0])
check("implausible weight 400", client.post(f"/api/pets/{pid}/weights", json={"weight_kg": 900}).status_code == 400)

# ── Timeline feed with per-asset curves ──
dates = ["2026-06-10T10:00:00+00:00", "2026-07-10T10:00:00+00:00"]
orig = pet_store._utcnow
for i, dt in enumerate(dates):
    pet_store._utcnow = lambda dt=dt: dt
    pet_store.log_analysis(pid, {
        "species": "dog",
        "overall_assessment": {"distress_score": 40 + i*10, "zone": "yellow", "primary_state": "alert"},
        "instrument_scores": {"instrument": "canine_observable_stress_subset", "total": 3+i, "max_total": 10},
        "capture_quality": {"grade": "good"},
        "timeline": [
            {"timestamp": "0:00", "distress_score": 30, "zone": "green"},
            {"timestamp": "0:15", "distress_score": 55, "zone": "yellow"},
            {"timestamp": "1:02", "distress_score": 45, "zone": "yellow"},
        ],
        "_media_kind": "video",
    }, media_type="video", owner_id=None, context="weekly_baseline")
pet_store._utcnow = orig

feed = pet_store.get_timeline_feed(pid)
check("feed merges 3 weights + 2 analyses", len(feed) == 5, len(feed))
check("chronological order", [f["date"] for f in feed] == sorted(f["date"] for f in feed))
an = [f for f in feed if f["type"] == "analysis"]
check("per-asset curve extracted", an[0]["distress_curve"] == [
    {"t_sec": 0.0, "distress_score": 30, "zone": "green"},
    {"t_sec": 15.0, "distress_score": 55, "zone": "yellow"},
    {"t_sec": 62.0, "distress_score": 45, "zone": "yellow"}], an[0]["distress_curve"])
check("feed items carry context+grade+instrument",
      an[0]["context"] == "weekly_baseline" and an[0]["quality_grade"] == "good"
      and an[0]["instrument_total"] == 3)
check("analysis_id present", all(f.get("analysis_id") for f in an))
r = client.get(f"/api/pets/{pid}/timeline")
check("GET /timeline endpoint", r.status_code == 200 and len(r.json()["timeline"]) == 5)

# ── Vet report weight section ──
md = vet_report.render_markdown(vet_report.build_report(pid))
for token in ["## Weight", "above range", "25-36 kg", "+9.0 kg", "after diet change",
              "Weight screening", "body condition"]:
    check(f"report contains '{token}'", token in md, "")

# ── Cross-owner scoping on new endpoints ──
M._API_KEY = "master"
adm = {"X-API-Key": "master"}
kb = client.post("/api/owners", json={"name": "Other"}, headers=adm).json()["api_key"]
hdr_b = {"X-API-Key": kb}
check("timeline cross-owner 404", client.get(f"/api/pets/{pid}/timeline", headers=hdr_b).status_code == 404)
check("weights cross-owner 404", client.post(f"/api/pets/{pid}/weights", json={"weight_kg": 5}, headers=hdr_b).status_code == 404)
M._API_KEY = ""

print(f"\n{'='*40}\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
