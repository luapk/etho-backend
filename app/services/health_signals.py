"""
Automatically-extracted health signals from video motion.

Broadens health coverage WITHOUT depending on per-limb pose, which the
current keypoint model cannot deliver (human COCO-17 keypoints give
approximate spine/head positions, not reliable paw contacts). Everything
here is derived from whole-frame motion and the pet's bounding box —
inputs we already produce reliably — so the numbers mean what they say.

Measured signals:
  activity_level     mean motion energy — lethargy is one of the earliest
                     and most sensitive illness signs, and it is a trend
                     signal: meaningful against this pet's own baseline
  movement_regularity spectral purity in the locomotion band (0.5-4 Hz):
                     rhythmic gait is periodic, unsteady movement is not
  tremor             periodic motion in the 4-12 Hz band, the established
                     frequency range for physiologic and pathologic tremor
  postural_sway      lateral wander of the pet's centroid, normalised to
                     body width — a balance/ataxia screen

Explicitly NOT measured here: per-limb lameness, stride length, footfall
timing, weight-bearing asymmetry. Those require paw-level keypoints
(AP-10K / DeepLabCut class models). The clinical gold standard for
lameness remains force plates and pressure-sensitive walkways; nothing
derived from a phone video substitutes for that.

All outputs are SCREENING signals against the pet's own baseline, never
diagnoses.
"""

import numpy as np

try:
    import cv2
    _CV2_OK = True
except Exception:
    _CV2_OK = False

try:
    from scipy.signal import welch
    _SCIPY_OK = True
except Exception:
    _SCIPY_OK = False

# Tremor band. Physiologic and most pathologic tremors in small animals
# fall in this range; below it is normal locomotion, above it is noise.
TREMOR_BAND_HZ = (4.0, 12.0)
# Locomotion/rhythm band — walking, trotting, rhythmic scratching.
LOCOMOTION_BAND_HZ = (0.5, 4.0)

# A tremor claim needs both a clear spectral peak and enough of the signal
# concentrated there; these gates keep noise from reading as pathology.
_TREMOR_PURITY_MIN = 0.18
_TREMOR_POWER_RATIO_MIN = 0.15

_MIN_SECONDS = 3.0


def _band_stats(freqs, psd, band):
    mask = (freqs >= band[0]) & (freqs <= band[1])
    if not np.any(mask) or psd.sum() <= 0:
        return None, 0.0, 0.0
    bf, bp = freqs[mask], psd[mask]
    if bp.sum() <= 0:
        return None, 0.0, 0.0
    peak = int(np.argmax(bp))
    purity = float(bp[peak] / bp.sum())          # concentration within band
    share = float(bp.sum() / psd.sum())          # band's share of all power
    return float(bf[peak]), purity, share


def _displacement_from_profiles(profiles) -> np.ndarray:
    """Cumulative signed vertical shift from consecutive row-intensity
    profiles, via sub-pixel cross-correlation. Preserves oscillation
    frequency (unlike rectified frame-difference energy)."""
    if len(profiles) < 2:
        return np.zeros(len(profiles))
    shifts = [0.0]
    max_lag = 6
    for k in range(1, len(profiles)):
        p0 = profiles[k - 1] - profiles[k - 1].mean()
        p1 = profiles[k] - profiles[k].mean()
        corr = np.correlate(p1, p0, mode="full")
        mid = p0.size - 1
        seg = corr[mid - max_lag: mid + max_lag + 1]
        if seg.size == 0:
            shifts.append(0.0)
            continue
        pk = int(np.argmax(seg))
        lag = float(pk - max_lag)
        if 0 < pk < seg.size - 1:
            a, b, c = seg[pk - 1], seg[pk], seg[pk + 1]
            denom = a - 2 * b + c
            if denom != 0:
                lag += 0.5 * (a - c) / denom
        shifts.append(lag)
    return np.cumsum(np.asarray(shifts, dtype=np.float64))


class HealthSignalService:
    def __init__(self):
        self._available = _CV2_OK and _SCIPY_OK
        if self._available:
            print("  ✓ Health-signal service ready (activity, tremor, sway)")
        else:
            print("  ⚠ Health-signal service unavailable (needs cv2 + scipy)")

    @property
    def available(self) -> bool:
        return self._available

    @staticmethod
    def _roi(pose_frames, w: int, h: int):
        """Median pet box (padded) when YOLO saw the pet, else centre region."""
        boxes = [a.bbox for pf in (pose_frames or []) for a in pf.animals]
        if not boxes:
            return int(w * 0.2), int(h * 0.2), max(int(w * 0.8), int(w * 0.2) + 8), \
                   max(int(h * 0.8), int(h * 0.2) + 8)
        arr = np.array(boxes, dtype=np.float64)
        x1, y1, x2, y2 = np.median(arr, axis=0)
        pw, ph = (x2 - x1) * 0.1, (y2 - y1) * 0.1
        return (max(0, int(x1 - pw)), max(0, int(y1 - ph)),
                min(w, max(int(x2 + pw), int(x1) + 8)),
                min(h, max(int(y2 + ph), int(y1) + 8)))

    def analyze(self, video_path: str, pose_frames=None,
                max_seconds: float = 30.0) -> dict:
        """Extract motion-derived health signals. Returns {} when nothing
        can be measured; never raises."""
        if not self._available:
            return {}

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {}

        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            rx1, ry1, rx2, ry2 = self._roi(pose_frames, w, h)
            # Sample every frame: tremor at up to 12 Hz needs >= 24 Hz
            # sampling (Nyquist). Frames are downscaled hard, so this is cheap.
            max_frames = int(min(max_seconds, 60.0) * fps)
            energies, profiles = [], []
            prev = None
            idx = 0
            while idx < max_frames:
                ok, frame = cap.read()
                if not ok:
                    break
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                small = cv2.resize(gray, (96, 54)).astype(np.float32)
                if prev is not None:
                    energies.append(float(np.abs(small - prev).mean()))
                prev = small
                roi = cv2.resize(gray[ry1:ry2, rx1:rx2], (48, 120)).astype(np.float64)
                profiles.append(roi.mean(axis=1))
                idx += 1
        finally:
            cap.release()

        n = len(energies)
        if n < int(_MIN_SECONDS * fps):
            return {}

        sig = np.asarray(energies, dtype=np.float64)
        duration = n / fps
        activity = float(sig.mean())
        # Signed vertical displacement — NOT frame-difference energy.
        # Energy is a rectified signal: an oscillation at f produces energy
        # peaks at 2f, which would report double the true tremor frequency.
        # Cross-correlating consecutive row profiles preserves direction and
        # therefore the true frequency (same approach as respiration_service).
        displacement = _displacement_from_profiles(profiles)

        out = {
            "measured": True,
            "window_sec": round(duration, 1),
            "sample_rate_hz": round(float(fps), 1),
            "activity_level": {
                "value": round(activity, 3),
                "unit": "mean inter-frame motion energy (0-255 scale)",
                "note": ("Comparable only against this pet's own history "
                         "under similar filming conditions — a drop is a "
                         "lethargy screen, not a diagnosis."),
            },
            "not_measured": [
                "per-limb lameness", "stride length", "footfall timing",
                "weight-bearing asymmetry",
            ],
            "limitations": ("Derived from whole-frame motion and the pet's "
                            "bounding box. Gait/lameness assessment requires "
                            "paw-level keypoints; force plates remain the "
                            "clinical standard."),
        }

        # Spectral analysis of the SIGNED DISPLACEMENT signal
        detrended = displacement - displacement.mean()
        if detrended.size > 4:
            # Remove slow drift so oscillation, not travel, drives the PSD.
            win = max(3, int(1.0 * fps) | 1)
            detrended = detrended - np.convolve(detrended, np.ones(win) / win,
                                                mode="same")
        if np.any(detrended) and duration >= 4:
            nperseg = min(detrended.size, int(8 * fps))
            freqs, psd = welch(detrended, fs=fps, nperseg=nperseg)

            loco_f, loco_purity, _ = _band_stats(freqs, psd, LOCOMOTION_BAND_HZ)
            if loco_f is not None:
                out["movement_regularity"] = {
                    "dominant_hz": round(loco_f, 2),
                    "rhythm_purity": round(loco_purity, 3),
                    "interpretation": ("rhythmic" if loco_purity >= 0.30
                                       else "irregular" if loco_purity < 0.15
                                       else "mixed"),
                    "note": ("Rhythm of gross movement. Irregular rhythm has "
                             "many innocent causes (play, camera movement) — "
                             "a screen, not a lameness measure."),
                }

            tre_f, tre_purity, tre_share = _band_stats(freqs, psd, TREMOR_BAND_HZ)
            detected = bool(
                tre_f is not None
                and tre_purity >= _TREMOR_PURITY_MIN
                and tre_share >= _TREMOR_POWER_RATIO_MIN
            )
            out["tremor"] = {
                "detected": detected,
                "frequency_hz": round(tre_f, 2) if tre_f is not None else None,
                "band_power_share": round(tre_share, 3),
                "peak_purity": round(tre_purity, 3),
                "band": f"{TREMOR_BAND_HZ[0]}-{TREMOR_BAND_HZ[1]} Hz",
                "note": ("Periodic motion in the tremor band. Shivering, "
                         "purring contact, panting, and a shaky camera all "
                         "produce similar signals — confirm visually before "
                         "acting."),
            }

        # Postural sway from the pet's bounding-box centroid
        sway = self._postural_sway(pose_frames)
        if sway:
            out["postural_sway"] = sway
        return out

    @staticmethod
    def _postural_sway(pose_frames):
        """Lateral centroid wander normalised to body width — a balance
        screen. Needs enough frames with a detected pet to be meaningful."""
        xs, widths = [], []
        for pf in (pose_frames or []):
            for a in pf.animals:
                x1, _, x2, _ = a.bbox
                xs.append((x1 + x2) / 2.0)
                widths.append(max(1.0, x2 - x1))
        if len(xs) < 8:
            return None
        body_w = float(np.median(widths))
        # Remove linear drift: a pet walking across frame is travelling,
        # not swaying. Residual scatter is the sway signal.
        idx = np.arange(len(xs), dtype=np.float64)
        arr = np.asarray(xs, dtype=np.float64)
        slope, intercept = np.polyfit(idx, arr, 1)
        residual = arr - (slope * idx + intercept)
        sway_ratio = float(np.std(residual) / body_w)
        return {
            "lateral_sway_ratio": round(sway_ratio, 3),
            "unit": "SD of lateral position / body width (drift removed)",
            "samples": len(xs),
            "note": ("Balance screen only. Compare against this pet's own "
                     "baseline; a single elevated value is not a finding."),
        }
