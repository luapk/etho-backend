"""
Video annotation service.

Renders a copy of the input video with:
  - Colour-coded bounding box per detected pet (green/yellow/red = distress zone)
  - Breed + confidence tag on the box
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
import uuid
import time
from typing import Optional

ANNOTATED_VIDEO_DIR = "/tmp/etho_annotated"
os.makedirs(ANNOTATED_VIDEO_DIR, exist_ok=True)

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

def _bbox(frame, bbox, color, label: str):
    x1, y1, x2, y2 = map(int, bbox)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 1)
    cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 6, y1), color, -1)
    cv2.putText(frame, label, (x1 + 3, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, _BLACK, 1, cv2.LINE_AA)


def _skeleton(frame, keypoints):
    if keypoints is None:
        return
    for a, b in SKELETON_CONNECTIONS:
        if a >= len(keypoints) or b >= len(keypoints):
            continue
        ka, kb = keypoints[a], keypoints[b]
        if ka[2] < 0.3 or kb[2] < 0.3:
            continue
        cv2.line(frame, (int(ka[0]), int(ka[1])), (int(kb[0]), int(kb[1])),
                 _SKEL, 2, cv2.LINE_AA)
    for kp in keypoints:
        if kp[2] > 0.3:
            cv2.circle(frame, (int(kp[0]), int(kp[1])), 4, _KP, -1)


def _text_strip(frame, text: str, color: tuple, y_anchor: int, margin: int = 10):
    """Draw a semi-transparent banner with wrapped text at y_anchor (top of box)."""
    if not text:
        return
    h, w = frame.shape[:2]
    font, scale, thick = cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1
    line_h = 18
    pad = 6

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
                    (margin + 5, y_anchor + pad + (i + 1) * line_h - 3),
                    font, scale, _WHITE, thick, cv2.LINE_AA)


def _distress_meter(frame, score: int, zone: str):
    h, w = frame.shape[:2]
    bw, bh = 130, 14
    x, y = w - bw - 10, h - bh - 10
    cv2.rectangle(frame, (x, y), (x + bw, y + bh), (40, 40, 40), -1)
    fill = int(bw * score / 100)
    cv2.rectangle(frame, (x, y), (x + fill, y + bh), _zone_color(zone), -1)
    cv2.rectangle(frame, (x, y), (x + bw, y + bh), _WHITE, 1)
    label = f"Distress {score}"
    (lw, _), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.40, 1)
    cv2.putText(frame, label, (x + bw // 2 - lw // 2, y - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.40, _WHITE, 1, cv2.LINE_AA)


def _spinal_readout(frame, angle: float):
    h = frame.shape[0]
    cv2.putText(frame, f"Spine {angle:.1f}deg",
                (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.40, _WHITE, 1, cv2.LINE_AA)


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
    fourcc     = cv2.VideoWriter_fourcc(*"mp4v")
    writer     = cv2.VideoWriter(out_path, fourcc, fps, (width, height))

    breed    = analysis.get("breed_detected", "Pet")
    default_d = analysis.get("overall_assessment", {}).get("distress_score", 50)
    default_z = analysis.get("overall_assessment", {}).get("zone", "yellow")

    event_lut   = _build_event_lookup(analysis.get("timeline", []), fps)
    pov_lut     = _build_pov_lookup(analysis.get("interpret_lines", []), fps)
    d_track     = _build_distress_track(event_lut, total, default_d)
    pose_track  = _build_pose_track(pose_frames, total, carry_secs=0.8, fps=fps)

    cur_event_text = ""
    cur_pov_text   = ""
    cur_zone       = default_z

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
            if frame_idx in pov_lut and pov_lut[frame_idx]:
                cur_pov_text = f'"{pov_lut[frame_idx]}"'

            # ── Pose overlay ─────────────────────────────────────────────────
            pf = pose_track.get(frame_idx)
            if pf:
                for animal in pf.animals:
                    label = f"{breed} {animal.confidence:.0%}"
                    _bbox(frame, animal.bbox, color, label)
                    _skeleton(frame, animal.keypoints)
                    if animal.spinal_angle is not None:
                        _spinal_readout(frame, animal.spinal_angle)

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

    print(f"  ✓ Annotated video: {video_id} ({frame_idx} frames)")
    return video_id


def get_annotated_video_path(video_id: str) -> Optional[str]:
    path = os.path.join(ANNOTATED_VIDEO_DIR, f"{video_id}.mp4")
    return path if os.path.exists(path) else None


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
