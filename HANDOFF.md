# Etho — Project Handoff

**Updated:** 2026-08-08
**Repo:** github.com/luapk/etho-backend (monorepo — backend + frontend)
**Backend version:** 17.1.0 · **Prompt version:** 6.2 · **Tests:** 226 passing

---

## What Etho is

A pet behaviour and welfare tool. A guardian uploads photos or videos of their
pet; Etho returns a structured ethological analysis, an annotated video, and —
the part that matters — accumulates those observations into a **longitudinal
record** that produces a pre-consultation report a vet can actually use.

It started as a one-shot analyser. It is now a record-keeping instrument.

---

## The design principle everything follows

**Measured and AI-estimated values are never mixed, and nothing is reported
that cannot be justified.**

Three "oracles" produce genuine measurements (signal processing, no AI):

| Oracle | Measures | File |
|---|---|---|
| Detection | pet present, bounding box, coverage | `yolo_pose_service.py` |
| Audio | pitch (F0), tonality, purr-band, vocal events, cough-like count | `audio_service.py` |
| Respiration | sleeping respiratory rate | `respiration_service.py` |
| Motion | activity, tremor, sway, movement regularity | `health_signals.py` |

Gemini receives those numbers as ground truth and does what it is good at:
identifying *what* is happening. It never invents the numbers.

Everywhere a value appears — API, database columns, vet report, video overlay
— it is labelled **Measured** or **AI-estimated**. Where a measurement cannot
be trusted, the system reports *nothing* rather than a guess. This is the rule
that most of the recent work has been about enforcing.

---

## Architecture

```
Vercel (frontend/)  ──►  Railway (backend)  ──►  Google Gemini
   React SPA               FastAPI + DSP           analysis model
```

Video pipeline (`app/main.py`):

```
1.  YOLO detection (yolo11m)         → boxes, coverage
1b. Audio DSP                        → pitch, tonality, events, coughs
1c. Respiration  [sleeping clips only] → breaths/min
1d. Motion health signals            → activity, tremor, sway
2.  Gemini Pass 1                    → scene verification (ground-truth lock)
3.  Gemini Pass 2                    → analysis, constrained by 1–2
4.  Annotator                        → H.264 MP4 + original audio, overlays
4b. Evidence stills                  → one frame per instrument item
5.  Log to record                    → dated by CAPTURE time, not upload time
```

### Services

| File | Responsibility |
|---|---|
| `main.py` | API, orchestration, auth, batch jobs, setup diagnostics |
| `gemini_service.py` | Two-pass analysis, model selection, response validation |
| `yolo_pose_service.py` | Pet detection (pose disabled — see Limitations) |
| `audio_service.py` | Acoustic measurement + cough screen |
| `respiration_service.py` | Sleeping respiratory rate (sleeping clips only) |
| `health_signals.py` | Activity, tremor, postural sway, movement regularity |
| `media_metadata.py` | Capture-time extraction (EXIF / container / filename) |
| `pet_store.py` | SQLite records, owners, weights, trends, timeline feed |
| `vet_report.py` | Pre-consultation document (JSON + Markdown) |
| `capture_quality.py` | Capture protocol + per-upload quality feedback |
| `breed_reference.py` | Breed weight ranges (screening only) |
| `model_selector.py` | Gemini model discovery and ranking |
| `video_annotator.py` | Annotated video/stills, evidence frames, media probes |

---

## Setup — four values

Full click-by-click version with troubleshooting: **`SETUP.md`**.

**Railway:** `GEMINI_API_KEY`, `API_KEY` (any long random string), and **mount a
volume at `/data`**. No `DATA_DIR` needed — the volume is auto-detected. Without
a volume, every pet record is wiped on each deploy.

**Vercel:** `VITE_API_URL` (Railway URL), `VITE_API_KEY` (same string as
`API_KEY`), repo = `luapk/etho-backend`, **Root Directory = `frontend`**, then
redeploy.

**Order matters:** do Vercel first, confirm the site works, *then* set `API_KEY`
on Railway — otherwise uploads 401 in the gap.

**Verify:** open `https://<railway-url>/health` — the `setup` block lists five
checks, each either OK or a plain-English fix. The same checklist prints to the
Railway deploy log on every boot.

---

## Key capabilities

**Longitudinal record.** Pet profiles; every analysis stored with full raw JSON
plus indexed metric columns, stamped with pipeline/prompt/model versions so
records stay comparable across upgrades. Baselines are **per-pet** (each animal
is its own control): mean ± SD of prior observations, deviation flagged at
≥1.5 SD, least-squares slope in points/week.

**Capture time, not upload time.** Records are dated by when the media was
*recorded* — EXIF for photos, container metadata for videos, filename patterns
as fallback (messaging apps strip metadata). Without this, importing a phone
backlog would stack months of history onto one day.

**Batch import.** `POST /api/batch/upload`, up to 30 mixed photos/videos,
processed in the background with `GET /api/batch/{id}` for progress. Each file
lands at its own capture date.

**Instrument scoring.** Cats get the Feline Grimace Scale (validated on stills);
dogs get an explicitly-labelled *non-validated* observable subset of Glasgow
CMPS-SF. Occluded items must be marked `visible: false`, never guessed. Totals
are recomputed server-side — the model's self-reported total is never trusted.
Every scored item carries an evidence still showing the exact frame.

**Sleeping respiratory rate.** Runs **only** on clips tagged
`context=sleeping_baseline`; refuses clips that are too short or too active.
Published >30/min screening threshold is *reported, never interpreted*.

**Vet report.** `GET /api/pets/{id}/vet-report?format=markdown` — signalment,
trend summary, flagged events, observation log (measured vs AI-estimated
columns separated, plus capture quality), weight screening, respiratory
section, recurring markers, methodology with the formulas stated verbatim, and
a disclaimer. Observations, never diagnoses.

**Multi-tenant auth.** Admin key (env `API_KEY`) vs per-owner keys minted by
`POST /api/owners` (returned once, only SHA-256 hash stored). Cross-owner
access returns **404, never 403** — a 403 would confirm another guardian's pet
exists.

---

## Honest limitations

Read this section before promising anything to a user or a vet.

**1. Pose estimation is DISABLED — and should stay that way for now.**
The only available weights are human-trained (COCO-17). On a clear frontal
frame of a sitting pug the model returned 13/17 keypoints at 0.92–0.98
confidence — shoulders, elbows, wrists, hips, knees, ankles — having fitted a
*standing human* to the dog. No nose, no eyes. The spinal-angle code then
substituted a hardcoded `[0,-1]` vector for the missing nose, so the angle was
computed from fabricated input, producing 75° mean / 165° peak and "extreme
fear crouch" for a calm dog. Spinal curvature, head tilt, and face visibility
are therefore **not reported at all**. Re-enable only with an animal-trained
model: `YOLO_POSE_MODEL=… ENABLE_POSE=1`, validated via
`scripts/compare_pose_models.py`.

**2. The distress score is an unvalidated AI estimate.** Run
`scripts/repeatability_study.py` before trusting trend slopes — same clips × N
runs, reports per-clip SD. Target SD ≤ 5 points.

**3. Respiratory numbers are unvalidated on real footage.** Synthetic clips
recover 18/24/36 bpm exactly, but run `scripts/validate_respiration.py` against
real sleeping clips with manual counts. Ship numbers only at MAE ≤ 3 bpm.

**4. No per-limb gait or lameness.** Stride length, footfall timing and
weight-bearing asymmetry need paw-level keypoints. Force plates remain the
clinical standard; `health_signals.py` says so in its own output.

**5. Detection still misses hard cases.** yolo11m manages 98% on a clear pug,
but only 51% on a cat lying flat on wet pavement. Odd postures are exactly the
clinically interesting ones.

**6. The frontend is the old v15 UI.** It works against the new backend, but
none of the longitudinal features (timeline, vet reports, weights, breathing
rate, batch import) have screens. **This is the largest outstanding piece of
work.**

**7. The API key is in the frontend bundle.** It keeps casual traffic out; it
is not real security. Per-owner keys plus proper accounts are the fix.

**8. Batch progress is in-memory.** Lost on restart — but completed analyses
are already persisted, so only the progress view disappears.

---

## Testing & tooling

```bash
pip install -r requirements-dev.txt
PYTHONPATH=. python tests/run_all.py        # 226 checks, no API keys needed

PYTHONPATH=. python scripts/seed_demo.py    # two demo pets with weeks of history
PYTHONPATH=. python scripts/check_models.py # Gemini model discovery + recommendation
PYTHONPATH=. python scripts/repeatability_study.py --media-dir ./clips
PYTHONPATH=. python scripts/validate_respiration.py --media-dir ./srr_clips
PYTHONPATH=. python scripts/compare_pose_models.py --media clip.mp4 [--vitpose …]
```

Suites stub the AI deps and use throwaway `DATA_DIR`s — the real database is
never touched. `seed_demo.py` creates Miso (a cat with a 9-week worsening arc
that trips every red-flag rule) and Bruno (a healthy control), so the timeline,
trends and vet report all have realistic data with no media or API keys.

---

## What real test clips taught us

Two clips changed the product more than any amount of reasoning did. Keep
testing on real footage.

- **Cat lying flat on wet pavement** — yolo11n detected it in **3%** of frames
  while correctly finding *humans* in 45% of the same frames. That isolated the
  failure to animals, not footage quality, and led to the detector upgrade
  (nano→medium, 3%→49%).
- **Pug sitting calmly on a beach** — detection was fine (98%), but the pose
  model confidently reported "extreme fear crouch" for a relaxed dog. That
  exposed the fabricated-nose fallback and led to pose being disabled entirely.

Both clips were silent screen recordings, and the audio oracle correctly
reported "no usable audio" rather than inventing acoustics.

---

## Roadmap, in priority order

1. **Frontend rebuild** — timeline UI, analysis view, vet-report export. A
   design preview built from real API payloads exists; see the artifact link in
   the project history. Backend endpoints are ready.
2. **Animal-trained pose model** (AP-10K / SuperAnimal) — unlocks spinal
   metrics, per-limb gait, and facial landmarks in one move. Weight hosts were
   unreachable from the dev sandbox; run the comparison locally.
3. **Validation studies** — repeatability (distress) and respiration (MAE).
   Both scripts exist and are waiting on real media.
4. **Facial landmark model** (CatFLW / DogFLW) — would turn Feline Grimace
   Scale scoring from AI-estimated into measured. Biggest single credibility
   upgrade available.
5. **Validated owner questionnaires** (LOAD / CBPI / HCPI / FMPI) — cheap,
   genuinely validated, complements the automated signals. Deliberately
   deferred in favour of media-derived automation.
6. **Media archival** (S3/R2) — so vet reports can link to source clips.

---

## Research grounding

The prompt encodes DogFACS (Waller 2013), CatFACS (Caeiro 2013), Feline Grimace
Scale (Evangelista 2019), Morton's motivation-structural rules (1977), tail-wag
lateralisation (Quaranta 2007), Glasgow CMPS, and Umwelt-based first-person
interpretation, with breed-morphology normalisation. Reference cards and a
BibTeX library live in `research/`, downloadable via `GET /api/research/bundle`.

`CLAUDE.md` carries the detailed technical documentation — read it before
changing any measurement code, particularly the sections on why pose is
disabled and why signed displacement is used instead of frame-difference energy.
