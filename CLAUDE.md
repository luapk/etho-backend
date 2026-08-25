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

# Before switching on the coat-colour half of the identity screen
PYTHONPATH=. python scripts/validate_identity.py   # do within-pet and between-pet distances separate?
#   → only if they do: set IDENTITY_APPEARANCE=1

# Before switching the detector (e.g. to a -seg model for outlines)
PYTHONPATH=. python scripts/compare_detectors.py --media ./clips
#   → detection rate decides it; never trade it away for a nicer overlay
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
GET   /api/pets                         list with analysis counts + has_avatar
PATCH /api/pets/{id}                    update profile (the Pet Profile screen)
POST  /api/pets/{id}/avatar             set a profile picture (centre-cropped square)
GET   /api/pets/{id}/avatar             fetch it (owner-scoped)
DELETE /api/pets/{id}/avatar            remove it
POST  /api/pets/{id}/wallpaper          set the full-screen background photo
POST  /api/pets/{id}/wallpaper/from-avatar   reuse the profile picture as the background
GET   /api/pets/{id}/wallpaper          fetch it (owner-scoped)
DELETE /api/pets/{id}/wallpaper         remove it
POST  /api/video/upload?pet_id=...      analysis is logged to that pet (pet_id optional everywhere)
GET   /api/pets/{id}/history            chronological indexed metrics (for timeline/chart UI)
GET   /api/pets/{id}/trends             baseline ± SD, latest deviation, slope (pts/week), red flags
GET   /api/pets/{id}/capture-plan       what's worth filming next, and why (breed-driven)
GET   /api/pets/{id}/breed-context      population predispositions for the CONFIRMED breed
GET   /api/analyses/{id}                full stored raw result (provenance) + has_poster/has_media
PATCH /api/analyses/{id}                correct the observation date (stamped capture_time_source=manual)
                                        and/or refile it under another pet (pet_id)
DELETE /api/analyses/{id}               remove an observation, its poster and its clip (permanent)
GET   /api/analyses/{id}/poster         timeline thumbnail (JPEG, owner-scoped)
GET   /api/analyses/{id}/media          stored annotated clip/photo (404 once evicted)
GET   /api/pets/{id}/vet-report?format=markdown|json&reason=...   pre-consultation document
GET   /api/pets/{id}/timeline           unified feed: analyses + weight entries, chronological;
                                        each analysis carries its per-asset distress_curve
                                        (sparkline-ready), a 48-bucket audio_envelope +
                                        vocal_events on the same time axis, zone, instrument
                                        total, quality grade, context tag
POST  /api/batch/upload                 batch import (photos+videos, max 30) — returns batch_id
GET   /api/batch/{batch_id}             batch progress (in-memory; analyses persist regardless)
POST  /api/pets/{id}/weights            log a weight (syncs profile weight_kg, returns screening)
GET   /api/pets/{id}/weights            weight log + breed-range assessment
```

**Undated media can be corrected by hand** (`PATCH /api/analyses/{id}`): roughly a fifth of a camera roll has no usable capture date — screenshots and anything saved from a messaging app lose it — and those land on the upload day, which bends every trend running through them. The guardian usually knows the real date, and the observation detail view asks for it when `capture_time_source` is `unknown` or `filename`. A hand-set date is stored as `capture_time_source="manual"`, never disguised as EXIF: a typed date and a read-from-file date are both legitimate but they are not the same evidence, and the vet report prints which.

**Capture time, not upload time** (`media_metadata.py`): every record is dated by when the media was RECORDED — EXIF `DateTimeOriginal` for photos, container `creation_time` for videos, filename patterns (`IMG_20260315_143022`, `PXL_…`, WhatsApp `IMG-20260315-WA…`) as a fallback since messaging apps strip metadata. Without this, importing a phone backlog would stamp months of history onto a single day and destroy the record. `created_at` = observation date; `uploaded_at` = when it reached us; `capture_time_source` (exif|video_metadata|filename|unknown) makes every date auditable.

**Motion-derived health signals** (`health_signals.py`): activity level (lethargy screen), movement regularity, tremor (4–12 Hz band), and postural sway (balance screen) — all from whole-frame motion and the pet's bounding box, so no paw-level keypoints required. **Uses signed displacement, not frame-difference energy**: energy is rectified and would report double the true frequency. Explicitly does NOT measure per-limb lameness, stride length, footfall timing, or weight-bearing asymmetry — those need AP-10K/DeepLabCut-class pose, and force plates remain the clinical standard. The audio service additionally flags `cough_like` events (short, aperiodic, broadband) and counts them — heuristic, confirmed by Gemini.

**Breed predispositions are a third kind of claim** (`breed_health.py`): not measured from the animal, not AI-estimated from their footage — a population base rate about a *group*. Merging it into either existing column would silently turn "Cavaliers commonly develop MMVD" into "your Cavalier has MMVD". Three rules keep it quarantined, and they're load-bearing:

1. **It never reaches Gemini.** Not Pass 1, not Pass 2. Tell the model a breed is prone to BOAS and it will see BOAS — the identical failure mode that got pose estimation switched off. Pass 1 is a ground-truth lock and Pass 2 *must* honour it, so a prior injected upstream becomes a mandatory hallucination. A test asserts the prompts contain none of these terms and that `gemini_service.py` never imports the module.
2. **It never moves a score.** A distress number that reflects breed instead of the animal destroys the per-pet baseline design.
3. **Guardian-confirmed breeds only.** `breed_detected` is a guess from one frame; epidemiology layered on a guess is not evidence. The only sanctioned use is `suggest_breed()`, which offers a breed for a human to ratify once several analyses agree.

Its primary output is not a warning but a **capture plan** (`GET /api/pets/{id}/capture-plan`): predispositions Etho has a real measurement for become an ask for the footage that produces it. A Maine Coon's HCM risk renders as "film them asleep" → SRR → the published >30/min threshold, because resting respiratory rate is the at-home measure vets actually use for cardiac and airway disease. A base rate that generates evidence earns its place; one that only generates worry does not. Predispositions we can screen for *nothing* on (IVDD, corneal ulceration, bloat) are stated with an explicit limitation rather than quietly dropped — the bloat entry tells the guardian to call an emergency vet instead of filming. The vet report gets the same data as a cited appendix, structurally separated from every observed field.

Deliberately NOT built: any combined breed × observation risk score (a diagnosis with extra steps, and a medical-device claim), odds ratios shown to guardians (meaningless without absolute base rates), and breed life-expectancy figures.

**Weight screening** (`breed_reference.py`): typical adult ranges for ~40 dog and ~16 cat breeds (substring-matched, species-level fallback for cats only — dog breeds vary too widely). Status below/within/above range with percent outside. Always framed as a rough screen: body condition score (BCS) by a vet is the clinical standard, and every output says so. The vet report gets a Weight section (latest vs range, delta over time, full log).

**Deleting an observation is a hard delete** (`DELETE /api/analyses/{id}`): the row, the poster and the clip all go. Not a soft-delete flag — a guardian removing a bad capture (wrong animal, useless clip) means it should stop affecting the baseline, and an archived row that still counted toward the trend would be a worse lie than no row at all. The control lives in the observation detail view, after the media and analysis are on screen, rather than as an × on a timeline tile: a small delete target beside a tap-to-open thumbnail is a mis-tap waiting to happen, and you should see what you are about to destroy. Two steps, and the second names what goes.

**Is this the same animal?** (`identity_check.py`): one misfiled clip puts a stranger's scores into a pet's baseline, and every deviation, slope and red flag is measured against that baseline — so each upload is screened against the pet it was filed under. It is **not** pet re-identification (an open research problem needing a purpose-trained embedding model); it is a guardrail built from two measured signals, treated very differently:

1. **Species** — YOLO detects by class, so a box exists only because the detector decided cat or dog. Profile says cat, every frame says dog → raise it. This is the half that works, and it needs no calibration.
2. **Coat colour** — an HSV histogram over the middle of the detection box, averaged over ~5 frames, compared by total-variation distance. Discriminative for a black cat against a ginger one, useless for two tabbies, and moved by lighting as much as by identity. It only speaks when a capture sits further from the pet's own previous captures than those sit from each other (≥3 priors, the same "each pet is its own control" rule as the distress baseline) — **and the alarm is OFF by default** (`IDENTITY_APPEARANCE=1`). The threshold has never been measured on real captures, and a wrong "is this really your pet?" teaches a guardian that this app's warnings are noise, which the red flags cannot afford. The measurement still runs and is stored (`coat_sig`) so `scripts/validate_identity.py` can report whether within-pet and between-pet distances actually separate on real data. Same posture as `ENABLE_POSE`: computed, kept, inspectable, not yet allowed to speak.

Three rules, the same three that quarantine `breed_health.py`: **it never reaches Gemini** (it runs after Pass 2 — telling the model an animal might be the wrong one invites it to go and find differences, and Pass 1 is a lock Pass 2 must honour; a test asserts neither `gemini_service.py` nor the prompt imports it), **it never moves a score**, and **it never blocks or reassigns** — the upload is analysed and logged exactly as asked. It produces a question with the fix attached: `PATCH /api/analyses/{id}` with `pet_id` refiles the observation, and both pets' baselines recompute from what they now own, which is why moving beats delete-and-re-upload.

**The pet's photo as wallpaper** (`media_store.py`, `{pet_id}_wallpaper.jpg`): a full-screen background behind that pet's pages, uploaded from the camera roll or copied from the profile picture. Deliberately **not** offered from the stored captures — everything in the media library is annotated, so a "photo from the timeline" would arrive with a detection box and a distress meter burned into it. Not square-cropped like the avatar (it is rendered `object-fit: cover` at every phone shape, so cropping twice throws away the margin the browser needs), scaled to a 1440px longest edge, and permanent alongside posters and avatars. The scrim is load-bearing: every card in the app is translucent glass, so an arbitrary photo behind it means white type landing on a white cat. A 6px blur removes the high-frequency detail that actually breaks small type — whiskers and grass edges, more than overall brightness — which then lets the dark wash be *lighter* than it would otherwise need to be, so more of the pet shows through, not less. Verified legible against a deliberately bright, noisy worst-case image.

**Every observation keeps its picture** (`media_store.py`): the timeline filmstrip shows a stored poster per capture, and tapping one reopens the complete analysis — the same screen the guardian saw on upload, rendered from the stored `full_json`, not a cut-down "history view" that would drift into a worse product. See *Annotated video storage* below for the retention rules.

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
- **Trend wording is not the trend maths** (`_trend_reading` in `pet_store.py`): the slope stays a number — `points_per_week`, `total_change`, `exceeds_variation` — and the vet report prints it verbatim. What a *guardian* sees is a separate `reading` block (headline / detail / tone), because two things go wrong otherwise. "Worsening" is frightening AND it's an interpretation, the one thing this codebase refuses to do elsewhere. And a pet whose every observation sits in the green band can still produce a positive slope from ordinary variation — telling their owner the pet is worsening while nothing has ever left the calm zone is alarming them over noise. So: a reading only sounds concerned when the SCORES warrant it (not the gradient), and a drift smaller than the pet's own SD is not called a trend at all. Zone-aware phrasing is applied to the baseline-deviation line too — a 2 SD jump inside green reads "above their usual — still in the calm range". The chart and the raw gradient stay on screen throughout; this governs the words around them.

**Each pet is its own control**: baseline = mean ± SD of prior observations (≥3), deviation flagged at ≥1.5 SD, slope = least-squares points/week (≥4). Formulas are stated verbatim in the report's methodology section.
- **Vet reports contain observations, never diagnoses**, and always carry the methodology/limitations section and disclaimer (`vet_report.py`).

### Key design decisions

**Stills are not short videos** (`enforce_image_mode` in `gemini_service.py`): a photo carries no duration and no audio, so anything defined by change over time is unobservable in it. Three layers keep that honest. Pass 1's scene-verification prompt is media-specific — asking a photograph "what sounds can you HEAR" or "what does the animal DO" doesn't just spoil a field, it mints a fabricated ground truth that Pass 2 is then *obliged* to honour, so the image variant asks only for posture, framing, and visible objects, and bans motion verbs outright. Pass 2's IMAGE MODE addendum lists what a frozen frame cannot show (movement, wag lateralisation, vocalisations, sequence, repetition) and what it shows well (FACS, posture, ear/tail position — and the Feline Grimace Scale, which was *validated* on stills, so for a cat a photo is the instrument's intended input rather than a compromise). Then the structure is clamped server-side rather than trusted: audio lists emptied, timeline and `interpret_lines` collapsed to one entry at 0:00. The frontend follows — no scrub-chart, no waveform, no subtitle track, and the single POV line becomes a fixed caption.

**The speech bubble opens when they speak** (`Dashboard.jsx`): the pet-POV caption used to appear on a four-second timer over whatever was on screen, which meant a speech bubble floating above a silent cat — the metaphor telling a small lie every few seconds in a product whose whole argument is that it doesn't. It is now driven by the MEASURED vocalization events (`_audio_metrics.vocalization_events`): *when* a sound happened is DSP, *what it meant* is Gemini, the same division of labour as the audio timeline. A POV line is matched to the nearest measured sound within 2.5 s (the model's timestamps are approximate, the DSP's are not), one line per sound; lines with no sound near them get no bubble, and a clip with no sounds says so in the controls rather than silently doing nothing. Opaque blue panel with bold white type at 16px — the old caption was 14px white italic on a zone-tinted panel, and white on amber is about 2:1, which fails hardest on a phone in daylight over moving footage. Zone is carried by a dot, never by the text's background.

**A human voice is not evidence about the animal** (`resolve_vocal_source` in `gemini_service.py`, prompt v6.5): home footage is mostly people talking to the pet, so every entry in `vocalizations_detected` carries `source: pet|human|other`, and the prompt states that a human sound is never interpreted as the animal's state, never scored on Morton's rules and never counted as one of the pet's vocalizations. That drives the colour coding in both audio views: **only the animal's own sounds are in the distress palette** (green/amber/red), a person is white, and anything unidentified — another animal, a TV, a sound nothing named — is slate. "We don't know who made this" is its own answer and it is not the same as "the pet did", so an unmatched sound is never credited to the animal. Records analysed before v6.5 are resolved by a word-list fallback in the same function (mirrored in `AudioWaveform.jsx` for records read from `full_json` in the browser — keep the two in step). The timeline tile's mini strip paints from the exported `soundColor()` used by the full audio timeline, so a tile and the screen it opens into cannot tell different stories.

**What the animal LOOKS like, not just what they're doing** (`physical_observations`, prompt v6.6): found in real testing — a dachshund with a markedly swollen face was analysed and nothing was reported. The cause was architectural. Pass 1 asked about posture, position, framing and objects but never about the animal's body; Pass 2's schema had no field for a physical finding, every slot being behaviour, emotion or a pain instrument; and the two-pass guard then made the miss certain, because **Pass 1 is a ground-truth lock Pass 2 must honour, so anything Pass 1 was never asked to look for is something Pass 2 is forbidden to raise.** The hallucination guard has a blind-spot cost: the tool can only see what Pass 1 was asked to look for.

Why it matters more than a missing feature: **behaviour and body come apart.** A dog with a swollen face can wag, eat and play, so on behaviour alone the analysis returns green and actively reassures the guardian — the false-reassurance failure, which is the one that harms. So the finding is recorded independently and **never moves the distress score**: a physical sign is a fact about the body, a distress score is an estimate of emotional state, and merging them would misrepresent both. In the reported case the score stays 14/green (the dog genuinely was relaxed) while the advisory goes to critical.

Rules: describe never diagnose ("swelling below the left eye", not "abscess"); breed-normal conformation is explicitly not a finding (a dachshund's back, a pug's face, a shar-pei's wrinkles); never inferred from behaviour; an empty list is the normal, expected answer. Pass 1 asks in both the video and image variants and is told to compare left with right, since most acute findings are unilateral. `enforce_image_mode` deliberately does NOT strip them — a photo is often the best evidence of swelling there is, and the thing an owner instinctively photographs.

**The urgency floor is enforced in code, not by the model** (`normalise_physical_observations`): any visible finding lifts the advisory to at least `elevated`; a finding in the urgent category forces `critical`. A model that correctly reports the swelling and then sets urgency to "routine" has produced a worse output than one that missed it, because the guardian reads the urgency. Swelling is matched as (swelling word + body region) rather than fixed phrases — the real finding read "Marked swelling of the left muzzle and below the left eye", which every literal phrase like "facial swelling" walks straight past.

**Two-pass hallucination prevention:** Gemini runs twice. Pass 1 (`run_scene_verification`) locks in what is literally visible as a JSON ground-truth object. Pass 2 (`analyze_video_with_context`) receives that object as a hard constraint and cannot contradict it. This was the core fix for the original problem of Gemini inventing scenarios.

**The overlay: outline, not rectangle** (`video_annotator.py`, `_contour`/`_trail`): with a `-seg` checkpoint in `YOLO_MODEL`, each animal is drawn as a rotoscoped contour taken from the segmentation mask rather than a bounding box, with a fading centroid trail showing where they have just been. This is not decoration. **Measured: 48% of a bounding box is not the animal** — a rectangle asserts "the pet is somewhere in here" and invites the whole rectangle to be read as the finding, whereas the outline asserts exactly what the detector decided was animal, which is a smaller and truer claim. The same mask tightens the ROI for the three measurements that sample inside the detection: respiration (chest motion), postural sway (normalised to body width), and the coat signature `identity_check` compares — which currently crops the central 60% of the box purely to dodge background pixels. The interior wash is kept at 0.14 alpha and blended only over the contour's own bounding rect: any stronger and a big silhouette becomes a solid colour block, and a full-frame blend per animal per frame is what turns a 30s clip into a two-minute render. The trail carries age by thickness plus a mild brightness ramp over a **dark casing** — the first version faded to 25% of the zone hue, which on green is (12,51,12) and invisible against a sofa or a night-time room. Only the largest animal in shot gets a trail and a caption: two paths cross into one scribble, and two chips stack on top of each other saying the same thing. Everything degrades to the box when no mask is present, so a detect-only model loses nothing but the look.

**YOLO as detection oracle (pose disabled):** `yolo_pose_service.py` samples video at 5 fps and runs `yolo11m.pt` (detection, classes 15=cat 16=dog; `YOLO_MODEL` env-configurable). Detection is solid and drives the framing quality check, the ROI for respiration and motion health signals, postural sway, and the annotated overlay — 98% frame coverage on a real pug clip, 51% on a hard cat clip (nano managed 3%).

**Pose estimation is OFF by default** (`ENABLE_POSE`). The only available weights are human-trained (COCO-17), and on a quadruped they don't approximate animal anatomy — they fit a *human* to the animal. Measured on a clear frontal frame of a sitting pug: 13/17 keypoints at 0.92–0.98 confidence (shoulders, elbows, wrists, hips, knees, ankles — the dog's front legs read as human legs), with **no nose and no eyes**. The spinal-angle code then substituted a hardcoded `[0,-1]` vector for the missing nose, so the angle was computed from fabricated input, yielding 75° mean / 165° peak and "extreme fear crouch" for a calm dog. Reliability gates (SD ≤ 20°, mean ≤ 45°, |tilt| ≤ 90°) still exist and still apply, but stable garbage would pass them, so the model simply isn't run. Spinal curvature, head tilt, and face visibility are therefore not reported at all. Supply an animal-trained model to re-enable: `YOLO_POSE_MODEL=/path/to/animal-pose.pt ENABLE_POSE=1`, validated first with `scripts/compare_pose_models.py`.

**Audio as measurement oracle:** `audio_service.py` is the acoustic counterpart to the YOLO oracle. It extracts the audio track via `ffmpeg` (mono, 22050 Hz, capped at 120 s) and computes *measured* acoustics with numpy/scipy: fundamental frequency (F0 via autocorrelation with octave-error mitigation + parabolic interpolation), tonality (spectral flatness), the 220–520 Hz solicitation-purr band ratio (McComb 2009), and energy-based vocalization-event segmentation with per-event pitch/contour/tonality. These are injected as a `## AUDIO ACOUSTIC MEASUREMENTS` block in the Pass 2 prompt. Division of labour: **Gemini identifies *what* a sound is** (bark/meow/growl/purr); **the DSP supplies the numbers Gemini can't hear precisely** (Hz, tonal-vs-noisy, purr-band energy), so Morton's-rule claims cite measurements instead of vague language. The per-event Morton labels the service emits are heuristic priming, not final verdicts.

**Sleeping respiratory rate (SRR) — sleeping clips ONLY:** `respiration_service.py` measures resting respiratory rate from chest-motion displacement (row-profile cross-correlation → Welch PSD, 0.10–1.67 Hz band, sub-harmonic guard). It runs **only** on uploads tagged `context=sleeping_baseline` — the measurement is physically meaningless on an awake/moving/panting pet, and the service additionally refuses (usable=false + plain-English reason) clips that are too short (<15 s) or show too much motion. Usable rates are stored as measured columns (`resp_rate_bpm`, `resp_confidence`), injected into Pass 2 as ground truth, surfaced in the timeline feed (`srr_bpm`), trends (red flag when > 30/min — the published veterinary screening threshold, *reported, never interpreted*), the vet report (its own section + methodology bullet), and capture-quality feedback. Validate against manual counts with `scripts/validate_respiration.py` (MAE ≤ 3 bpm to ship numbers) before trusting real-world readings.

**The audio timeline is the audio.** `audio_service.py` returns a downsampled RMS `envelope` (200 buckets, normalised to its own peak) alongside the metrics, and the waveform draws that. It previously drew `Math.random()` shaped by a sine envelope — on a panel that also prints measured frequencies in Hz, an invented waveform is the same failure as any other fabricated measurement, it just looks more like evidence. With no DSP available the strip goes flat and says so rather than inventing one. Event markers are positioned from the MEASURED events (`vocalization_events[].timestamp_sec/duration_sec`), with Gemini's identifications matched onto the nearest measured event within 2 s — when a sound happened is measured, what it was is identified. Each row shows the measured pitch, contour, tonality and Morton reading labelled *measured*, and **flags an identification that contradicts them**: a purr has a fundamental near 20–40 Hz (the 220–520 Hz band is the *cry* inside a solicitation purr), so a "purr" measured above 600 Hz is reported as contradicted rather than silently accepted. The Pass 2 prompt now states those physical constraints too, so the model stops calling a 1.3 kHz tonal sound a contentment purr because the animal looked relaxed.

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
| `app/services/media_store.py` | Persistent media library under `$DATA_DIR/media` — posters + annotated clips, budget-capped eviction |
| `app/services/breed_health.py` | Breed predisposition context and the capture plan it drives — population data, quarantined from the pipeline |
| `app/services/identity_check.py` | Is this the same animal? Measured species + coat-colour screen against the pet's own history — quarantined from the pipeline, never scores, never blocks |
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
| `ENABLE_POSE` | No | Set `1` ONLY with an animal-trained pose model in `YOLO_POSE_MODEL`. Off by default: human COCO-17 keypoints fit a human skeleton to pets and fabricated the spinal angle |
| `YOLO_MODEL` | No | Detector weights (default `yolo11m.pt`). Measured detection rate on a real cat clip: nano 3%, small 34%, **medium 49%**, large 45%, xlarge 48%. Set `yolo11s.pt` to trade detection rate for latency. Set a `-seg` checkpoint (`yolo11m-seg.pt`) to get **outlines instead of boxes** — one model, one pass, and the overlay adapts automatically. Measured cost: +52% inference time, same detection count on the test clip. Benchmark on your own media with `scripts/compare_detectors.py` before switching: detection rate decides it, not the overlay |
| `DATA_DIR` | Production | Directory for the SQLite longitudinal DB and the media library (mount a Railway volume here; default `./data` is ephemeral) |
| `MEDIA_MAX_MB` | No | Size cap for stored annotated clips (default 2000). Past it, the oldest clips are evicted; posters, avatars and wallpapers are never evicted |
| `IDENTITY_APPEARANCE` | No | Set `1` ONLY after `scripts/validate_identity.py` shows within-pet and between-pet coat distances separate on real data. Off by default: the species half of the identity screen always runs, the coat-colour half measures and stores but never raises |

### System dependencies

Audio analysis requires the `ffmpeg` binary on PATH, installed at build time via `nixpacks.toml`.

**The OpenCV conflict — do not undo this.** `ultralytics` hard-requires `opencv-python` (the full desktop build), so pip installs it alongside our `opencv-python-headless`, both write to the same `cv2/` directory, and the desktop build wins at import. It links against X11/OpenGL objects a slim server image doesn't ship, crashing startup with `ImportError: libxcb.so.1`. Two fixes work together:
1. `nixpacks.toml` `[phases.build]` purges every OpenCV variant after install and reinstalls **headless alone** (a partial uninstall leaves a broken `cv2`, hence purge-then-reinstall), then asserts `import cv2` during the build so a regression fails the build rather than the deploy.
2. `yolo_pose_service.py` sets `YOLO_AUTOINSTALL=false` **before importing ultralytics** — otherwise ultralytics re-installs `opencv-python` at runtime and silently reintroduces the crash.

Declaring the X11 libs in `aptPkgs` is kept only as a safety net; it is not sufficient on its own, because the Nix-based image doesn't reliably put apt libraries on the runtime library path.

### Annotated video storage — two tiers

**Working copy (`/tmp/etho_annotated/{uuid}.mp4`).** What the annotator renders and what `GET /api/video/annotated/{video_id}` serves immediately after an upload. OpenCV writes raw `mp4v`, then `_finalize_annotated()` re-encodes to **H.264 + AAC + faststart** and muxes the original audio back in (OpenCV's writer is video-only, and mp4v doesn't play on mobile Safari); it falls back to the silent mp4v file if ffmpeg is missing. Ephemeral — every upload triggers `cleanup_old_videos()`, deleting anything over 2 hours old, and Railway clears `/tmp` on restart.

**Record copy (`$DATA_DIR/media/`, `media_store.py`).** A timeline of scores with no pictures is a spreadsheet, so every analysis logged **against a pet** also keeps:

- `{analysis_id}_poster.jpg` — 480px still cut 40% into the ANNOTATED media (so the detection box is visible on the tile, proving the tool found the pet), tens of KB.
- `{pet_id}_avatar.jpg` — the guardian's chosen profile picture, centre-cropped square at 512px (squashing a portrait phone photo into a round tile distorts the face, which is the one thing the picture is for).
- `{analysis_id}.mp4|.jpg` — the annotated media itself, replayed by the detail view.

Retention is asymmetric on purpose: **clips are evicted oldest-first past `MEDIA_MAX_MB` (default 2000); posters and avatars are never evicted** — `_is_permanent()` is a single predicate precisely because three separate code paths (size accounting, eviction, status) have to agree on what survives, and an avatar sitting in the same directory as the clips would otherwise be deleted as one. A timeline that loses its pictures loses what makes it readable, whereas a clip that ages out costs nothing the record needs — the analysis JSON is the durable artefact. `GET /api/analyses/{id}/media` returning 404 is therefore a normal end state the UI handles, not an error. Unassigned one-off analyses store no media at all: with no timeline to appear in, nothing would ever read it.

Both media endpoints are owner-scoped (404, never 403). Because `<img src>` and `<video src>` can't send `X-API-Key`, the frontend fetches them as blobs and uses object URLs rather than putting the key in a URL where it would land in server logs.
