import sys, types, os, json, tempfile

# Stub heavy deps not needed for this layer
for name in ['google', 'google.generativeai', 'cv2']:
    m = types.ModuleType(name); sys.modules[name] = m
sys.modules['google'].generativeai = sys.modules['google.generativeai']

os.environ['DATA_DIR'] = tempfile.mkdtemp()

from app.services import pet_store, vet_report
from app.services.gemini_service import validate_and_enrich_response
import app.main as M
from fastapi.testclient import TestClient

client = TestClient(M.app, raise_server_exceptions=True)
ok = fail = 0
def check(name, cond, detail=""):
    global ok, fail
    if cond: ok += 1; print(f"  PASS {name}")
    else: fail += 1; print(f"  FAIL {name} {detail}")

# ── 1. Instrument clamping in validate_and_enrich_response ──
r = validate_and_enrich_response({
    "species": "cat",
    "overall_assessment": {"distress_score": 30},
    "instrument_scores": {"instrument": "feline_grimace_scale", "max_total": 10,
        "items": [
            {"item": "ear_position", "score": 5, "max": 2, "visible": True},   # over max -> clamp 2
            {"item": "orbital_tightening", "score": 1, "max": 2, "visible": True},
            {"item": "muzzle_tension", "score": 2, "max": 2, "visible": False}, # not visible -> None
            {"item": "whisker_position", "score": "bad", "max": 2, "visible": True}, # junk -> None
        ], "total": 99}
}, {})
ins = r["instrument_scores"]
check("clamp over-max item", ins["items"][0]["score"] == 2)
check("invisible item nulled", ins["items"][2]["score"] is None)
check("junk score nulled", ins["items"][3]["score"] is None)
check("total recomputed (2+1=3, not 99)", ins["total"] == 3.0, ins["total"])
check("items_scorable", ins["items_scorable"] == 2)
check("default instrument block added when missing",
      validate_and_enrich_response({}, {})["instrument_scores"]["instrument"] == "not_scored")

# ── 2. Store: pet CRUD + logged analyses over 5 weeks ──
pet = pet_store.create_pet({"name": "Miso", "species": "cat", "breed": "Siamese",
                            "sex": "female", "birthdate": "2019-03-01", "weight_kg": 4.2})
pid = pet["id"]
check("pet created", pet["name"] == "Miso")

dates = [f"2026-07-{d:02d}T10:00:00+00:00" for d in (1, 8, 15, 22, 29)]
scores = [25, 30, 28, 45, 62]  # worsening trend
fgs =    [1, 1, 2, 4, 5]
orig = pet_store._utcnow
for i, (dt, sc, fg) in enumerate(zip(dates, scores, fgs)):
    pet_store._utcnow = lambda dt=dt: dt
    fake = {
        "species": "cat", "breed_detected": "Siamese",
        "overall_assessment": {"distress_score": sc,
            "zone": "red" if sc > 66 else ("yellow" if sc > 33 else "green"),
            "confidence": "high", "primary_state": "alert"},
        "advisory": {"urgency": "elevated" if sc >= 60 else "routine"},
        "instrument_scores": {"instrument": "feline_grimace_scale",
            "total": fg, "max_total": 10, "items_scorable": 5},
        "behavioral_markers": [{"marker": "Ears flattened", "code": "EAD103",
                                "zone": "yellow"}] if sc > 27 else [],
        "_pose_metrics": {"spinal_curvature": {"mean_deg": 10 + sc/5, "max_deg": 20 + sc/4},
                          "detection_coverage": 0.9},
        "_audio_metrics": {"audio_present": True, "vocalization_event_count": i + 1,
                           "pitch": {"mean_hz": 400 + sc}, "solicitation_purr": {"possible": i == 4}},
        "_analysis_version": "etho-v17-longitudinal", "_prompt_version": "6.1",
        "_model_used": "gemini-2.0-flash",
    }
    pet_store.log_analysis(pid, fake, media_type="video" if i % 2 == 0 else "image",
                           source_filename=f"clip{i}.mp4", file_size_bytes=1000)
pet_store._utcnow = orig

hist = pet_store.get_history(pid)
check("5 records logged", len(hist) == 5, len(hist))
check("indexed metrics extracted", hist[3]["spinal_mean_deg"] == 19.0 and hist[3]["pitch_mean_hz"] == 445)
check("chronological order", [h["distress_score"] for h in hist] == scores)

# ── 3. Trends ──
t = pet_store.compute_trends(pid)
b = t["baseline"]
check("baseline from first 4 (mean 32)", b["mean"] == 32.0, b)
check("latest deviation positive & flagged", b["latest_deviation_sigma"] > 1.5 and b["flag"], b)
check("slope worsening", t["slope"]["direction"] == "worsening", t["slope"])
check("fgs threshold flags (4 and 5 >= 4)", sum(1 for f in t["red_flags"] if f["type"] == "fgs_threshold") == 2)
check("urgency flag present", any(f["type"] == "urgency" for f in t["red_flags"]))

# ── 4. Vet report ──
rep = vet_report.build_report(pid, reason_for_visit="Eating less this week")
check("report built", rep is not None and rep["signalment"]["name"] == "Miso")
check("age computed", rep["signalment"]["age"] is not None, rep["signalment"]["age"])
check("markers aggregated", rep["recurring_markers"][0]["records"] == 4, rep["recurring_markers"])
md = vet_report.render_markdown(rep)
for token in ["# Pre-Consultation", "Miso", "Signalment", "Observation Log",
              "Methodology & Limitations", "NOT a diagnosis", "Eating less",
              "fgs_threshold", "worsening", "gemini-2.0-flash"]:
    check(f"markdown contains '{token[:25]}'", token in md)

# ── 5. Endpoints via TestClient ──
r = client.post("/api/pets", json={"name": "Bruno", "species": "dog", "breed": "Boxer"})
check("POST /api/pets", r.status_code == 200 and r.json()["pet"]["name"] == "Bruno")
bruno = r.json()["pet"]["id"]
r = client.get("/api/pets")
check("GET /api/pets lists both", len(r.json()["pets"]) == 2)
check("analysis_count in listing", any(p["analysis_count"] == 5 for p in r.json()["pets"]))
r = client.patch(f"/api/pets/{bruno}", json={"weight_kg": 28.5})
check("PATCH pet", r.json()["pet"]["weight_kg"] == 28.5)
r = client.get(f"/api/pets/{pid}/history")
check("GET history", len(r.json()["history"]) == 5)
r = client.get(f"/api/pets/{pid}/trends")
check("GET trends", r.json()["trends"]["slope"]["direction"] == "worsening")
r = client.get(f"/api/pets/{pid}/vet-report?reason=checkup&format=markdown")
check("GET vet-report markdown", r.status_code == 200 and "Pre-Consultation" in r.text
      and r.headers["content-type"].startswith("text/markdown"))
r = client.get(f"/api/pets/{pid}/vet-report")
check("GET vet-report json", r.json()["report"]["period"]["observation_count"] == 5)
check("404 unknown pet", client.get("/api/pets/nope/history").status_code == 404)
aid = hist[0]["id"]
r = client.get(f"/api/analyses/{aid}")
check("GET analysis full record", r.json()["analysis"]["full_json"]["species"] == "cat")

# API key enforcement check
M._API_KEY = "sekrit"
check("401 without key", client.get("/api/pets").status_code == 401)
check("200 with key", client.get("/api/pets", headers={"X-API-Key": "sekrit"}).status_code == 200)
M._API_KEY = ""

print(f"\n{'='*40}\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
