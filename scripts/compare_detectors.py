#!/usr/bin/env python3
"""
Detector shoot-out on YOUR clips: does segmentation cost you detections?

The current detector was chosen on measured detection rate against a real cat
clip (nano 3%, small 34%, medium 49%, large 45%, xlarge 48%), which is the only
honest way to pick one — the headline benchmarks are COCO mAP over eighty
classes, and we care about exactly two.

A `-seg` checkpoint gives an outline instead of a rectangle, which is a better
overlay AND a much tighter region of interest for the three measurements that
sample inside the detection: respiration (chest motion), postural sway (body
width), and the coat signature the identity screen compares. But it is a
different set of weights and it costs inference time, so switch on evidence:

    PYTHONPATH=. python scripts/compare_detectors.py --media clip.mp4
    PYTHONPATH=. python scripts/compare_detectors.py --media ./clips \
        --models yolo11m.pt yolo11m-seg.pt yolo11l-seg.pt

Reported per model, per clip:
    detection_rate   fraction of sampled frames where a cat/dog was found —
                     the number that decides it
    outline_rate     fraction of detections that came with a usable mask
    box_fill         median share of the box that is actually animal, from the
                     mask. This is the size of the problem segmentation solves:
                     everything outside it is background being measured
    sec_per_frame    inference cost

Then set YOLO_MODEL to the winner. Nothing else needs changing — the overlay
draws an outline when there is one and a box when there isn't.
"""
import argparse
import glob
import os
import statistics
import sys
import time

DEFAULT_MODELS = ["yolo11m.pt", "yolo11m-seg.pt"]
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".avi", ".webm")
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".heic", ".webp")


def gather(path: str) -> list:
    if os.path.isdir(path):
        return sorted(f for f in glob.glob(os.path.join(path, "*"))
                      if f.lower().endswith(VIDEO_EXT + IMAGE_EXT))
    return [path]


def run(model_name: str, media: list, sample_fps: float) -> dict:
    os.environ["YOLO_MODEL"] = model_name
    import importlib
    from app.services import yolo_pose_service as Y
    importlib.reload(Y)
    svc = Y.YoloPoseService()
    if not svc.available:
        return {"error": "model unavailable"}

    import cv2
    frames_total = dets = outlines = 0
    fills = []
    t0 = time.time()
    for path in media:
        if path.lower().endswith(IMAGE_EXT):
            pose_frames = svc.process_image(path)
        else:
            pose_frames = svc.process_video(path, sample_fps=sample_fps)
        frames_total += len(pose_frames)
        for pf in pose_frames:
            for a in pf.animals:
                dets += 1
                if a.polygon is None:
                    continue
                outlines += 1
                x1, y1, x2, y2 = a.bbox
                box_area = max(1.0, (x2 - x1) * (y2 - y1))
                fills.append(cv2.contourArea(a.polygon) / box_area)
    elapsed = time.time() - t0
    return {
        "frames": frames_total,
        "detections": dets,
        "outlines": outlines,
        "box_fill": statistics.median(fills) if fills else None,
        "sec_per_frame": elapsed / max(frames_total, 1),
        "segmenting": svc.segmenting,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--media", required=True, help="A clip/photo, or a directory of them")
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    ap.add_argument("--sample-fps", type=float, default=5.0)
    args = ap.parse_args()

    media = gather(args.media)
    if not media:
        print(f"No media found at {args.media}")
        return 1
    print(f"{len(media)} file(s), sampling at {args.sample_fps} fps\n")

    rows = {}
    for name in args.models:
        print(f"→ {name}")
        try:
            rows[name] = run(name, media, args.sample_fps)
        except Exception as e:
            rows[name] = {"error": str(e)}

    print(f"\n{'model':20s} {'frames':>7s} {'detections':>11s} "
          f"{'outlines':>9s} {'box fill':>9s} {'sec/frame':>10s}")
    for name, r in rows.items():
        if "error" in r:
            print(f"{name:20s} {r['error']}")
            continue
        fill = f"{r['box_fill']:.0%}" if r["box_fill"] is not None else "—"
        print(f"{name:20s} {r['frames']:7d} {r['detections']:11d} "
              f"{r['outlines']:9d} {fill:>9s} {r['sec_per_frame']:9.3f}s")

    ok = [(n, r) for n, r in rows.items() if "error" not in r and r["frames"]]
    if len(ok) >= 2:
        best = max(ok, key=lambda kv: kv[1]["detections"])
        print(f"\nMost detections: {best[0]}.")
        seg = [(n, r) for n, r in ok if r["segmenting"] and r["box_fill"]]
        if seg:
            n, r = seg[0]
            print(f"On this media {1 - r['box_fill']:.0%} of the bounding box is NOT "
                  f"the animal — that is the share of background the ROI "
                  f"measurements currently include and the outline removes.")
        print("\nDetection rate decides it. Do not trade it away for a nicer "
              "overlay: an outline on 30% of frames is worse than a box on 50%.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
