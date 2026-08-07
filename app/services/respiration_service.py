"""
Respiratory-rate measurement from video of a SLEEPING pet.

⚠ SLEEPING PETS ONLY. This measures resting/sleeping respiratory rate (SRR)
— the one respiratory metric with validated home-monitoring science behind
it (sustained sleeping RR above ~30 breaths/min in dogs and cats is a
published early-warning threshold for cardiac decompensation; vets already
ask owners to count it manually). The measurement is physically meaningless
on an awake, moving, or panting animal, so the pipeline only invokes this
service for uploads explicitly tagged context=sleeping_baseline, and the
service itself refuses to report a rate when the clip shows too much
non-respiratory motion.

Method (pure DSP, no ML):
  1. Sample frames at ~10 Hz; crop to the pet region (median YOLO box when
     available, else the central area).
  2. Collapse each crop to a vertical row-intensity profile; estimate the
     frame-to-frame vertical shift by cross-correlating consecutive profiles
     (sub-pixel via parabolic interpolation). Cumulative shift ≈ chest/flank
     displacement.
  3. Detrend, then Welch PSD over the respiratory band 0.10–1.67 Hz
     (6–100 breaths/min); the dominant peak is the rate. Spectral purity
     (peak power / band power) and clip stillness gate the confidence.

This is a screening measurement: the published >=30/min threshold is
REPORTED, never interpreted — the output says "discuss with your vet",
not a diagnosis.

Reported values carry method + confidence and are stored as measured
columns, distinct from AI-estimated scores, like every other oracle.
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

# Respiratory band: 6–100 breaths/min. Sleeping dogs/cats sit ~10–35;
# the wide band lets us SEE an implausibly high reading and reject it
# rather than alias it into range.
BAND_HZ = (0.10, 1.67)

# Published sleeping-RR screening threshold (dogs & cats, veterinary
# cardiology home-monitoring literature). Reported, never interpreted.
SRR_THRESHOLD_BPM = 30

REQUIRES_NOTE = ("Valid ONLY for a pet that is fully asleep (or completely "
                 "at rest), filmed for 30+ seconds with a stable, propped "
                 "camera and the chest/flank visible.")

_MIN_SECONDS = 15.0
# Median whole-frame motion (mean abs pixel diff, 0-255 scale) above this
# means the animal or camera is moving — not a sleeping clip.
_STILLNESS_LIMIT = 2.5


def estimate_rate_from_signal(displacement: np.ndarray, fs: float) -> dict:
    """Dominant respiratory frequency of a displacement signal.

    Pure numpy/scipy — unit-testable without video. Returns bpm, spectral
    purity (peak power / band power, 0-1) and a confidence grade.
    """
    n = displacement.size
    if n < int(_MIN_SECONDS * fs) or fs <= 0:
        return {"breaths_per_min": None, "spectral_purity": 0.0,
                "confidence": "low", "reason": "signal too short"}

    sig = displacement.astype(np.float64)
    # Remove slow drift (posture settling, camera creep): subtract a ~5 s
    # moving average so only oscillatory content remains.
    win = max(3, int(5 * fs) | 1)
    kernel = np.ones(win) / win
    trend = np.convolve(sig, kernel, mode="same")
    sig = sig - trend

    nperseg = min(n, int(30 * fs))
    freqs, psd = welch(sig, fs=fs, nperseg=nperseg)
    band = (freqs >= BAND_HZ[0]) & (freqs <= BAND_HZ[1])
    if not np.any(band) or psd[band].sum() <= 0:
        return {"breaths_per_min": None, "spectral_purity": 0.0,
                "confidence": "low", "reason": "no respiratory-band signal"}

    bf, bp = freqs[band], psd[band]
    peak_idx = int(np.argmax(bp))
    peak_f = bf[peak_idx]

    # Sub-harmonic check: if strong power sits at half the peak frequency,
    # the peak is likely a motion harmonic (each breath can produce two
    # motion pulses) — prefer the fundamental.
    half_mask = np.abs(bf - peak_f / 2) <= (bf[1] - bf[0]) if bf.size > 1 else np.zeros_like(bf, bool)
    if peak_f / 2 >= BAND_HZ[0] and np.any(half_mask):
        if bp[half_mask].max() >= 0.6 * bp[peak_idx]:
            peak_f = peak_f / 2

    purity = float(bp[peak_idx] / bp.sum())
    duration = n / fs
    if purity >= 0.45 and duration >= 30:
        confidence = "high"
    elif purity >= 0.25:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "breaths_per_min": round(float(peak_f * 60), 1),
        "spectral_purity": round(purity, 3),
        "confidence": confidence,
        "reason": None if confidence != "low" else "weak periodic signal",
    }


class RespirationService:
    def __init__(self):
        self._available = _CV2_OK and _SCIPY_OK
        if self._available:
            print("  ✓ Respiration (SRR) service ready — sleeping clips only")
        else:
            print("  ⚠ Respiration service unavailable (needs cv2 + scipy)")

    @property
    def available(self) -> bool:
        return self._available

    # ── ROI selection ────────────────────────────────────────────────────────

    @staticmethod
    def _roi_from_pose(pose_frames, w: int, h: int):
        """Median pet bounding box across sampled frames, padded 10%."""
        boxes = [a.bbox for pf in (pose_frames or []) for a in pf.animals]
        if not boxes:
            # Central 60% fallback when YOLO saw nothing usable
            return int(w * 0.2), int(h * 0.2), int(w * 0.8), int(h * 0.8)
        arr = np.array(boxes, dtype=np.float64)
        x1, y1, x2, y2 = np.median(arr, axis=0)
        pw, ph = (x2 - x1) * 0.1, (y2 - y1) * 0.1
        return (max(0, int(x1 - pw)), max(0, int(y1 - ph)),
                min(w, int(x2 + pw)), min(h, int(y2 + ph)))

    # ── Main entry point ─────────────────────────────────────────────────────

    def analyze(self, video_path: str, pose_frames=None,
                max_seconds: float = 90.0, target_fs: float = 10.0) -> dict:
        """Measure sleeping respiratory rate from a video clip.

        Returns a dict that ALWAYS carries the sleeping-pet requirement.
        usable=False (with a plain-English reason) whenever the clip cannot
        support a trustworthy rate — too short, too much motion, or no clear
        periodic signal. A refused measurement is the honest output.
        """
        base = {
            "usable": False,
            "breaths_per_min": None,
            "requires": REQUIRES_NOTE,
            "threshold_note": (f"Published sleeping-RR screening threshold: "
                               f">{SRR_THRESHOLD_BPM}/min sustained warrants "
                               f"discussing with a vet (reported, not "
                               f"interpreted)."),
            "method": "chest-motion vertical displacement, Welch PSD "
                      f"{BAND_HZ[0]}-{BAND_HZ[1]} Hz",
        }
        if not self._available:
            return {**base, "reason": "respiration service unavailable"}

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {**base, "reason": "could not open video"}

        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            step = max(1, round(fps / target_fs))
            fs = fps / step
            max_frames = int(max_seconds * fps)

            rx1, ry1, rx2, ry2 = self._roi_from_pose(pose_frames, w, h)
            if rx2 - rx1 < 16 or ry2 - ry1 < 16:
                return {**base, "reason": "pet region too small in frame"}

            profiles = []      # per-sample vertical row-intensity profiles
            motions = []       # whole-frame motion per sample (stillness)
            prev_small = None
            idx = 0
            while idx < max_frames:
                ok, frame = cap.read()
                if not ok:
                    break
                if idx % step == 0:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    roi = gray[ry1:ry2, rx1:rx2]
                    roi = cv2.resize(roi, (64, 160)).astype(np.float64)
                    profiles.append(roi.mean(axis=1))
                    small = cv2.resize(gray, (80, 45)).astype(np.float64)
                    if prev_small is not None:
                        motions.append(float(np.abs(small - prev_small).mean()))
                    prev_small = small
                idx += 1
        finally:
            cap.release()

        n = len(profiles)
        duration = n / fs if fs else 0
        if duration < _MIN_SECONDS:
            return {**base, "reason": f"clip too short ({duration:.0f}s of "
                    f"usable footage; need {int(_MIN_SECONDS)}s+, 30s+ ideal)"}

        stillness = float(np.median(motions)) if motions else 99.0
        if stillness > _STILLNESS_LIMIT:
            return {**base, "reason": "too much movement — the pet must be "
                    "asleep and the camera propped still",
                    "motion_level": round(stillness, 2)}

        # Vertical displacement via sub-pixel cross-correlation of profiles
        shifts = [0.0]
        max_lag = 8
        for k in range(1, n):
            p0 = profiles[k - 1] - profiles[k - 1].mean()
            p1 = profiles[k] - profiles[k].mean()
            corr = np.correlate(p1, p0, mode="full")
            mid = p0.size - 1
            lo, hi = mid - max_lag, mid + max_lag + 1
            seg = corr[lo:hi]
            pk = int(np.argmax(seg))
            lag = float(pk - max_lag)
            if 0 < pk < seg.size - 1:   # parabolic sub-pixel refinement
                a, b, c = seg[pk - 1], seg[pk], seg[pk + 1]
                denom = a - 2 * b + c
                if denom != 0:
                    lag += 0.5 * (a - c) / denom
            shifts.append(lag)
        displacement = np.cumsum(np.array(shifts))

        est = estimate_rate_from_signal(displacement, fs)
        result = {
            **base,
            **est,
            "window_sec": round(duration, 1),
            "motion_level": round(stillness, 2),
        }
        if est["breaths_per_min"] is not None and est["confidence"] != "low":
            result["usable"] = True
            result["above_threshold"] = est["breaths_per_min"] > SRR_THRESHOLD_BPM
            print(f"  ✓ SRR: {est['breaths_per_min']} breaths/min "
                  f"({est['confidence']} confidence, {duration:.0f}s)")
        else:
            result["reason"] = result.get("reason") or est.get("reason") \
                or "no clear breathing signal"
            print(f"  ⚠ SRR not measurable: {result['reason']}")
        return result
