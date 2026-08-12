"""
YOLO detection service for pets, with optional (disabled) pose estimation.

WHAT THIS PROVIDES TODAY: per-frame cat/dog detection and bounding boxes.
Those feed the framing quality check, the ROI for respiration and motion
health signals, the annotated-video overlay, and postural-sway measurement.
Detection is solid — cat and dog are genuine COCO classes and yolo11m hits
98% frame coverage on real footage.

WHAT IT DOES NOT PROVIDE: keypoints. Pose estimation is OFF by default
because the only available weights are human-trained (COCO-17), and on a
quadruped they yield a confident human fit rather than approximate animal
anatomy — see the ENABLE_POSE comment below for the measured evidence.
Consequently spinal curvature, head tilt, and face visibility are not
reported unless an animal-trained model is supplied.

Supply one (AP-10K / SuperAnimal) via YOLO_POSE_MODEL + ENABLE_POSE=1, and
validate it with scripts/compare_pose_models.py before trusting its output.
"""

import os

# Ultralytics re-checks its requirements at import and will pip-install
# anything missing — including opencv-python, the desktop build we
# deliberately purge at build time (see nixpacks.toml). Left unchecked that
# would silently reintroduce the X11 dependency that crashes startup on a
# headless server. Must be set BEFORE ultralytics is imported.
os.environ.setdefault("YOLO_AUTOINSTALL", "false")

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

ANIMAL_CLASSES = {15: "cat", 16: "dog"}

# Detector size is the single biggest lever on whether a pet is found at
# all. Measured on a real cat clip (65 frames, conf 0.25), detection rate:
#
#   yolo11n   2.6M params    3%   0.07 s/frame   <- the old default
#   yolo11s   9.5M params   34%   0.10 s/frame
#   yolo11m  20.1M params   49%   0.25 s/frame   <- current default
#   yolo11l  25.4M params   45%   0.28 s/frame
#   yolo11x  57.0M params   48%   0.53 s/frame
#
# The nano model was effectively blind to a cat lying flat — the exact
# posture that matters clinically — while correctly finding humans in the
# same frames. Medium is the quality/latency sweet spot; set YOLO_MODEL to
# yolo11s.pt if per-request latency matters more than detection rate.
DETECT_MODEL = os.environ.get("YOLO_MODEL", "yolo11m.pt")
# ── Pose estimation is DISABLED by default ───────────────────────────────────
#
# The available pose weights are HUMAN-trained (COCO-17). Running them on a
# quadruped does not produce approximate animal anatomy — it produces a
# confident human fit to the wrong animal. Measured on a clear frontal frame
# of a sitting pug, the model returned 13/17 keypoints at 0.92-0.98
# confidence — shoulders, elbows, wrists, hips, knees, ankles — having read
# the dog's front legs as human legs. The nose and both eyes were absent.
#
# That absence was fatal: the spinal-angle calculation substituted a
# hardcoded [0, -1] "straight up" vector whenever the nose was missing, so
# the angle was computed from INVENTED input against mis-assigned keypoints.
# It reported 75 deg mean / 165 deg peak and "extreme fear crouch" for a
# calm dog. Reliability gates catch that after the fact, but stable garbage
# would still pass them — a static clip can yield consistently wrong
# keypoints. The honest fix is not to run the model at all.
#
# Detection (above) is unaffected and stays on: cat and dog are real COCO
# classes and it works well (98% coverage on that same clip).
#
# To re-enable, supply an ANIMAL-trained model (AP-10K / SuperAnimal):
#     YOLO_POSE_MODEL=/path/to/animal-pose.pt ENABLE_POSE=1
# and validate it first with scripts/compare_pose_models.py.
POSE_MODEL = os.environ.get("YOLO_POSE_MODEL", "yolo11n-pose.pt")
ENABLE_POSE = os.environ.get("ENABLE_POSE", "").strip().lower() in ("1", "true", "yes")

# COCO-17 skeleton connections used for visual overlay
SKELETON_CONNECTIONS = [
    (0, 1), (0, 2), (1, 3), (2, 4),          # head
    (5, 6), (5, 7), (7, 9), (6, 8), (8, 10), # arms / forelegs
    (5, 11), (6, 12), (11, 12),               # torso
    (11, 13), (13, 15), (12, 14), (14, 16),   # legs / hindlegs
]


@dataclass
class AnimalPose:
    bbox: tuple           # (x1, y1, x2, y2) in pixels
    confidence: float
    class_id: int
    class_name: str
    keypoints: Optional[np.ndarray]  # shape (17, 3): x, y, conf
    spinal_angle: Optional[float] = None
    head_tilt: Optional[float] = None
    # Outline of the animal in image coordinates, (N, 2). Present only when a
    # segmentation model is loaded. Unlike the box this contains the animal and
    # nothing else, so it is both the honest overlay and a much tighter ROI.
    polygon: Optional[np.ndarray] = None


@dataclass
class PoseFrame:
    frame_idx: int
    timestamp_sec: float
    animals: list = field(default_factory=list)


def _compute_iou(box1: tuple, box2: np.ndarray) -> float:
    x1 = max(box1[0], float(box2[0]))
    y1 = max(box1[1], float(box2[1]))
    x2 = min(box1[2], float(box2[2]))
    y2 = min(box1[3], float(box2[3]))
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if inter == 0.0:
        return 0.0
    a1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    a2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    return inter / (a1 + a2 - inter)


# Reliability gates for pose-derived angles.
#
# The pose model is HUMAN-trained (COCO-17). On a quadruped it places
# "shoulders" and "hips" wherever they best fit a human prior, which on some
# animals produces confident-looking nonsense. Measured on a clip of a calm
# pug sitting still: mean spinal curvature 75 deg, peak 165 deg, per-second
# values swinging 79 -> 118 -> 12 -> 69 -> 131, and a head tilt of -175 deg
# (upside down). Those numbers were being injected into Gemini as ground
# truth alongside the interpretation "extreme fear crouch, pain, or
# submission" — actively pushing the analysis toward a false positive.
#
# So the metric must prove itself before it is reported:
#   stability   a real posture does not swing tens of degrees per second;
#               high variance means keypoint noise, not movement
#   plausibility the interpretation scale tops out at 30 deg; a mean far
#               beyond it is not a posture this scale can describe
# Failing either, the raw numbers are still returned (for debugging) but
# flagged unreliable, and no interpretation is produced or sent to Gemini.
# The real fix is an animal-trained pose model (AP-10K / SuperAnimal) —
# see scripts/compare_pose_models.py.
SPINE_STABILITY_MAX_SD = 20.0
SPINE_PLAUSIBLE_MAX_DEG = 45.0
HEAD_TILT_PLAUSIBLE_MAX_DEG = 90.0


def _interpret_spinal_angle(deg: float) -> str:
    if deg < 5:
        return "Normal relaxed posture"
    elif deg < 15:
        return "Mild curvature - alert or mildly tense"
    elif deg < 30:
        return "Moderate curvature - submissive, fearful, or pain posture"
    else:
        return "Severe curvature - extreme fear crouch, pain, or submission"


class YoloPoseService:
    def __init__(self):
        self._detect_model = None
        self._pose_model = None
        self._segmenting = False
        self._available = False
        self._load_models()

    def _load_models(self):
        try:
            from ultralytics import YOLO
            self._detect_model = YOLO(DETECT_MODEL)
            # A -seg checkpoint gives masks as well as boxes, from one model
            # and one pass. Nothing else needs configuring: the overlay draws
            # the outline when it is there and the box when it is not.
            self._segmenting = getattr(self._detect_model, "task", "") == "segment"
            if ENABLE_POSE:
                self._pose_model = YOLO(POSE_MODEL)
                print(f"  ✓ YOLO loaded: {DETECT_MODEL} (detect) + {POSE_MODEL} (pose)")
                print("    ⚠ Pose enabled — verify the weights are ANIMAL-trained; "
                      "human COCO-17 keypoints produce confident nonsense on pets")
            else:
                mode = "detect+segment" if self._segmenting else "detect"
                print(f"  ✓ YOLO loaded: {DETECT_MODEL} ({mode}); pose disabled "
                      f"(no animal-trained model — set ENABLE_POSE=1 to override)")
            self._available = True
        except Exception as e:
            print(f"  ⚠ YOLO unavailable: {e}")

    @property
    def available(self) -> bool:
        return self._available

    @property
    def segmenting(self) -> bool:
        """True when the loaded detector also produces outlines."""
        return self._segmenting

    def process_video(self, video_path: str, sample_fps: float = 5.0) -> list:
        """
        Sample video at sample_fps and return a PoseFrame per sampled frame.
        Higher sample_fps = smoother overlay but longer processing time.
        """
        if not self._available:
            return []

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []

        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_interval = max(1, int(video_fps / sample_fps))
        frames: list[PoseFrame] = []
        frame_idx = 0

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_idx % frame_interval == 0:
                    ts = frame_idx / video_fps
                    frames.append(self._process_frame(frame, frame_idx, ts))
                frame_idx += 1
        finally:
            cap.release()

        print(f"  ✓ YOLO: {len(frames)} frames sampled, "
              f"{sum(1 for f in frames if f.animals)} with detections")
        return frames

    def process_image(self, image_path: str) -> list:
        """Run detection + pose on a single still image. Returns a list with
        one PoseFrame (or empty), so downstream summarize_metrics/annotation
        code works unchanged."""
        if not self._available:
            return []
        frame = cv2.imread(image_path)
        if frame is None:
            return []
        pf = self._process_frame(frame, frame_idx=0, timestamp=0.0)
        print(f"  ✓ YOLO (image): {len(pf.animals)} pet(s) detected")
        return [pf]

    def _process_frame(self, frame: np.ndarray, frame_idx: int, timestamp: float) -> PoseFrame:
        pose_frame = PoseFrame(frame_idx=frame_idx, timestamp_sec=timestamp)
        try:
            # ANIMAL_CLASSES is the single source of truth for what counts as
            # the subject; the filter used to repeat [15, 16] separately, so
            # the two could drift apart silently.
            det_results = self._detect_model(frame, classes=list(ANIMAL_CLASSES),
                                             verbose=False)
            if not det_results or not len(det_results[0].boxes):
                return pose_frame

            # Segmentation models return one polygon per detection, in the same
            # order as the boxes. Absent on a detect-only model, in which case
            # everything downstream falls back to the box.
            polys = None
            masks = getattr(det_results[0], "masks", None)
            if masks is not None and getattr(masks, "xy", None) is not None:
                polys = list(masks.xy)

            pose_boxes = None
            pose_kps = None
            pose_results = (self._pose_model(frame, verbose=False)
                            if self._pose_model is not None else None)
            if pose_results and pose_results[0].boxes is not None:
                pose_boxes = pose_results[0].boxes.xyxy.cpu().numpy()
                if pose_results[0].keypoints is not None:
                    pose_kps = pose_results[0].keypoints.data.cpu().numpy()

            for det_i, det_box in enumerate(det_results[0].boxes):
                cls_id = int(det_box.cls[0])
                if cls_id not in ANIMAL_CLASSES:
                    continue

                bbox = tuple(det_box.xyxy[0].tolist())
                conf = float(det_box.conf[0])

                # Match to best-overlapping pose skeleton
                keypoints = None
                if pose_boxes is not None and pose_kps is not None and len(pose_boxes):
                    best_iou, best_idx = 0.0, -1
                    for i, pb in enumerate(pose_boxes):
                        iou = _compute_iou(bbox, pb)
                        if iou > best_iou:
                            best_iou, best_idx = iou, i
                    if best_idx >= 0 and best_iou > 0.1:
                        keypoints = pose_kps[best_idx]

                polygon = None
                if polys is not None and det_i < len(polys):
                    p = polys[det_i]
                    # A three-point "outline" is a rendering artefact, not a
                    # silhouette; fall back to the box rather than draw it.
                    if p is not None and len(p) >= 8:
                        polygon = np.asarray(p, dtype=np.int32)

                pose_frame.animals.append(AnimalPose(
                    bbox=bbox,
                    confidence=conf,
                    class_id=cls_id,
                    class_name=ANIMAL_CLASSES[cls_id],
                    keypoints=keypoints,
                    spinal_angle=self._spinal_angle(keypoints),
                    head_tilt=self._head_tilt(keypoints),
                    polygon=polygon,
                ))
        except Exception as e:
            print(f"    ⚠ Frame {frame_idx} pose error: {e}")
        return pose_frame

    def _spinal_angle(self, kps: Optional[np.ndarray]) -> Optional[float]:
        """
        Deviation from straight axis via nose → mid-shoulder → mid-hip vectors.
        Returns degrees; 0° = perfectly straight spine.
        """
        if kps is None:
            return None

        def kp(i):
            return kps[i] if kps[i][2] > 0.3 else None

        nose = kp(0)
        ls, rs = kp(5), kp(6)
        lh, rh = kp(11), kp(12)

        if ls is None or rs is None or lh is None or rh is None:
            return None

        mid_s = np.array([(ls[0] + rs[0]) / 2, (ls[1] + rs[1]) / 2])
        mid_h = np.array([(lh[0] + rh[0]) / 2, (lh[1] + rh[1]) / 2])

        if nose is None:
            # Previously this substituted a hardcoded [0, -1] "straight up"
            # vector, fabricating the input the angle is measured against.
            # Absent a nose there is no measurement to make.
            return None

        v2 = mid_h - mid_s
        v1 = np.array([nose[0] - mid_s[0], nose[1] - mid_s[1]])

        n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
        if n1 == 0 or n2 == 0:
            return None

        cos_a = np.dot(v1, v2) / (n1 * n2)
        return round(180.0 - np.degrees(np.arccos(np.clip(cos_a, -1, 1))), 1)

    def _head_tilt(self, kps: Optional[np.ndarray]) -> Optional[float]:
        """Lateral head tilt from ear-to-ear line vs horizontal."""
        if kps is None:
            return None
        le, re = kps[3], kps[4]
        if le[2] < 0.3 or re[2] < 0.3:
            return None
        return round(float(np.degrees(np.arctan2(re[1] - le[1], re[0] - le[0]))), 1)

    def summarize_metrics(self, pose_frames: list) -> dict:
        """
        Aggregate per-frame data into a summary dict suitable for injection
        into Gemini's scene context string.
        """
        spinal_vals, tilt_vals = [], []
        frames_with_pet = 0
        frames_with_face = 0
        spine_buckets: dict = {}   # int(second) -> [angles]

        for pf in pose_frames:
            if pf.animals:
                frames_with_pet += 1
                for a in pf.animals:
                    if a.spinal_angle is not None:
                        spinal_vals.append(a.spinal_angle)
                        spine_buckets.setdefault(int(pf.timestamp_sec), []).append(a.spinal_angle)
                    if a.head_tilt is not None:
                        tilt_vals.append(a.head_tilt)
                # Face visible = nose + at least one eye confidently located
                # (COCO kp 0=nose, 1/2=eyes). Approximate on animals, but a
                # reliable screen for "can facial items be scored at all".
                if any(
                    a.keypoints is not None
                    and a.keypoints[0][2] > 0.3
                    and (a.keypoints[1][2] > 0.3 or a.keypoints[2][2] > 0.3)
                    for a in pf.animals
                ):
                    frames_with_face += 1

        total = max(len(pose_frames), 1)
        summary: dict = {
            "detection_coverage": round(frames_with_pet / total, 2),
            "frames_analyzed": len(pose_frames),
        }
        # Only report face visibility when keypoints actually exist. With pose
        # disabled the figure would be a constant 0.0, which reads as "the face
        # was never visible" and would wrongly tell guardians to re-film.
        # Absent a measurement, report nothing.
        if frames_with_pet and any(
            a.keypoints is not None for pf in pose_frames for a in pf.animals
        ):
            summary["face_visibility"] = round(frames_with_face / frames_with_pet, 2)

        if spinal_vals:
            mean_s = float(np.mean(spinal_vals))
            sd_s = float(np.std(spinal_vals)) if len(spinal_vals) > 1 else 0.0
            reasons = []
            if sd_s > SPINE_STABILITY_MAX_SD:
                reasons.append(f"unstable across frames (SD {sd_s:.0f} deg > "
                               f"{SPINE_STABILITY_MAX_SD:.0f}) — keypoint noise, "
                               f"not posture change")
            if mean_s > SPINE_PLAUSIBLE_MAX_DEG:
                reasons.append(f"implausible magnitude ({mean_s:.0f} deg; the "
                               f"interpretation scale ends at 30 deg)")
            reliable = not reasons

            sc = {
                "mean_deg": round(mean_s, 1),
                "max_deg": round(float(np.max(spinal_vals)), 1),
                "sd_deg": round(sd_s, 1),
                "reliable": reliable,
            }
            if reliable:
                sc["interpretation"] = _interpret_spinal_angle(mean_s)
            else:
                sc["unreliable_reason"] = "; ".join(reasons)
                sc["note"] = ("Human-pose keypoints (COCO-17) on an animal. "
                              "Not reported as a finding — assess posture "
                              "visually.")
            summary["spinal_curvature"] = sc
            # Per-second median series: the measured track a frontend can plot
            # on the same time axis as the AI distress curve and audio events,
            # so posture claims are visually corroborated. Median per bucket
            # suppresses single-frame pose glitches; capped for payload size.
            summary["spine_series"] = [
                {"t_sec": t, "deg": round(float(np.median(vals)), 1)}
                for t, vals in sorted(spine_buckets.items())
            ][:300]

        if tilt_vals:
            mean_t = float(np.mean(tilt_vals))
            # |tilt| near 180 deg means the ear-line was read upside down —
            # a keypoint-assignment failure, not a head position.
            tilt_reliable = abs(mean_t) <= HEAD_TILT_PLAUSIBLE_MAX_DEG
            summary["head_tilt"] = {
                "mean_deg": round(mean_t, 1),
                "max_abs_deg": round(float(np.max(np.abs(tilt_vals))), 1),
                "reliable": tilt_reliable,
            }
            if not tilt_reliable:
                summary["head_tilt"]["unreliable_reason"] = (
                    f"implausible tilt ({mean_t:.0f} deg) — ear keypoints "
                    f"likely mis-assigned by the human-pose model")

        return summary
