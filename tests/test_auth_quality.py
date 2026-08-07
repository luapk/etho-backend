import sys, types, os, tempfile, io

for name in ['google', 'google.generativeai', 'cv2']:
    m = types.ModuleType(name); sys.modules[name] = m
sys.modules['google'].generativeai = sys.modules['google.generativeai']
os.environ['DATA_DIR'] = tempfile.mkdtemp()

from app.services import pet_store, capture_quality, vet_report
import app.main as M
from fastapi.testclient import TestClient

client = TestClient(M.app)
ok = fail = 0
def check(name, cond, detail=""):
    global ok, fail
    if cond: ok += 1; print(f"  PASS {name}")
    else: fail += 1; print(f"  FAIL {name} {detail}")

ADMIN = "master-key"
M._API_KEY = ADMIN
adm = {"X-API-Key": ADMIN}

# ── Owners ──
r = client.post("/api/owners", json={"name": "Paul", "email": "p@x.com"}, headers=adm)
check("admin creates owner", r.status_code == 200)
key_a = r.json()["api_key"]
check("raw key etho_ prefix", key_a.startswith("etho_"))
owner_a_id = r.json()["owner"]["id"]
r2 = client.post("/api/owners", json={"name": "Sam"}, headers=adm)
key_b = r2.json()["api_key"]
hdr_a, hdr_b = {"X-API-Key": key_a}, {"X-API-Key": key_b}

check("owner cannot create owners (403)", client.post("/api/owners", json={"name": "X"}, headers=hdr_a).status_code == 403)
check("bad key 401", client.get("/api/pets", headers={"X-API-Key": "wrong"}).status_code == 401)
check("no key 401 when master set", client.get("/api/pets").status_code == 401)
r = client.get("/api/owners", headers=adm)
check("owner roster, no hashes", len(r.json()["owners"]) == 2 and "api_key_hash" not in r.json()["owners"][0])

# ── Scoping ──
pa = client.post("/api/pets", json={"name": "Rex", "species": "dog"}, headers=hdr_a).json()["pet"]
pb = client.post("/api/pets", json={"name": "Luna", "species": "cat"}, headers=hdr_b).json()["pet"]
check("pet gets owner_id", pa["owner_id"] == owner_a_id)
check("A lists only own pet", [p["name"] for p in client.get("/api/pets", headers=hdr_a).json()["pets"]] == ["Rex"])
check("admin lists all", len(client.get("/api/pets", headers=adm).json()["pets"]) == 2)
check("cross-owner get is 404 not 403", client.get(f"/api/pets/{pb['id']}", headers=hdr_a).status_code == 404)
check("cross-owner patch 404", client.patch(f"/api/pets/{pb['id']}", json={"name": "Hack"}, headers=hdr_a).status_code == 404)
check("cross-owner history 404", client.get(f"/api/pets/{pb['id']}/history", headers=hdr_a).status_code == 404)
check("cross-owner vet-report 404", client.get(f"/api/pets/{pb['id']}/vet-report", headers=hdr_a).status_code == 404)
check("own pet ok", client.get(f"/api/pets/{pa['id']}", headers=hdr_a).status_code == 200)
check("admin sees B's pet", client.get(f"/api/pets/{pb['id']}", headers=adm).status_code == 200)

# Upload guard fails fast on someone else's pet (404 before pipeline)
r = client.post(f"/api/video/upload?pet_id={pb['id']}", headers=hdr_a,
                files={"file": ("x.mp4", io.BytesIO(b"00"), "video/mp4")})
check("upload to other's pet: fast 404", r.status_code == 404)

# Analysis record scoping
aid = pet_store.log_analysis(pa["id"], {"species": "dog",
        "overall_assessment": {"distress_score": 20, "zone": "green"}},
        media_type="video", owner_id=owner_a_id, context="incident")
check("A reads own analysis", client.get(f"/api/analyses/{aid}", headers=hdr_a).status_code == 200)
check("B cannot read A's analysis (404)", client.get(f"/api/analyses/{aid}", headers=hdr_b).status_code == 404)
check("context stored", pet_store.get_history(pa["id"])[0]["context"] == "incident")

# Context surfaces in vet report
md = vet_report.render_markdown(vet_report.build_report(pa["id"]))
check("report shows context tag", "video (incident)" in md)

# ── Capture quality ──
good = capture_quality.assess("video",
    {"detection_coverage": 0.92}, {"audio_present": True},
    {"duration_sec": 45, "width": 1920, "height": 1080, "brightness": 120})
check("good grade", good["grade"] == "good", good)
check("no advice when good", good["advice"] == [])

fair = capture_quality.assess("video",
    {"detection_coverage": 0.6}, {"audio_present": True},
    {"duration_sec": 45, "width": 1920, "height": 1080, "brightness": 120})
check("fair grade on low coverage", fair["grade"] == "fair")
check("framing advice present", any("frame" in a for a in fair["advice"]))

poor = capture_quality.assess("video",
    {"detection_coverage": 0.9}, {},
    {"duration_sec": 5, "width": 640, "height": 360, "brightness": 30})
check("poor grade (short+dark)", poor["grade"] == "poor")
check("thresholds stated in checks", all(c["threshold"] for c in poor["checks"] if c["status"] != "unknown"))

img = capture_quality.assess("image", {"detection_coverage": 1.0}, None,
    {"width": 1000, "height": 800, "brightness": 100})
check("image good", img["grade"] == "good")
noyolo = capture_quality.assess("video", {}, {}, {}, yolo_available=False)
check("degrades to unknown without yolo", any(c["status"] == "unknown" for c in noyolo["checks"]))

# ── Protocol endpoint (public) ──
M._API_KEY = ""
r = client.get("/api/capture-protocol")
check("protocol endpoint open", r.status_code == 200)
proto = r.json()["protocol"]
check("protocol has contexts + rules", len(proto["contexts"]) == 4 and "video_baseline" in proto)

# ── Migration idempotence ──
pet_store.init_db(); pet_store.init_db()
check("init_db idempotent", True)

print(f"\n{'='*40}\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
