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

# ── Avatars: permanent, square, and never confused with a clip ──
import numpy as np, cv2                                  # noqa: E402

pid = str(uuid.uuid4())
portrait = os.path.join(tempfile.mkdtemp(), "portrait.jpg")
cv2.imwrite(portrait, np.full((1200, 800, 3), 120, np.uint8))   # tall phone photo
check("avatar saved", media_store.save_avatar(pid, portrait) is True)
check("avatar found", media_store.has_avatar(pid) is True)
av = cv2.imread(media_store.avatar_path(pid))
check("avatar is square", av.shape[0] == av.shape[1], av.shape)
check("avatar is downscaled", av.shape[0] == media_store.AVATAR_EDGE, av.shape)

small = os.path.join(tempfile.mkdtemp(), "small.png")
cv2.imwrite(small, np.full((200, 300, 3), 80, np.uint8))
pid2 = str(uuid.uuid4())
media_store.save_avatar(pid2, small)
av2 = cv2.imread(media_store.avatar_path(pid2))
check("small avatar squared but not upscaled", av2.shape[:2] == (200, 200), av2.shape)

check("unreadable file rejected cleanly",
      media_store.save_avatar(str(uuid.uuid4()), portrait + ".missing") is False)
check("traversal id rejected", media_store.save_avatar("../../evil", portrait) is False)

# The bug this guards: avatars live in the same directory as clips, so an
# eviction pass that only skips posters would delete pets' faces.
before = media_store.library_bytes()
fake_media(os.path.join(root, f"{uuid.uuid4()}.mp4"), 4.0)
media_store.enforce_budget(budget_mb=1)
check("avatars are not counted as evictable media",
      media_store.has_avatar(pid) and media_store.has_avatar(pid2),
      "an avatar must survive eviction like a poster")
check("library_bytes ignores avatars",
      media_store.library_bytes() < before + 4 * 1024 * 1024)

check("avatar removed on request", media_store.delete_avatar(pid) is True)
check("removing a missing avatar is a no-op", media_store.delete_avatar(pid) is False)

# ── Deletion removes both artefacts ──
media_store.delete_for_analysis(ids[4])
check("delete removes clip", media_store.has_media(ids[4]) is False)
check("delete removes poster", media_store.has_poster(ids[4]) is False)

# ── Status reporting ──
st = media_store.storage_status()
check("status counts posters", st["posters_stored"] == 4, st)
check("status counts avatars", st["avatars_stored"] == 1, st)
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

# ── Avatars through the API ──
avatar_src = os.path.join(tempfile.mkdtemp(), "face.jpg")
cv2.imwrite(avatar_src, np.full((900, 600, 3), 200, np.uint8))

with open(avatar_src, "rb") as fh:
    r = client.post(f"/api/pets/{pet['id']}/avatar",
                    files={"file": ("face.jpg", fh, "image/jpeg")}, headers=H1)
check("owner can set an avatar", r.status_code == 200, r.text[:120])

r = client.get(f"/api/pets/{pet['id']}/avatar", headers=H1)
check("avatar served", r.status_code == 200 and r.headers["content-type"] == "image/jpeg")

r = client.get(f"/api/pets/{pet['id']}/avatar", headers=H2)
check("other owner can't see the avatar (404, not 403)", r.status_code == 404)

with open(avatar_src, "rb") as fh:
    r = client.post(f"/api/pets/{pet['id']}/avatar",
                    files={"file": ("face.jpg", fh, "image/jpeg")}, headers=H2)
check("other owner can't set an avatar", r.status_code == 404, r.status_code)

listed = client.get("/api/pets", headers=H1).json()["pets"][0]
check("pet list advertises the avatar", listed["has_avatar"] is True, listed)
one = client.get(f"/api/pets/{pet['id']}", headers=H1).json()["pet"]
check("pet detail advertises the avatar", one["has_avatar"] is True)

with open(avatar_src, "rb") as fh:
    r = client.post(f"/api/pets/{pet['id']}/avatar",
                    files={"file": ("clip.mp4", fh, "video/mp4")}, headers=H1)
check("a video is rejected as a profile picture", r.status_code == 400, r.status_code)

r = client.delete(f"/api/pets/{pet['id']}/avatar", headers=H1)
check("avatar deletable", r.status_code == 200 and r.json()["removed"] is True)
check("pet list reflects removal",
      client.get("/api/pets", headers=H1).json()["pets"][0]["has_avatar"] is False)
r = client.get(f"/api/pets/{pet['id']}/avatar", headers=H1)
check("missing avatar 404s", r.status_code == 404)

# ── Correcting an observation's date ──
r = client.patch(f"/api/analyses/{analysis_id}", json={"observed_at": "2026-03-15"}, headers=H1)
check("owner can correct the date", r.status_code == 200, r.text[:120])
rec2 = r.json()["analysis"]
check("date moved", rec2["created_at"].startswith("2026-03-15"), rec2["created_at"])
check("correction is recorded as manual, not passed off as EXIF",
      rec2["capture_time_source"] == "manual", rec2["capture_time_source"])

r = client.patch(f"/api/analyses/{analysis_id}", json={"observed_at": "2026-03-15"}, headers=H2)
check("other owner cannot edit the date (404)", r.status_code == 404, r.status_code)

for bad, why in [("not-a-date", "gibberish"), ("2099-01-01", "future"), ("1970-01-01", "pre-2000")]:
    r = client.patch(f"/api/analyses/{analysis_id}", json={"observed_at": bad}, headers=H1)
    check(f"rejects {why} date", r.status_code == 400, f"{bad} -> {r.status_code}")

check("a rejected edit leaves the date alone",
      client.get(f"/api/analyses/{analysis_id}", headers=H1)
            .json()["analysis"]["created_at"].startswith("2026-03-15"))

tl = client.get(f"/api/pets/{pet['id']}/timeline", headers=H1).json()["timeline"]
entry = [i for i in tl if i["type"] == "analysis"][0]
check("timeline feed carries has_poster", entry["has_poster"] is True)
check("timeline feed carries has_media", entry["has_media"] is False)

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
