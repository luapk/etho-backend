"""
Head-to-head: current COCO-17 YOLO pose vs an animal-pose model.

WHY: our pose oracle runs a HUMAN keypoint model (yolo11n + yolo11n-pose,
COCO-17) on cats and dogs. On a real test clip it detected the cat in 3%
of frames while correctly finding humans in 45% of the SAME frames — the
failure is specific to animals, not to footage quality. This script
quantifies whether an animal-trained model fixes that, on your own media,
before committing to the swap.

The YOLO baseline half runs anywhere. The animal-model half needs weights
that this repo does not vendor — pick ONE:

  A) easy_ViTPose (AP-10K, ONNX — lighter, CPU-friendly)
       pip install easy_ViTPose onnxruntime
       weights: https://huggingface.co/JunkyByte/easy_ViTPose
       run with:  --vitpose /path/to/vitpose-s-ap10k.onnx

  B) DeepLabCut SuperAnimal-Quadruped (zero-shot, heavier)
       pip install "deeplabcut[pytorch]"
       run with:  --superanimal

Usage:
    PYTHONPATH=. python scripts/compare_pose_models.py \
        --media clip.mp4 --vitpose models/vitpose-s-ap10k.onnx --out ./compare

Metrics reported per model:
    detection_rate     frames where the pet was found (the headline number)
    keypoint_yield     mean confident keypoints per detected frame
    centroid_jitter    frame-to-frame box-centre movement, normalised to box
                       width — a good tracker is smooth; a flickering one
                       produces noisy spine angles even when it detects
    spine_available    frames where our spinal-angle metric is computable

NOTE: the author could not execute the animal-model path (model hosts are
unreachable from the dev sandbox), so treat that branch as untested
scaffolding — expect to adjust the API call for your installed version.
The YOLO baseline path IS tested.
"""

import argparse
import os
import sys

import numpy as np

try:
    import cv2
except ImportError:
    sys.exit("opencv is required: pip install opencv-python-headless")

COCO_ANIMAL_CLASSES = {15: "cat", 16: "dog"}
CONF_KP = 0.5


def sample_frames(path: str, every_n: int = 5, cap_frames: int = 400):
    """Return [(t_sec, frame)] sampled from a video, or one frame for images."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".jpg", ".jpeg", ".png", ".webp"):
        img = cv2.imread(path)
        return [(0.0, img)] if img is not None else []
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return []
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    out, i = [], 0
    while len(out) < cap_frames:
        ok, f = cap.read()
        if not ok:
            break
        if i % every_n == 0:
            out.append((i / fps, f))
        i += 1
    cap.release()
    return out


def summarise(name: str, dets: list) -> dict:
    """dets: per-frame [(found: bool, n_conf_kp: int, centroid|None, width|None)]"""
    n = len(dets)
    found = [d for d in dets if d[0]]
    kp = [d[1] for d in found]
    jitter = []
    prev = None
    for f, _, c, w in dets:
        if f and c is not None and w:
            if prev is not None:
                jitter.append(abs(c - prev) / max(w, 1.0))
            prev = c
        else:
            prev = None
    return {
        "model": name,
        "frames": n,
        "detection_rate": len(found) / n if n else 0.0,
        "keypoint_yield": float(np.mean(kp)) if kp else 0.0,
        "centroid_jitter": float(np.median(jitter)) if jitter else None,
        "spine_available": sum(1 for k in kp if k >= 5) / n if n else 0.0,
    }


def run_yolo(frames, conf: float):
    from ultralytics import YOLO
    det = YOLO("yolo11n.pt")
    pose = YOLO("yolo11n-pose.pt")
    out = []
    for _, f in frames:
        r = det(f, classes=list(COCO_ANIMAL_CLASSES), conf=conf, verbose=False)[0]
        if not len(r.boxes):
            out.append((False, 0, None, None))
            continue
        b = max(r.boxes, key=lambda b: float(b.conf[0]))
        x1, y1, x2, y2 = b.xyxy[0].tolist()
        pr = pose(f, verbose=False)[0]
        n_kp = 0
        if pr.keypoints is not None and len(pr.keypoints.data):
            n_kp = int((pr.keypoints.data[0][..., 2] > CONF_KP).sum())
        out.append((True, n_kp, (x1 + x2) / 2, x2 - x1))
    return out


def run_vitpose(frames, onnx_path: str, conf: float):
    """AP-10K ViTPose via easy_ViTPose. UNTESTED — adjust for your version."""
    from easy_ViTPose import VitInference
    model = VitInference(onnx_path, yolo="yolov8s.pt", dataset="ap10k",
                         det_class="cat", is_video=False)
    out = []
    for _, f in frames:
        try:
            keypoints = model.inference(f)
        except Exception as e:
            print(f"  ! ViTPose inference error: {e}")
            out.append((False, 0, None, None))
            continue
        if not keypoints:
            out.append((False, 0, None, None))
            continue
        kps = list(keypoints.values())[0]           # (K, 3) y, x, score
        n_kp = int((kps[:, 2] > CONF_KP).sum())
        xs = kps[kps[:, 2] > CONF_KP][:, 1] if n_kp else np.array([])
        centroid = float(xs.mean()) if xs.size else None
        width = float(xs.max() - xs.min()) if xs.size > 1 else None
        out.append((True, n_kp, centroid, width))
    return out


def run_superanimal(media_path: str):
    """DeepLabCut SuperAnimal-Quadruped. UNTESTED — API varies by version."""
    import deeplabcut
    print("  Running SuperAnimal-Quadruped (first run downloads weights)...")
    deeplabcut.video_inference_superanimal(
        videos=[media_path],
        superanimal_name="superanimal_quadruped",
        model_name="hrnet_w32",
        detector_name="fasterrcnn_resnet50_fpn_v2",
        video_adapt=False,
    )
    print("  SuperAnimal wrote its predictions alongside the video (h5/csv).")
    print("  Load that file to compute the same metrics; this script does not")
    print("  parse it because output naming varies across DLC versions.")
    return None


def main():
    ap = argparse.ArgumentParser(description="YOLO vs animal-pose comparison")
    ap.add_argument("--media", required=True, help="Video or image path")
    ap.add_argument("--conf", type=float, default=0.25, help="Detection confidence")
    ap.add_argument("--every-n", type=int, default=5, help="Sample every Nth frame")
    ap.add_argument("--vitpose", help="Path to AP-10K ViTPose .onnx")
    ap.add_argument("--superanimal", action="store_true")
    ap.add_argument("--out", default="./pose_compare")
    args = ap.parse_args()

    if not os.path.exists(args.media):
        sys.exit(f"Not found: {args.media}")

    frames = sample_frames(args.media, args.every_n)
    if not frames:
        sys.exit("Could not read any frames")
    print(f"\nMedia: {args.media}\nSampled {len(frames)} frame(s) "
          f"at detection confidence {args.conf}\n")

    results = []
    print("Running YOLO (COCO-17, current production model)...")
    results.append(summarise("yolo11n + yolo11n-pose (COCO-17)",
                             run_yolo(frames, args.conf)))

    if args.vitpose:
        print("Running ViTPose AP-10K...")
        try:
            results.append(summarise("ViTPose (AP-10K, animal-trained)",
                                     run_vitpose(frames, args.vitpose, args.conf)))
        except Exception as e:
            print(f"  ! ViTPose unavailable: {e}")

    if args.superanimal:
        print("Running SuperAnimal-Quadruped...")
        try:
            run_superanimal(args.media)
        except Exception as e:
            print(f"  ! SuperAnimal unavailable: {e}")

    print(f"\n{'model':<38} {'detect':>7} {'kp/frame':>9} {'jitter':>8} {'spine':>7}")
    print("-" * 74)
    for r in results:
        j = f"{r['centroid_jitter']:.3f}" if r["centroid_jitter"] is not None else "—"
        print(f"{r['model']:<38} {r['detection_rate']:>6.0%} "
              f"{r['keypoint_yield']:>9.1f} {j:>8} {r['spine_available']:>6.0%}")
    print("-" * 74)
    print("detect = frames where the pet was found (the number that matters)")
    print("kp/frame = mean keypoints above 0.5 confidence when detected")
    print("jitter = median frame-to-frame centroid shift / box width (lower is steadier)")
    print("spine = frames with enough keypoints for our spinal-angle metric")
    print("\nDecision rule: swap models if detection_rate improves substantially")
    print("on clips where the current model fails (odd postures, close-ups,")
    print("recumbent animals) WITHOUT regressing on clips where it works.\n")

    if len(results) < 2:
        print("Only the baseline ran. Supply --vitpose or --superanimal for the")
        print("comparison; see this file's docstring for how to get weights.")


if __name__ == "__main__":
    main()
