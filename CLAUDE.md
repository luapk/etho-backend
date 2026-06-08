# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run locally
uvicorn app.main:app --reload --port 8000

# Install dependencies
pip install -r requirements.txt

# Hit the main endpoint manually
curl -X POST http://localhost:8000/api/video/upload \
  -F "file=@test.mp4" \
  -F "mode=full"

# Download an annotated video after analysis
curl http://localhost:8000/api/video/annotated/{video_id} -o annotated.mp4
```

There are no tests or linters configured. The app is deployed to Railway via Nixpacks — pushing to `main` deploys automatically.

## Architecture

The API is a single FastAPI app (`app/main.py`) with one primary endpoint: `POST /api/video/upload`. Every request runs a **4-step pipeline** sequentially:

```
1. YoloPoseService.process_video()    → pose_frames, pose_metrics
2. Gemini Pass 1 (scene verification) → scene_context (ground truth lock)
3. Gemini Pass 2 (ethological analysis, pose_metrics injected as context)
4. video_annotator.annotate_video()   → annotated MP4 stored in /tmp
```

The annotated video ID is returned in the JSON response as `annotated_video_id` and served from `GET /api/video/annotated/{video_id}`.

### Key design decisions

**Two-pass hallucination prevention:** Gemini runs twice. Pass 1 (`run_scene_verification`) locks in what is literally visible as a JSON ground-truth object. Pass 2 (`analyze_video_with_context`) receives that object as a hard constraint and cannot contradict it. This was the core fix for the original problem of Gemini inventing scenarios.

**YOLO as measurement oracle:** `yolo_pose_service.py` samples video at 5 fps, runs `yolo11n.pt` (detection, classes 15=cat 16=dog) and `yolo11n-pose.pt` (skeleton) separately, then matches skeletons to pet bounding boxes by IoU. The derived metrics — spinal curvature (degrees deviation from nose→shoulder→hip axis), head tilt, detection coverage — are injected as a `## YOLO11-POSE MEASUREMENTS` block in the Pass 2 prompt. Gemini is instructed to cite these measurements when making posture claims rather than using vague language. YOLO uses human-pose keypoints (COCO-17) applied to animals; accuracy is approximate but sufficient for spinal angle trends and visual overlay.

**Video annotator carry-forward:** The annotator samples pose data from YOLO at 5 fps but writes every frame at full fps. It carries the last known bounding box and skeleton forward for 0.8 seconds between samples so the overlay is continuous. Timeline event text and pet-POV text persist on screen until the next event timestamp fires (not just for one frame).

**Graceful YOLO degradation:** If `ultralytics` is not installed or model download fails, `YoloPoseService.available` is `False` and the pipeline skips steps 1 and 4 entirely — Gemini-only analysis still works. The `_yolo` instance is created once at module load in `main.py`, not per-request.

### Service responsibilities

| File | Responsibility |
|------|---------------|
| `app/main.py` | FastAPI app, request validation, pipeline orchestration, file cleanup |
| `app/services/gemini_service.py` | Gemini File API upload, two-pass analysis, JSON parsing, response validation/enrichment |
| `app/services/yolo_pose_service.py` | Per-frame pet detection, keypoint extraction, spinal angle + head tilt calculation, metrics summary |
| `app/services/video_annotator.py` | Frame-by-frame rendering of bounding boxes, skeleton, breed tag, distress meter, event/POV text strips |
| `app/prompts/ethological_prompt.py` | The entire Gemini system prompt — output schema, behavioural frameworks, FACS codes, morphological normalisation rules, YOLO integration guidance |

### Response shape (key fields)

```json
{
  "success": true,
  "data": {
    "species": "dog|cat",
    "breed_detected": "...",
    "morphology_type": "brachycephalic|dolichocephalic|spitz|paedomorphic|standard",
    "overall_assessment": { "distress_score": 0-100, "zone": "green|yellow|red" },
    "visual_analysis": { "facs_codes_detected": [...], "body_language": "..." },
    "audio_analysis": { "vocalizations_detected": [...] },
    "timeline": [{ "timestamp": "0:05", "distress_score": 60, "zone": "yellow" }],
    "interpret_lines": [{ "timestamp": "0:05", "pet_pov": "max 10 words" }],
    "behavioral_markers": [...],
    "advisory": { "headline": "...", "urgency": "routine|elevated|critical" },
    "annotated_video_id": "uuid",
    "_pose_metrics": { "spinal_curvature": { "mean_deg": 18.4 }, "detection_coverage": 0.92 },
    "_verified_scene": { ... }
  }
}
```

Distress zones: green = 0–33, yellow = 34–66, red = 67–100. `validate_and_enrich_response()` in `gemini_service.py` enforces zone/score consistency and applies predator-prey score floor logic when `other_animals_present` contains prey species.

### Ethological frameworks in the prompt

The prompt (`ethological_prompt.py`) encodes peer-reviewed frameworks that Gemini must apply: DogFACS (Waller 2013), CatFACS (Caeiro 2013), Feline Grimace Scale (Evangelista 2019), Morton's motivation-structural rules for vocalisations, tail-wag lateralisation valence (Quaranta 2007), Glasgow Composite Measure Pain Scale, and Umwelt-based first-person pet interpretation. Breed morphology normalisation (brachycephalic, spitz, paedomorphic, etc.) adjusts which signals are weighted — e.g. brachycephalic breeds have facial AU weight reduced 40% because their anatomy makes AU signals unreliable. When editing the prompt, keep the output schema section in sync with `validate_and_enrich_response()` in `gemini_service.py`.

### Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `GEMINI_API_KEY` | Yes | Google Gemini API access |

### Annotated video storage

Annotated videos are written to `/tmp/etho_annotated/{uuid}.mp4` using the `mp4v` codec (OpenCV default). They are ephemeral — each call to `POST /api/video/upload` triggers `cleanup_old_videos()` which deletes files older than 2 hours. On Railway, `/tmp` is cleared on restart. The codec is mp4v (MPEG-4 Part 2); most browsers play it natively inside a `.mp4` container.
