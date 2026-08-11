"""Stored media for the longitudinal record: posters, clips, eviction, scoping.

The point of these tests is the retention contract, not the JPEG encoding:
a timeline must keep its pictures forever while playable clips are allowed to
age out, and neither may ever leak across owners.
"""
import sys, types, os, tempfile

for n in ['google', 'google.generativeai']:
    sys.modules[n] = types.ModuleType(n)
sys.modules['google'].generativeai = sys.modules['google.generativeai']
os.environ['DATA_DIR'] = tempfile.mkdtemp()

import uuid
from app.services import media_store

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  PASS {name}")
    else:
        fail += 1
        print(f"  FAIL {name} {detail}")


def fake_media(path, mb):
    with open(path, "wb") as f:
        f.write(b"\0" * int(mb * 1024 * 1024))


# ── Path safety ──
check("rejects traversal id", media_store.media_path("../../etc/passwd") is None)
check("rejects empty id", media_store.poster_path("") is None)
check("unknown id has no media", media_store.has_media(str(uuid.uuid4())) is False)

# ── Save keeps the annotated file, and reports honestly when it can't ──
root = media_store.media_root()
aid = str(uuid.uuid4())
src = os.path.join(tempfile.mkdtemp(), "annotated.mp4")
fake_media(src, 0.2)
saved = media_store.save_for_analysis(aid, "video", annotated_path=src)
check("clip stored", saved["media"] is True)
check("clip retrievable", media_store.media_path(aid) is not None)
check("stored under DATA_DIR", media_store.media_path(aid).startswith(root))
# A byte-blob isn't a decodable video, so no poster — the important part is
# that this is reported rather than raised.
check("poster failure reported, not raised", saved["poster"] is False)

missing = str(uuid.uuid4())
res = media_store.save_for_analysis(missing, "video", annotated_path="/nope/absent.mp4")
check("absent source stores nothing", res == {"media": False, "poster": False})
check("absent source leaves no file", media_store.has_media(missing) is False)

# ── Eviction: oldest clips go first, posters never do ──
for f in os.listdir(root):
    os.unlink(os.path.join(root, f))

ids = []
for i in range(5):
    a = str(uuid.uuid4())
    ids.append(a)
    clip = os.path.join(root, f"{a}.mp4")
    fake_media(clip, 1.0)
    os.utime(clip, (1_000_000 + i * 60, 1_000_000 + i * 60))   # oldest first
    poster = os.path.join(root, f"{a}_poster.jpg")
    fake_media(poster, 0.01)

check("library measures clips only", 4.9 < media_store.library_bytes() / (1024 * 1024) < 5.1)

removed = media_store.enforce_budget(budget_mb=3)
check("evicted down to budget", removed == 2, f"removed={removed}")
check("oldest clip went", media_store.has_media(ids[0]) is False)
check("second-oldest clip went", media_store.has_media(ids[1]) is False)
check("newest clip kept", media_store.has_media(ids[4]) is True)
check("under budget after eviction",
      media_store.library_bytes() <= 3 * 1024 * 1024,
      f"{media_store.library_bytes()}")

check("every poster survived eviction",
      all(media_store.has_poster(a) for a in ids),
      "a timeline must keep its pictures even once the clips age out")

check("no-op when already under budget", media_store.enforce_budget(budget_mb=100) == 0)
check("zero budget disables eviction rather than wiping the library",
      media_store.enforce_budget(budget_mb=0) == 0 and media_store.has_media(ids[4]))

# ── Deletion removes both artefacts ──
media_store.delete_for_analysis(ids[4])
check("delete removes clip", media_store.has_media(ids[4]) is False)
check("delete removes poster", media_store.has_poster(ids[4]) is False)

# ── Status reporting ──
st = media_store.storage_status()
check("status counts posters", st["posters_stored"] == 4, st)
check("status reports budget", st["budget_mb"] == media_store.BUDGET_MB)

# ── Owner scoping through the API ──
os.environ['API_KEY'] = 'admin-key-media'
import app.main as M                                    # noqa: E402
from fastapi.testclient import TestClient               # noqa: E402

client = TestClient(M.app)
A = {"X-API-Key": "admin-key-media"}

k1 = client.post("/api/owners", json={"name": "One"}, headers=A).json()["api_key"]
k2 = client.post("/api/owners", json={"name": "Two"}, headers=A).json()["api_key"]
H1, H2 = {"X-API-Key": k1}, {"X-API-Key": k2}

pet = client.post("/api/pets", json={"name": "Poster Pup", "species": "dog"},
                  headers=H1).json()["pet"]
from app.services import pet_store                      # noqa: E402
analysis_id = pet_store.log_analysis(
    pet["id"], {"overall_assessment": {"distress_score": 20, "zone": "green"}},
    media_type="video", source_filename="x.mp4", file_size_bytes=1,
    owner_id=client.get("/api/owners", headers=A).json()["owners"][0]["id"],
)
fake_media(os.path.join(media_store.media_root(), f"{analysis_id}_poster.jpg"), 0.01)

r = client.get(f"/api/analyses/{analysis_id}/poster", headers=H1)
check("owner gets their own poster", r.status_code == 200, r.status_code)
check("poster served as jpeg", r.headers["content-type"] == "image/jpeg")

r = client.get(f"/api/analyses/{analysis_id}/poster", headers=H2)
check("other owner gets 404, never 403", r.status_code == 404, r.status_code)

r = client.get(f"/api/analyses/{analysis_id}/media", headers=H1)
check("evicted clip 404s with an explanation",
      r.status_code == 404 and "no longer stored" in r.json()["detail"])

r = client.get(f"/api/analyses/{analysis_id}", headers=H1)
rec = r.json()["analysis"]
check("record advertises its poster", rec["has_poster"] is True)
check("record advertises missing clip", rec["has_media"] is False)

tl = client.get(f"/api/pets/{pet['id']}/timeline", headers=H1).json()["timeline"]
entry = [i for i in tl if i["type"] == "analysis"][0]
check("timeline feed carries has_poster", entry["has_poster"] is True)
check("timeline feed carries has_media", entry["has_media"] is False)

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
