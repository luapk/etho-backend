"""
Video annotation service.

Renders a copy of the input video with:
  - Colour-coded bounding box per detected pet (green/yellow/red = distress zone)
  - Two-line tag on the box: what the animal is doing (AI reading, from the
    timeline entry in force) over what was detected and how sure (measured)
  - YOLO skeleton overlay (keypoints + connections)
  - Spinal-angle readout when available
  - Persistent timeline event text (top strip) — updates at each Gemini event
  - Pet-POV interpretation text (bottom strip) — from interpret_lines
  - Distress meter (bottom-right corner) that tracks the Gemini timeline

Annotated videos are stored in ANNOTATED_VIDEO_DIR and served via the
GET /api/video/annotated/{video_id} endpoint.  They are ephemeral: stored in
/tmp and cleaned up on the next upload request (files older than 2 hours).
"""

import cv2
import numpy as np
import os
import shutil
import subprocess
import uuid
import time
from collections import deque
from typing import Optional

ANNOTATED_VIDEO_DIR = "/tmp/etho_annotated"
os.makedirs(ANNOTATED_VIDEO_DIR, exist_ok=True)

# Keypoints are drawn at a stricter confidence than the one used for metrics
# (0.3): a wrongly-placed skeleton drawn confidently costs more trust than a
# missing one. Metrics keep the looser threshold because averages tolerate
# noise; the overlay does not.
DRAW_CONF = 0.5

# BGR colours
_GREEN  = (50, 205, 50)
_YELLOW = (30, 210, 245)
_RED    = (50, 50, 220)
_WHITE  = (255, 255, 255)
_BLACK  = (0, 0, 0)
_SKEL   = (50, 200, 200)   # skeleton lines
_KP     = (30, 240, 130)   # keypoint dots

SKELETON_CONNECTIONS = [
    (0, 1), (0, 2), (1, 3), (2, 4),
    (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
    (5, 11), (6, 12), (11, 12),
    (11, 13), (13, 15), (12, 14), (14, 16),
]


def _zone_color(zone: str) -> tuple:
    return {"green": _GREEN, "yellow": _YELLOW, "red": _RED}.get(zone, _YELLOW)


def _ts_to_frame(ts, fps: float) -> int:
    try:
        s = ts if not isinstance(ts, str) else (
            sum(float(p) * 60 ** (1 - i) for i, p in enumerate(str(ts).split(":")))
        )
        return int(float(s) * fps)
    except Exception:
        return 0


# ── Drawing primitives ────────────────────────────────────────────────────────
# All text/geometry scales with frame height so overlays stay legible from
# 480p phone clips to 4K — fixed pixel sizes were unreadable on large frames.

def _ui_scale(frame) -> float:
    return max(0.6, frame.shape[0] / 720.0)


_UNNAMED = {"", "unknown", "unclear", "unidentified", "n/a", "na", "none",
            "mixed", "mixed breed", "not determined", "indeterminate"}


def _subject_tag(analysis: dict) -> str:
    """What the DETECTOR is looking at, in words that are always true.

    The box used to be captioned with `breed_detected`, which is "unknown"
    whenever the model won't commit to a breed — so the one overlay that
    proves the tool actually found the animal was labelled "unknown 22%".
    The species is never unknown (YOLO detects by class, that is what put the
    box there); the breed is printed only when there is one to print.
    """
    species = str(analysis.get("species") or "").strip().lower()
    subject = {"cat": "Cat", "dog": "Dog"}.get(species, "Pet")
    breed = str(analysis.get("breed_detected") or "").strip()
    if breed.lower() in _UNNAMED:
        return subject
    if subject.lower() in breed.lower():
        return breed
    return f"{breed} {subject.lower()}"


_STATE_MAX_WORDS = 5
_STATE_MAX_CHARS = 30


def _state_phrase(event: Optional[dict]) -> str:
    """A few words for what the animal is doing at this moment, taken from the
    timeline entry in force on this frame.

    A breed name never changes across a clip, so it told the viewer nothing
    about the footage they were watching. What the animal is doing does change,
    and it is the thing the box is drawn around.

    Gemini returns these as sentences, so this takes the first clause and caps
    it — a caption that outgrows the box it labels is worse than no caption.
    """
    if not event:
        return ""
    raw = str(event.get("pet_state") or event.get("event_description") or "").strip()
    if not raw:
        return ""
    for sep in ("—", " - ", ";", ",", ". "):
        if sep in raw:
            raw = raw.split(sep)[0]
            break
    raw = raw.rstrip(" .").strip()
    words = raw.split()
    cut = len(words) > _STATE_MAX_WORDS
    if cut:
        raw = " ".join(words[:_STATE_MAX_WORDS])
    if len(raw) > _STATE_MAX_CHARS:
        raw, cut = raw[:_STATE_MAX_CHARS].rstrip(), True
    if cut:
        # Say it was cut. A phrase that stops mid-thought without a mark reads
        # as the model's whole reading rather than the front of it.
        raw += "..."
    # Hershey fonts are ASCII-only; anything else renders as '?'.
    raw = raw.encode("ascii", "ignore").decode()
    return raw[:1].upper() + raw[1:]


def _bbox(frame, bbox, color, state: str, measured: str):
    """Box plus a two-line caption, and the two lines are deliberately unequal:

        line 1   what the animal is DOING   (AI reading — larger)
        line 2   what was DETECTED, and how sure   (measured — smaller, greyed)

    Never merged into one string. The box itself is a measurement, and printing
    a behaviour word in the same weight as a detection confidence would let the
    estimate borrow the detector's authority — the one rule this codebase keeps
    everywhere else.
    """
    u = _ui_scale(frame)
    th_line = max(2, int(2 * u))
    x1, y1, x2, y2 = map(int, bbox)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, th_line)

    fs1, fs2 = 0.52 * u, 0.38 * u
    pad = int(4 * u)
    (w1, h1), _ = cv2.getTextSize(state, cv2.FONT_HERSHEY_SIMPLEX, fs1, 1) if state else ((0, 0), 0)
    (w2, h2), _ = cv2.getTextSize(measured, cv2.FONT_HERSHEY_SIMPLEX, fs2, 1)
    gap = int(3 * u) if state else 0
    chip_w = max(w1, w2) + pad * 2
    chip_h = (h1 + gap if state else 0) + h2 + pad * 2

    # Above the box by default; tucked inside its top edge when the animal is
    # framed against the top of the shot and there is no room outside.
    top = y1 - chip_h
    if top < 0:
        top = min(y1, frame.shape[0] - chip_h)
    cv2.rectangle(frame, (x1, top), (x1 + chip_w, top + chip_h), color, -1)

    y = top + pad
    if state:
        y += h1
        cv2.putText(frame, state, (x1 + pad, y),
                    cv2.FONT_HERSHEY_SIMPLEX, fs1, _BLACK, 1, cv2.LINE_AA)
        y += gap
    y += h2
    # Both lines in black: the hierarchy is carried by size, not by fading one
    # of them out. Grey text on the red zone chip was the least legible thing
    # on the frame, and it was the measured line — the one that should never be
    # the hardest to read.
    cv2.putText(frame, measured, (x1 + pad, y),
                cv2.FONT_HERSHEY_SIMPLEX, fs2, _BLACK, 1, cv2.LINE_AA)


def _skeleton(frame, keypoints):
    if keypoints is None:
        return
    u = _ui_scale(frame)
    for a, b in SKELETON_CONNECTIONS:
        if a >= len(keypoints) or b >= len(keypoints):
            continue
        ka, kb = keypoints[a], keypoints[b]
        if ka[2] < DRAW_CONF or kb[2] < DRAW_CONF:
            continue
        cv2.line(frame, (int(ka[0]), int(ka[1])), (int(kb[0]), int(kb[1])),
                 _SKEL, max(2, int(2 * u)), cv2.LINE_AA)
    for kp in keypoints:
        if kp[2] > DRAW_CONF:
            cv2.circle(frame, (int(kp[0]), int(kp[1])), max(3, int(4 * u)), _KP, -1)


def _text_strip(frame, text: str, color: tuple, y_anchor: int, margin: int = 10):
    """Draw a semi-transparent banner with wrapped text at y_anchor (top of box)."""
    if not text:
        return
    h, w = frame.shape[:2]
    u = _ui_scale(frame)
    font, scale, thick = cv2.FONT_HERSHEY_SIMPLEX, 0.48 * u, max(1, int(u))
    line_h = int(18 * u)
    pad = int(6 * u)
    margin = int(margin * u)

    # Word-wrap
    words, lines, cur = text.split(), [], ""
    for word in words:
        test = (cur + " " + word).strip()
        (tw, _), _ = cv2.getTextSize(test, font, scale, thick)
        if tw > w - margin * 2 - 8:
            if cur:
                lines.append(cur)
            cur = word
        else:
            cur = test
    if cur:
        lines.append(cur)

    box_h = len(lines) * line_h + pad * 2
    overlay = frame.copy()
    cv2.rectangle(overlay, (margin, y_anchor), (w - margin, y_anchor + box_h), _BLACK, -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
    cv2.rectangle(frame, (margin, y_anchor), (w - margin, y_anchor + box_h), color, 1)

    for i, line in enumerate(lines):
        cv2.putText(frame, line,
                    (margin + int(5 * u), y_anchor + pad + (i + 1) * line_h - int(3 * u)),
                    font, scale, _WHITE, thick, cv2.LINE_AA)


_ZONE_LABELS = {"green": "LOW", "yellow": "MODERATE", "red": "ELEVATED"}


def _distress_meter(frame, score: int, zone: str):
    """Score bar with zone-boundary ticks, a text zone label (never color
    alone), and an explicit AI-estimate tag — the bar must not borrow the
    authority of the measured overlays around it."""
    h, w = frame.shape[:2]
    u = _ui_scale(frame)
    bw, bh = int(150 * u), int(14 * u)
    x, y = w - bw - int(10 * u), h - bh - int(10 * u)
    cv2.rectangle(frame, (x, y), (x + bw, y + bh), (40, 40, 40), -1)
    fill = int(bw * score / 100)
    cv2.rectangle(frame, (x, y), (x + fill, y + bh), _zone_color(zone), -1)
    cv2.rectangle(frame, (x, y), (x + bw, y + bh), _WHITE, 1)
    # Zone boundary ticks at 33 and 66
    for boundary in (33, 66):
        tx = x + int(bw * boundary / 100)
        cv2.line(frame, (tx, y - int(3 * u)), (tx, y + bh + int(3 * u)), _WHITE, 1)

    label = f"Distress {score} - {_ZONE_LABELS.get(zone, zone).upper()}"
    fs = 0.40 * u
    (lw, _), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, fs, 1)
    cv2.putText(frame, label, (x + bw - lw, y - int(6 * u)),
                cv2.FONT_HERSHEY_SIMPLEX, fs, _WHITE, 1, cv2.LINE_AA)
    tag = "AI estimate"
    fs2 = 0.32 * u
    (tw2, _), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, fs2, 1)
    cv2.putText(frame, tag, (x + bw - tw2, y + bh + int(12 * u)),
                cv2.FONT_HERSHEY_SIMPLEX, fs2, (200, 200, 200), 1, cv2.LINE_AA)


def _spine_band(deg: float) -> str:
    if deg < 5:
        return "relaxed"
    elif deg < 15:
        return "mild"
    elif deg < 30:
        return "moderate"
    return "severe"


def _spinal_readout(frame, angle: float):
    """Rolling-mean spine angle with its interpretation band. The instantaneous
    per-frame number flickered with pose noise, which read as unscientific."""
    h = frame.shape[0]
    u = _ui_scale(frame)
    cv2.putText(frame, f"Spine {angle:.1f}deg ({_spine_band(angle)}) YOLO-measured",
                (int(10 * u), h - int(10 * u)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.40 * u, _WHITE, 1, cv2.LINE_AA)


# ── Lookup builders ───────────────────────────────────────────────────────────

def _build_event_lookup(timeline: list, fps: float) -> dict:
    out = {}
    for ev in timeline:
        out[_ts_to_frame(ev.get("timestamp", "0:00"), fps)] = ev
    return out


def _build_pov_lookup(interpret_lines: list, fps: float) -> dict:
    out = {}
    for item in interpret_lines:
        frame = _ts_to_frame(item.get("timestamp", "0:00"), fps)
        out[frame] = item.get("pet_pov") or item.get("first_person_interpretation", "")
    return out


def _build_distress_track(event_lookup: dict, total_frames: int, default: int) -> list:
    """Per-frame distress score interpolated from timeline events."""
    track = [default] * total_frames
    sorted_frames = sorted(event_lookup.keys())
    for i, f in enumerate(sorted_frames):
        score = event_lookup[f].get("distress_score", default)
        next_f = sorted_frames[i + 1] if i + 1 < len(sorted_frames) else total_frames
        for fi in range(f, min(next_f, total_frames)):
            track[fi] = score
    return track


def _build_pose_track(pose_frames: list, total_frames: int, carry_secs: float, fps: float) -> dict:
    """
    Map sampled pose frames onto all video frames.
    Each sampled frame's data is carried forward for carry_secs seconds so the
    overlay stays visible between samples.
    """
    carry = int(carry_secs * fps)
    raw = {pf.frame_idx: pf for pf in pose_frames}
    track: dict = {}
    last_pf = None
    last_at = -carry - 1

    for fi in range(total_frames):
        if fi in raw:
            last_pf = raw[fi]
            last_at = fi
        if last_pf is not None and (fi - last_at) < carry:
            track[fi] = last_pf
    return track


# ── Main entry point ──────────────────────────────────────────────────────────

def annotate_video(video_path: str, pose_frames: list, analysis: dict) -> Optional[str]:
    """
    Render annotated video and return its video_id (UUID string).
    Returns None if the video cannot be opened or writing fails.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None

    fps    = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    video_id   = str(uuid.uuid4())
    out_path   = os.path.join(ANNOTATED_VIDEO_DIR, f"{video_id}.mp4")
    raw_path   = os.path.join(ANNOTATED_VIDEO_DIR, f"{video_id}_raw.mp4")
    fourcc     = cv2.VideoWriter_fourcc(*"mp4v")
    writer     = cv2.VideoWriter(raw_path, fourcc, fps, (width, height))

    subject  = _subject_tag(analysis)
    default_d = analysis.get("overall_assessment", {}).get("distress_score", 50)
    default_z = analysis.get("overall_assessment", {}).get("zone", "yellow")

    event_lut   = _build_event_lookup(analysis.get("timeline", []), fps)
    pov_lut     = _build_pov_lookup(analysis.get("interpret_lines", []), fps)
    d_track     = _build_distress_track(event_lut, total, default_d)
    pose_track  = _build_pose_track(pose_frames, total, carry_secs=0.8, fps=fps)

    cur_event_text = ""
    cur_pov_text   = ""
    cur_zone       = default_z
    # The box caption before the first timeline entry lands: the overall
    # body-language reading, so the box says something about the animal from
    # frame one rather than waiting several seconds to acquire a phrase.
    cur_state      = _state_phrase(
        {"pet_state": analysis.get("visual_analysis", {}).get("body_language", "")}
    )
    # ~1.5s rolling mean stabilises the on-screen spine number; the raw
    # per-sample values still feed the stored metrics untouched.
    spine_window = deque(maxlen=max(2, int(1.5 * 5)))

    frame_idx = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            score = d_track[frame_idx] if frame_idx < len(d_track) else default_d
            zone  = "green" if score <= 33 else ("red" if score > 66 else "yellow")
            color = _zone_color(zone)

            # Update persistent text from events
            if frame_idx in event_lut:
                ev = event_lut[frame_idx]
                cur_event_text = ev.get("event_description", "")
                cur_zone = ev.get("zone", zone)
                cur_state = _state_phrase(ev) or cur_state
            if frame_idx in pov_lut and pov_lut[frame_idx]:
                cur_pov_text = f'"{pov_lut[frame_idx]}"'

            # ── Pose overlay ─────────────────────────────────────────────────
            pf = pose_track.get(frame_idx)
            if pf:
                for animal in pf.animals:
                    _bbox(frame, animal.bbox, color, cur_state,
                          f"{subject} detected {animal.confidence:.0%}")
                    _skeleton(frame, animal.keypoints)
                    if animal.spinal_angle is not None:
                        spine_window.append(animal.spinal_angle)
                if spine_window:
                    _spinal_readout(frame, sum(spine_window) / len(spine_window))

            # ── Text overlays ────────────────────────────────────────────────
            h = frame.shape[0]
            if cur_event_text:
                _text_strip(frame, cur_event_text, _zone_color(cur_zone), y_anchor=8)
            if cur_pov_text:
                _text_strip(frame, cur_pov_text, _zone_color(cur_zone), y_anchor=h - 60)

            # ── Distress meter ───────────────────────────────────────────────
            _distress_meter(frame, score, zone)

            writer.write(frame)
            frame_idx += 1

    finally:
        cap.release()
        writer.release()

    _finalize_annotated(video_path, raw_path, out_path)
    print(f"  ✓ Annotated video: {video_id} ({frame_idx} frames)")
    return video_id


def _finalize_annotated(source_path: str, raw_path: str, out_path: str):
    """Re-encode the raw mp4v render to H.264 and mux the ORIGINAL AUDIO back
    in. OpenCV's writer produces a silent video-only file — unacceptable for
    a behaviour tool whose analysis cites vocalizations. H.264 + faststart
    also fixes mp4v playback on mobile Safari. Falls back to the silent mp4v
    file if ffmpeg is unavailable or fails, so annotation never breaks."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        try:
            cmd = [
                ffmpeg, "-nostdin", "-y",
                "-i", raw_path,          # annotated frames
                "-i", source_path,       # original upload (audio source)
                "-map", "0:v:0", "-map", "1:a:0?",   # audio optional
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-shortest", "-movflags", "+faststart",
                out_path,
            ]
            proc = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.PIPE, timeout=600)
            if proc.returncode == 0 and os.path.exists(out_path) \
                    and os.path.getsize(out_path) > 1024:
                os.unlink(raw_path)
                print("  ✓ Annotated video finalized (H.264 + original audio)")
                return
            print(f"  ⚠ ffmpeg finalize failed (rc={proc.returncode}) — "
                  f"serving silent mp4v fallback")
        except Exception as e:
            print(f"  ⚠ ffmpeg finalize error ({e}) — serving silent mp4v fallback")
    else:
        print("  ⚠ ffmpeg not found — annotated video will have no audio")
    os.replace(raw_path, out_path)


def extract_instrument_evidence(video_path: str, instrument_scores: dict) -> int:
    """Save one evidence still per scored instrument item.

    The FGS was validated on stills, so 'orbital_tightening: 1' should point
    at the exact frame it was scored from — that provenance is what lets a
    vet check the claim in two seconds. Each visible item with an
    evidence_timestamp gets a JPEG (caption bar: item, score, timestamp)
    stored in the annotated-media dir and referenced from the item as
    evidence_media_id, served by GET /api/video/annotated/{id}.

    Returns the number of stills written. Never raises — evidence is an
    enhancement, not a dependency.
    """
    if not isinstance(instrument_scores, dict):
        return 0
    items = instrument_scores.get("items") or []
    if not items:
        return 0

    written = 0
    cap = None
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return 0
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        for item in items:
            if not isinstance(item, dict) or item.get("visible") is False:
                continue
            ts = item.get("evidence_timestamp")
            if ts is None or item.get("score") is None:
                continue
            fidx = min(max(_ts_to_frame(ts, fps), 0), max(total - 1, 0))
            cap.set(cv2.CAP_PROP_POS_FRAMES, fidx)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue

            u = _ui_scale(frame)
            h, w = frame.shape[:2]
            bar_h = int(30 * u)
            caption = (f"{item.get('item', 'item')}: "
                       f"{item['score']:g}/{item.get('max', 2)}  @ {ts}  "
                       f"(AI-scored from this frame)")
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, h - bar_h), (w, h), _BLACK, -1)
            cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)
            cv2.putText(frame, caption, (int(8 * u), h - int(10 * u)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5 * u, _WHITE,
                        max(1, int(u)), cv2.LINE_AA)

            media_id = str(uuid.uuid4())
            out = os.path.join(ANNOTATED_VIDEO_DIR, f"{media_id}.jpg")
            if cv2.imwrite(out, frame):
                item["evidence_media_id"] = media_id
                written += 1
    except Exception as e:
        print(f"  ⚠ Evidence frame extraction failed: {e}")
    finally:
        if cap is not None:
            cap.release()
    if written:
        print(f"  ✓ Evidence stills: {written} instrument item(s)")
    return written


def probe_video_meta(video_path: str) -> dict:
    """Cheap technical probe for capture-quality checks: duration, resolution,
    and mid-clip brightness (mean grey 0-255). Returns {} on any failure —
    quality feedback is best-effort and must never break an analysis."""
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {}
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        meta = {
            "duration_sec": round(total / fps, 1) if fps else None,
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        }
        # Sample the middle frame for brightness
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, total // 2))
        ret, frame = cap.read()
        if ret and frame is not None:
            grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            meta["brightness"] = round(float(np.mean(grey)), 1)
        cap.release()
        return meta
    except Exception:
        return {}


def probe_image_meta(image_path: str) -> dict:
    """Technical probe for a still image. Returns {} on failure."""
    try:
        frame = cv2.imread(image_path)
        if frame is None:
            return {}
        grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return {
            "width": frame.shape[1],
            "height": frame.shape[0],
            "brightness": round(float(np.mean(grey)), 1),
        }
    except Exception:
        return {}


def annotate_image(image_path: str, pose_frames: list, analysis: dict) -> Optional[str]:
    """
    Render an annotated still (bbox, skeleton, distress meter, POV line) and
    return its media_id. Stored as {uuid}.jpg in the same ephemeral dir and
    served by the same download endpoint.
    """
    frame = cv2.imread(image_path)
    if frame is None:
        return None

    oa = analysis.get("overall_assessment", {})
    score = oa.get("distress_score", 50)
    zone = oa.get("zone", "yellow")
    color = _zone_color(zone)
    subject = _subject_tag(analysis)
    # A still has one moment, so its caption is the single timeline entry's
    # state — falling back to the overall body-language reading.
    tl = analysis.get("timeline") or []
    state = _state_phrase(tl[0] if tl else None) or _state_phrase(
        {"pet_state": analysis.get("visual_analysis", {}).get("body_language", "")}
    )

    if pose_frames and pose_frames[0].animals:
        for animal in pose_frames[0].animals:
            _bbox(frame, animal.bbox, color, state,
                  f"{subject} detected {animal.confidence:.0%}")
            _skeleton(frame, animal.keypoints)
            if animal.spinal_angle is not None:
                _spinal_readout(frame, animal.spinal_angle)

    lines = analysis.get("interpret_lines") or []
    pov = (lines[0].get("pet_pov") or lines[0].get("first_person_interpretation", "")
           if lines else "")
    if pov:
        _text_strip(frame, f'"{pov}"', color, y_anchor=frame.shape[0] - 60)
    _distress_meter(frame, score, zone)

    media_id = str(uuid.uuid4())
    out_path = os.path.join(ANNOTATED_VIDEO_DIR, f"{media_id}.jpg")
    if not cv2.imwrite(out_path, frame):
        return None
    print(f"  ✓ Annotated image: {media_id}")
    return media_id


def get_annotated_video_path(video_id: str) -> Optional[str]:
    for ext in (".mp4", ".jpg"):
        path = os.path.join(ANNOTATED_VIDEO_DIR, f"{video_id}{ext}")
        if os.path.exists(path):
            return path
    return None


def cleanup_video(video_id: str):
    path = os.path.join(ANNOTATED_VIDEO_DIR, f"{video_id}.mp4")
    try:
        os.unlink(path)
    except OSError:
        pass


def cleanup_old_videos(max_age_secs: int = 7200):
    """Delete annotated videos older than max_age_secs. Called lazily on upload."""
    now = time.time()
    try:
        for fname in os.listdir(ANNOTATED_VIDEO_DIR):
            fpath = os.path.join(ANNOTATED_VIDEO_DIR, fname)
            if os.path.isfile(fpath) and (now - os.path.getmtime(fpath)) > max_age_secs:
                os.unlink(fpath)
    except OSError:
        pass
