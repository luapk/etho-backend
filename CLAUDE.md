# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Monorepo layout

This repo holds both halves of Etho:
- **Backend** (repo root): FastAPI app in `app/`, deployed to Railway via Nixpacks. Nixpacks detects Python from the root `requirements.txt`; the `frontend/` subdirectory does not affect it.
- **Frontend** (`frontend/`): Vite + React + Tailwind SPA, deployed to Vercel. In the Vercel project settings set **Root Directory = `frontend`** (its `vercel.json` handles build/output/rewrites). Imported from the former `luapk/etho-frontend` repo (its git history stays there; the v16 `feat/annotated-video-pose-metrics` branch was never pushed to GitHub — the imported code is v15 `main`).

```bash
# Frontend dev
cd frontend && npm install && npm run dev    # Vite dev server
npm run build                                # production build to frontend/dist
```

Frontend env vars (Vercel): `VITE_API_URL` (Railway backend URL), `VITE_API_KEY` (backend key), `VITE_APP_PASSWORD` (cosmetic gate).

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

The app is deployed to Railway via Nixpacks — pushing to `main` deploys automatically.

```bash
# Run the test suites (stub google/cv2 — no AI deps or API keys needed)
pip install -r requirements-dev.txt
PYTHONPATH=. python tests/run_all.py

# Seed two demo pets with weeks of history (timeline/trends/vet-report demo data)
PYTHONPATH=. python scripts/seed_demo.py     # writes to $DATA_DIR (default ./data)

# Model upgrade workflow (deliberate, in this order)
PYTHONPATH=. python scripts/check_models.py                        # what's available + recommendation
#   → set GEMINI_MODEL=<recommended>
PYTHONPATH=. python scripts/repeatability_study.py --media-dir ./clips   # confirm score consistency
```

**Choosing the analysis model** (`model_selector.py`): ranking is pure/testable — non-video families (embedding, imagen, veo, gemma, tts, native-audio) are excluded, previews excluded unless asked for, then tier preference → newest version → stable over preview → bare alias over dated snapshot. `GEMINI_MODEL` is **pinned by default on purpose**: a longitudinal record needs a stable instrument, so upgrades should be deliberate and followed by the repeatability study. `GEMINI_MODEL=auto` resolves once at import (never per-request), logs what it picked, and falls back to the pinned default if discovery fails. `GET /api/models/available` (admin) does the same discovery from a deployed instance but never switches anything itself.

Test suites use throwaway `DATA_DIR`s and never touch the real database. `scripts/seed_demo.py` refuses to double-seed; delete the DB or point `DATA_DIR` elsewhere to reseed.

## Architecture

The API is a single FastAPI app (`app/main.py`) with two analysis endpoints — `POST /api/video/upload` and `POST /api/image/upload` — plus a longitudinal record layer (pet profiles, analysis history, trends, vet reports). Every video request runs a sequential pipeline:

```
1.  YoloPoseService.process_video()   → pose_frames, pose_metrics
1b. AudioService.analyze()            → audio_metrics (pitch, tonality, purr-band, events)
2.  Gemini Pass 1 (scene verification)→ scene_context (ground truth lock)
3.  Gemini Pass 2 (ethological analysis, pose_metrics + audio_metrics injected as context)
4.  video_annotator.annotate_video()  → annotated MP4 stored in /tmp
```

The annotated video ID is returned in the JSON response as `annotated_video_id` and served from `GET /api/video/annotated/{video_id}` (which also serves annotated stills as `.jpg`). Image uploads run the same pipeline minus audio and with a single-frame YOLO pass; Gemini receives an IMAGE MODE addendum (single-entry timeline, no invented motion/sound).

### Longitudinal record layer (v17)

Analyses can be logged against pet profiles, turning one-shot results into a record over time:

```
POST  /api/pets                         create profile (name, species, breed, sex, birthdate, weight)
GET   /api/pets                         list with analysis counts
PATCH /api/pets/{id}                    update profile
POST  /api/video/upload?pet_id=...      analysis is logged to that pet (pet_id optional everywhere)
GET   /api/pets/{id}/history            chronological indexed metrics (for timeline/chart UI)
GET   /api/pets/{id}/trends             baseline ± SD, latest deviation, slope (pts/week), red flags
GET   /api/analyses/{id}                full stored raw result (provenance)
GET   /api/pets/{id}/vet-report?format=markdown|json&reason=...   pre-consultation document
GET   /api/pets/{id}/timeline           unified feed: analyses + weight entries, chronological;
                                        each analysis carries its per-asset distress_curve
                                        (sparkline-ready), zone, instrument total, quality grade,
                                        context tag — built for a scrubbable timeline UI
POST  /api/pets/{id}/weights            log a weight (syncs profile weight_kg, returns screening)
GET   /api/pets/{id}/weights            weight log + breed-range assessment
```

**Weight screening** (`breed_reference.py`): typical adult ranges for ~40 dog and ~16 cat breeds (substring-matched, species-level fallback for cats only — dog breeds vary too widely). Status below/within/above range with percent outside. Always framed as a rough screen: body condition score (BCS) by a vet is the clinical standard, and every output says so. The vet report gets a Weight section (latest vs range, delta over time, full log).

**Per-asset temporal data**: every analysis's `timeline` array (per-timestamp distress/zone) is preserved in `full_json`; `get_timeline_feed()` extracts it as `distress_curve` ([{t_sec, distress_score, zone}]) so frontends render per-asset graphs without fetching full records.

Storage is SQLite (stdlib, no new deps) at `$DATA_DIR/etho.db` (`pet_store.py`, default `./data`). **On Railway, mount a volume and set `DATA_DIR` to it — otherwise records are lost on redeploy.** Every analysis row stores the complete raw result JSON plus indexed metric columns, stamped with `pipeline_version` / `prompt_version` / `model_used` (bump `PROMPT_VERSION` in `ethological_prompt.py` when the prompt changes).

### Auth model (v17.1)

Two key tiers resolved by `get_auth` in `main.py`:
- **Admin** — the `API_KEY` env var. Sees all pets, creates owners (`POST /api/owners`, admin-only). With `API_KEY` unset, everything is open admin-like (local dev only — always set it in production).
- **Owner** — per-guardian keys minted by `POST /api/owners` (returned once, prefixed `etho_`; only the SHA-256 hash is stored). Owners see only their own pets/analyses; pets created with an owner key are owned by that owner and uploads log with `owner_id`.

Rules: cross-owner access returns **404, never 403** (don't confirm other guardians' pets exist); pet ownership is validated **before** the pipeline runs so a bad `pet_id` fails fast instead of after a full Gemini analysis.

### Capture protocol & quality feedback (v17.1)

`capture_quality.py` holds the versioned capture protocol (`GET /api/capture-protocol`, public) and `assess()`, which attaches a `capture_quality` block to every analysis: framing (YOLO detection coverage), duration, audio presence, brightness, resolution, and face visibility (nose + eye keypoints from YOLO; low visibility warns that grimace/facial items may not be scorable, and the Pass 2 prompt tells Gemini to mark them `visible=false` rather than infer) — each check reporting measured value + threshold + advice. `scripts/repeatability_study.py` runs the test-retest consistency study (same clips × N runs, per-clip SD/CV verdicts) — run it after any model or prompt change. Grades: good/fair/poor. **Quality is feedback, never a gate** — a poor incident clip is still analysed. Uploads accept `?context=weekly_baseline|incident|post_vet|other`, stored per record and shown in the vet report's observation log. Media probes live in `video_annotator.py` (`probe_video_meta`/`probe_image_meta`) and return `{}` on any failure.

Scientific-validity rules encoded in this layer:
- **Measured vs AI-estimated are never mixed** — YOLO/DSP columns are labelled measured; distress/instrument scores are labelled AI-estimated, in both the DB layout and the vet report.
- **Instrument scoring** (`instrument_scores` in the schema): cats get the Feline Grimace Scale (validated on stills, 5 items 0–2, ≥4/10 published threshold *reported, not interpreted*); dogs get an explicitly-labelled non-validated observable subset of Glasgow CMPS-SF. `validate_and_enrich_response()` clamps item scores, nulls invisible items, and recomputes totals — never trusts the model's self-reported total.
- **Each pet is its own control**: baseline = mean ± SD of prior observations (≥3), deviation flagged at ≥1.5 SD, slope = least-squares points/week (≥4). Formulas are stated verbatim in the report's methodology section.
- **Vet reports contain observations, never diagnoses**, and always carry the methodology/limitations section and disclaimer (`vet_report.py`).

### Key design decisions

**Two-pass hallucination prevention:** Gemini runs twice. Pass 1 (`run_scene_verification`) locks in what is literally visible as a JSON ground-truth object. Pass 2 (`analyze_video_with_context`) receives that object as a hard constraint and cannot contradict it. This was the core fix for the original problem of Gemini inventing scenarios.

**YOLO as measurement oracle:** `yolo_pose_service.py` samples video at 5 fps, runs `yolo11n.pt` (detection, classes 15=cat 16=dog) and `yolo11n-pose.pt` (skeleton) separately, then matches skeletons to pet bounding boxes by IoU. The derived metrics — spinal curvature (degrees deviation from nose→shoulder→hip axis), head tilt, detection coverage — are injected as a `## YOLO11-POSE MEASUREMENTS` block in the Pass 2 prompt. Gemini is instructed to cite these measurements when making posture claims rather than using vague language. YOLO uses human-pose keypoints (COCO-17) applied to animals; accuracy is approximate but sufficient for spinal angle trends and visual overlay.

**Audio as measurement oracle:** `audio_service.py` is the acoustic counterpart to the YOLO oracle. It extracts the audio track via `ffmpeg` (mono, 22050 Hz, capped at 120 s) and computes *measured* acoustics with numpy/scipy: fundamental frequency (F0 via autocorrelation with octave-error mitigation + parabolic interpolation), tonality (spectral flatness), the 220–520 Hz solicitation-purr band ratio (McComb 2009), and energy-based vocalization-event segmentation with per-event pitch/contour/tonality. These are injected as a `## AUDIO ACOUSTIC MEASUREMENTS` block in the Pass 2 prompt. Division of labour: **Gemini identifies *what* a sound is** (bark/meow/growl/purr); **the DSP supplies the numbers Gemini can't hear precisely** (Hz, tonal-vs-noisy, purr-band energy), so Morton's-rule claims cite measurements instead of vague language. The per-event Morton labels the service emits are heuristic priming, not final verdicts.

**Graceful audio degradation:** If `ffmpeg` is not on PATH or `scipy` is unavailable, `AudioService.available` is `False` and step 1b is skipped — the rest of the pipeline is unaffected. If the video simply has no audio track, `analyze()` returns `{}` and no audio block is injected. The `_audio` instance is created once at module load in `main.py`. Note: audio runs whenever available, independent of the `annotate` flag (unlike YOLO, which is gated on `annotate` because the annotated video needs it).

**Video annotator carry-forward:** The annotator samples pose data from YOLO at 5 fps but writes every frame at full fps. It carries the last known bounding box and skeleton forward for 0.8 seconds between samples so the overlay is continuous. Timeline event text and pet-POV text persist on screen until the next event timestamp fires (not just for one frame).

**Graceful YOLO degradation:** If `ultralytics` is not installed or model download fails, `YoloPoseService.available` is `False` and the pipeline skips steps 1 and 4 entirely — Gemini-only analysis still works. The `_yolo` instance is created once at module load in `main.py`, not per-request.

### Service responsibilities

| File | Responsibility |
|------|---------------|
| `app/main.py` | FastAPI app, request validation, pipeline orchestration, file cleanup |
| `app/services/gemini_service.py` | Gemini File API upload, two-pass analysis, JSON parsing, response validation/enrichment |
| `app/services/yolo_pose_service.py` | Per-frame pet detection, keypoint extraction, spinal angle + head tilt calculation, metrics summary |
| `app/services/audio_service.py` | ffmpeg audio extraction, pitch (F0) / tonality / purr-band measurement, vocalization-event segmentation, acoustic metrics summary |
| `app/services/pet_store.py` | SQLite pet profiles + analysis history, indexed metrics, baseline/trend/red-flag computation |
| `app/services/vet_report.py` | Pre-consultation report builder (structured JSON + rendered Markdown) |
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
    "_audio_metrics": {
      "audio_present": true,
      "pitch": { "mean_hz": 575.0, "min_hz": 350.0, "max_hz": 800.0 },
      "tonality": { "mean_flatness": 0.43, "interpretation": "mixed" },
      "solicitation_purr": { "possible": false, "peak_purr_band_ratio": 0.12 },
      "vocalization_events": [
        { "timestamp_sec": 5.0, "pitch_hz": 800.0, "pitch_contour": "rising", "tonality": "tonal", "morton_inference": "..." }
      ]
    },
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
| `GEMINI_MODEL` | No | Gemini model ID (default `gemini-2.5-flash`), or `auto` to resolve the newest suitable model at startup. Every analysis row is stamped with the model that produced it, so upgrades don't corrupt longitudinal comparisons |
| `GEMINI_MODEL_TIER` | No | Tier preference when `GEMINI_MODEL=auto`: `flash` (default), `pro`, `flash-lite` |
| `API_KEY` | Production | X-API-Key auth on upload/pets/research endpoints (skipped if unset — local dev only) |
| `DATA_DIR` | Production | Directory for the SQLite longitudinal DB (mount a Railway volume here; default `./data` is ephemeral) |

### System dependencies

Audio analysis requires the `ffmpeg` binary on PATH. It is installed at build time via `nixpacks.toml` (`aptPkgs = ["ffmpeg"]`, additive to the auto-detected Python setup). Without it, `AudioService.available` is `False` and audio analysis is skipped — everything else still works. `scipy` (in `requirements.txt`) provides the DSP primitives.

### Annotated video storage

Annotated videos are written to `/tmp/etho_annotated/{uuid}.mp4` using the `mp4v` codec (OpenCV default). They are ephemeral — each call to `POST /api/video/upload` triggers `cleanup_old_videos()` which deletes files older than 2 hours. On Railway, `/tmp` is cleared on restart. The codec is mp4v (MPEG-4 Part 2); most browsers play it natively inside a `.mp4` container.
