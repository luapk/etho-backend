"""Capture-time extraction, batch upload, and motion health signals."""
import sys, types, os, tempfile, io
for n in ['google', 'google.generativeai']:
    sys.modules[n] = types.ModuleType(n)
sys.modules['google'].generativeai = sys.modules['google.generativeai']
os.environ['DATA_DIR'] = tempfile.mkdtemp()

import numpy as np

def _no_nose_kps():
    """Confident shoulders/hips but no nose — exactly what the human-pose
    model returns on a dog."""
    k = np.zeros((17, 3))
    for i in (5, 6, 11, 12):
        k[i] = [10 + i, 20 + i, 0.95]
    return k
from datetime import datetime, timezone, timedelta
from app.services import pet_store, media_metadata
from app.services.health_signals import HealthSignalService, _band_stats
import app.main as M
from fastapi.testclient import TestClient

client = TestClient(M.app)
ok = fail = 0
def check(name, cond, detail=""):
    global ok, fail
    if cond: ok += 1; print(f"  PASS {name}")
    else: fail += 1; print(f"  FAIL {name} {detail}")

# ── Capture time: filename patterns ──
f = media_metadata._from_filename
check("IMG_20260315_143022", f("IMG_20260315_143022.jpg").isoformat().startswith("2026-03-15T14:30:22"))
check("PXL phone format", f("PXL_20260315_143022123.jpg").isoformat().startswith("2026-03-15T14:30:22"))
check("Screenshot dashed", f("Screenshot_2026-03-15-14-30-22.png").isoformat().startswith("2026-03-15T14:30:22"))
check("WhatsApp date-only", f("IMG-20260315-WA0001.jpg").isoformat().startswith("2026-03-15T12:00:00"))
check("no date in name", f("cat_video.mp4") is None)
check("future date rejected", f(f"IMG_{(datetime.now(timezone.utc)+timedelta(days=400)).strftime('%Y%m%d')}_120000.jpg") is None)
check("pre-2000 rejected", f("IMG_19950101_120000.jpg") is None)

# ── Capture time: real video container metadata ──
V = "/root/.claude/uploads/5e872beb-d2fa-5d03-b724-cbcc21a87bb0/fe345ee8-screen2026080722575617861398690532.mp4"
if os.path.exists(V):
    info = media_metadata.extract_capture_time(V, os.path.basename(V), "video")
    check("real video: container time extracted",
          info["source"] == "video_metadata" and info["confident"]
          and info["captured_at"].startswith("2026-08-07T21:57"), info)

# ── Capture time: real EXIF round-trip ──
from PIL import Image
img_path = tempfile.mktemp(suffix=".jpg")
Image.new("RGB", (64, 64), (120, 120, 120)).save(img_path)
info = media_metadata.extract_capture_time(img_path, "plain.jpg", "image")
check("image without EXIF -> unknown", info["captured_at"] is None and info["source"] == "unknown")
info2 = media_metadata.extract_capture_time(img_path, "IMG_20260101_090000.jpg", "image")
check("EXIF-less image falls back to filename",
      info2["source"] == "filename" and not info2["confident"], info2)
os.unlink(img_path)

# ── Observed_at drives the record date (the whole point) ──
pet = pet_store.create_pet({"name": "Backlog", "species": "cat"})
old = "2026-01-15T10:00:00+00:00"
aid = pet_store.log_analysis(pet["id"], {
    "species": "cat", "overall_assessment": {"distress_score": 20, "zone": "green"},
}, media_type="image", observed_at=old, capture_time_source="exif")
h = pet_store.get_history(pet["id"])[0]
check("record dated by capture time, not upload", h["created_at"] == old, h["created_at"])
check("upload time kept separately", h["uploaded_at"] and h["uploaded_at"] != old)
check("capture source recorded", h["capture_time_source"] == "exif")
aid2 = pet_store.log_analysis(pet["id"], {
    "species": "cat", "overall_assessment": {"distress_score": 30, "zone": "green"},
}, media_type="image")
h2 = pet_store.get_history(pet["id"])
check("no capture time -> upload time used", h2[1]["created_at"] == h2[1]["uploaded_at"])
check("backlog sorts chronologically by capture date",
      h2[0]["created_at"] < h2[1]["created_at"])

# ── Health signals: pure spectral helper ──
fs = 30.0
t = np.arange(0, 10, 1/fs)
freqs = np.fft.rfftfreq(t.size, 1/fs)
tremor_sig = np.sin(2*np.pi*7*t)
from scipy.signal import welch
fr, psd = welch(tremor_sig, fs=fs, nperseg=128)
peak, purity, share = _band_stats(fr, psd, (4.0, 12.0))
check("tremor band finds 7 Hz", abs(peak - 7) < 0.7, peak)
check("tremor band dominant share", share > 0.5, share)
_, _, low_share = _band_stats(fr, psd, (0.5, 4.0))
check("locomotion band low for tremor signal", low_share < 0.3, low_share)

# ── Health signals: e2e on synthetic video ──
import cv2
def make_video(path, tremor_hz=None, seconds=8, fps=30):
    vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (320, 240))
    for i in range(int(seconds*fps)):
        tt = i/fps
        frame = np.full((240, 320, 3), 90, np.uint8)
        dy = int(6*np.sin(2*np.pi*tremor_hz*tt)) if tremor_hz else 0
        cv2.circle(frame, (160, 120+dy), 45, (180, 175, 170), -1)
        vw.write(frame)
    vw.release()

svc = HealthSignalService()
check("health service available", svc.available)
p1 = tempfile.mktemp(suffix=".mp4"); make_video(p1, tremor_hz=8)
r1 = svc.analyze(p1); os.unlink(p1)
check("tremor detected at 8 Hz",
      r1.get("tremor", {}).get("detected") and abs(r1["tremor"]["frequency_hz"] - 8) < 1.0,
      r1.get("tremor"))
p2 = tempfile.mktemp(suffix=".mp4"); make_video(p2, tremor_hz=None)
r2 = svc.analyze(p2); os.unlink(p2)
check("no tremor on still subject", not r2.get("tremor", {}).get("detected"), r2.get("tremor"))
check("activity level measured", r1["activity_level"]["value"] > r2["activity_level"]["value"])
check("limitations stated", "force plates" in r1["limitations"])
check("declares what it does NOT measure", "per-limb lameness" in r1["not_measured"])

# ── Batch endpoint ──
def jpg_bytes():
    p = tempfile.mktemp(suffix=".jpg")
    Image.new("RGB", (80, 80), (100, 140, 100)).save(p)
    b = open(p, "rb").read(); os.unlink(p); return b

r = client.post("/api/batch/upload", files=[])
check("empty batch rejected", r.status_code in (400, 422))
files = [("files", (f"IMG_2026031{i}_120000.jpg", io.BytesIO(jpg_bytes()), "image/jpeg"))
         for i in range(3)]
files.append(("files", ("notes.txt", io.BytesIO(b"nope"), "text/plain")))
r = client.post("/api/batch/upload", files=files)
check("batch accepted", r.status_code == 200 and r.json()["queued"] == 3, r.status_code)
check("unsupported type rejected per-file",
      len(r.json()["rejected"]) == 1 and "notes.txt" == r.json()["rejected"][0]["filename"])
bid = r.json()["batch_id"]
rs = client.get(f"/api/batch/{bid}")
check("batch status readable", rs.status_code == 200 and rs.json()["batch"]["total"] == 3)
check("unknown batch 404", client.get("/api/batch/nope").status_code == 404)

over = [("files", (f"f{i}.jpg", io.BytesIO(b"x"), "image/jpeg")) for i in range(31)]
check("over-limit batch rejected", client.post("/api/batch/upload", files=over).status_code == 400)

# ── Detector configuration ──
from app.services import yolo_pose_service as yps
check("detector defaults to yolo11m (nano was 3% detection)",
      yps.DETECT_MODEL == "yolo11m.pt", yps.DETECT_MODEL)
check("detector overridable via YOLO_MODEL", "YOLO_MODEL" in open(
      "app/services/yolo_pose_service.py").read())
check("pose stays nano (bigger human-pose model does not help animals)",
      yps.POSE_MODEL == "yolo11n-pose.pt")

# ── Pose reliability gates (human keypoints on animals emit nonsense) ──
from app.services.yolo_pose_service import (SPINE_STABILITY_MAX_SD,
                                            SPINE_PLAUSIBLE_MAX_DEG)
svc2 = yps.YoloPoseService.__new__(yps.YoloPoseService)
def mkframes(angles, tilt=5.0):
    out = []
    for i, a in enumerate(angles):
        out.append(yps.PoseFrame(i, float(i), [yps.AnimalPose(
            bbox=(0, 0, 10, 10), confidence=0.9, class_id=16, class_name="dog",
            keypoints=None, spinal_angle=a, head_tilt=tilt)]))
    return out

# Real pug clip values: wildly unstable and implausibly large
bad = svc2.summarize_metrics(mkframes([78.8, 117.9, 11.8, 68.5, 131.2]))["spinal_curvature"]
check("unstable spine flagged unreliable", bad["reliable"] is False, bad)
check("no interpretation when unreliable", "interpretation" not in bad)
check("unreliable reason explains why",
      "unstable" in bad["unreliable_reason"] or "implausible" in bad["unreliable_reason"])

good = svc2.summarize_metrics(mkframes([12.0, 14.0, 11.0, 13.5, 12.5]))["spinal_curvature"]
check("stable plausible spine stays reliable", good["reliable"] is True, good)
check("interpretation present when reliable", "interpretation" in good)

tilt_bad = svc2.summarize_metrics(mkframes([12.0, 13.0, 12.5], tilt=-174.7))["head_tilt"]
check("upside-down head tilt flagged", tilt_bad["reliable"] is False, tilt_bad)

# Unreliable values must not reach Gemini as ground truth
import sys as _s
_s.modules.setdefault("google", types.ModuleType("google"))
from app.services.gemini_service import analyze_video_with_context as _avc
import inspect
src = inspect.getsource(_avc)
check("Pass 2 gates on reliability", "NOT RELIABLY MEASURABLE" in src)

# ── Pose disabled by default (human keypoints fit a human to the dog) ──
check("pose estimation off by default", yps.ENABLE_POSE is False)
check("no invented nose vector remains",
      "0.0, -1.0" not in open("app/services/yolo_pose_service.py").read())
_svc3 = yps.YoloPoseService.__new__(yps.YoloPoseService)
check("missing nose -> no measurement (was fabricated)",
      _svc3._spinal_angle(_no_nose_kps()) is None)
check("detection still enabled", yps.DETECT_MODEL == "yolo11m.pt")
_nokp = [yps.PoseFrame(0, 0.0, [yps.AnimalPose(bbox=(0,0,9,9), confidence=0.9,
    class_id=16, class_name="dog", keypoints=None)])]
_m = _svc3.summarize_metrics(_nokp)
check("no face_visibility reported without keypoints", "face_visibility" not in _m, _m)
check("detection_coverage still reported", _m["detection_coverage"] == 1.0)

print(f"\n{'='*40}\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
