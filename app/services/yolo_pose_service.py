"""
YOLO11-Pose service for real-time pet detection and pose estimation.

Extracts bounding boxes, keypoints, and derived biomechanical metrics
(spinal angle, head tilt) that are injected into Gemini's context as
objective ground truth, preventing hallucinated posture claims.

Note: yolo11n-pose.pt is trained on human poses (COCO 17-keypoint).
It approximates pet body regions well enough for spinal angle calculation
and visual skeleton overlay. Upgrade to an AP-10K animal pose model for
production-grade keypoint accuracy.
"""

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

ANIMAL_CLASSES = {15: "cat", 16: "dog"}

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
        self._available = False
        self._load_models()

    def _load_models(self):
        try:
            from ultralytics import YOLO
            self._detect_model = YOLO("yolo11n.pt")
            self._pose_model = YOLO("yolo11n-pose.pt")
            self._available = True
            print("  ✓ YOLO11-Pose models loaded")
        except Exception as e:
            print(f"  ⚠ YOLO unavailable: {e}")

    @property
    def available(self) -> bool:
        return self._available

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
            det_results = self._detect_model(frame, classes=[15, 16], verbose=False)
            if not det_results or not len(det_results[0].boxes):
                return pose_frame

            pose_results = self._pose_model(frame, verbose=False)
            pose_boxes = None
            pose_kps = None
            if pose_results and pose_results[0].boxes is not None:
                pose_boxes = pose_results[0].boxes.xyxy.cpu().numpy()
                if pose_results[0].keypoints is not None:
                    pose_kps = pose_results[0].keypoints.data.cpu().numpy()

            for det_box in det_results[0].boxes:
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

                pose_frame.animals.append(AnimalPose(
                    bbox=bbox,
                    confidence=conf,
                    class_id=cls_id,
                    class_name=ANIMAL_CLASSES[cls_id],
                    keypoints=keypoints,
                    spinal_angle=self._spinal_angle(keypoints),
                    head_tilt=self._head_tilt(keypoints),
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

        v2 = mid_h - mid_s
        v1 = np.array([nose[0] - mid_s[0], nose[1] - mid_s[1]]) if nose is not None \
            else np.array([0.0, -1.0])

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

        for pf in pose_frames:
            if pf.animals:
                frames_with_pet += 1
                for a in pf.animals:
                    if a.spinal_angle is not None:
                        spinal_vals.append(a.spinal_angle)
                    if a.head_tilt is not None:
                        tilt_vals.append(a.head_tilt)

        total = max(len(pose_frames), 1)
        summary: dict = {
            "detection_coverage": round(frames_with_pet / total, 2),
            "frames_analyzed": len(pose_frames),
        }

        if spinal_vals:
            mean_s = float(np.mean(spinal_vals))
            summary["spinal_curvature"] = {
                "mean_deg": round(mean_s, 1),
                "max_deg": round(float(np.max(spinal_vals)), 1),
                "interpretation": _interpret_spinal_angle(mean_s),
            }

        if tilt_vals:
            summary["head_tilt"] = {
                "mean_deg": round(float(np.mean(tilt_vals)), 1),
                "max_abs_deg": round(float(np.max(np.abs(tilt_vals))), 1),
            }

        return summary
