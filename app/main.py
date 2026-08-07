"""
Etho API v16 - YOLO11-Pose + Gemini Pet Behaviour Analysis
Full video understanding with pose estimation, annotated video output,
and complete ethological research framework.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse, PlainTextResponse
from pydantic import BaseModel
from typing import Optional
import tempfile
import os
import shutil
import zipfile
import io

from .services.gemini_service import analyze_video, GEMINI_MODEL
from .services.yolo_pose_service import YoloPoseService
from .services.audio_service import AudioService
from .services import (
    pet_store, vet_report, capture_quality, breed_reference, model_selector,
)
from .services.video_annotator import (
    annotate_video,
    annotate_image,
    get_annotated_video_path,
    cleanup_old_videos,
    probe_video_meta,
    probe_image_meta,
)

_API_KEY = os.environ.get("API_KEY", "")


async def get_auth(x_api_key: str = Header(default="", alias="X-API-Key")) -> dict:
    """Resolve the X-API-Key header to an auth context.

    Three roles:
      admin — the master API_KEY env var (or local dev with API_KEY unset):
              sees all pets, can create owners
      owner — a per-guardian key minted via POST /api/owners: sees only
              their own pets and records
    Anything else with API_KEY set → 401.

    Cross-owner lookups return 404 (not 403) at the endpoint level so the
    existence of other guardians' pets is never confirmed.
    """
    if _API_KEY and x_api_key == _API_KEY:
        return {"role": "admin", "owner_id": None}
    if x_api_key:
        owner = pet_store.get_owner_by_key(x_api_key)
        if owner:
            return {"role": "owner", "owner_id": owner["id"], "owner": owner}
    if not _API_KEY:
        # Local dev convenience: no master key configured → open, admin-like
        return {"role": "admin", "owner_id": None}
    raise HTTPException(status_code=401, detail="Invalid or missing API key")


def _authorized_pet(pet_id: str, auth: dict) -> dict:
    """Fetch a pet the caller is allowed to see, else 404. Owners only see
    their own; admin sees all."""
    pet = pet_store.get_pet(pet_id)
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")
    if auth["role"] == "owner" and pet.get("owner_id") != auth["owner_id"]:
        raise HTTPException(status_code=404, detail="Pet not found")
    return pet


app = FastAPI(
    title="Etho API",
    description="AI-powered pet behaviour analysis — YOLO11-Pose + Gemini",
    version="17.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialise YOLO once at startup (downloads weights on first run)
_yolo = YoloPoseService()
# Initialise audio acoustic service once at startup (checks ffmpeg + scipy)
_audio = AudioService()
# Initialise the longitudinal pet/analysis store (SQLite at $DATA_DIR/etho.db)
pet_store.init_db()


class PetCreate(BaseModel):
    name: str
    species: Optional[str] = None       # dog | cat
    breed: Optional[str] = None
    sex: Optional[str] = None
    birthdate: Optional[str] = None     # ISO date
    weight_kg: Optional[float] = None
    notes: Optional[str] = None


class PetUpdate(BaseModel):
    name: Optional[str] = None
    species: Optional[str] = None
    breed: Optional[str] = None
    sex: Optional[str] = None
    birthdate: Optional[str] = None
    weight_kg: Optional[float] = None
    notes: Optional[str] = None


def _log_to_history(pet_id, result: dict, media_type: str,
                    filename: str, size_bytes: int,
                    owner_id: str = None, context: str = None):
    """Persist a successful analysis to the pet's longitudinal record.
    pet_id may be None — the record is stored unassigned (but still
    owner-scoped). Pet ownership is validated by the endpoint BEFORE the
    pipeline runs. Never lets a logging failure break the response."""
    try:
        analysis_id = pet_store.log_analysis(
            pet_id, result, media_type=media_type,
            source_filename=filename, file_size_bytes=size_bytes,
            owner_id=owner_id, context=context,
        )
        result["analysis_id"] = analysis_id
        result["pet_id"] = pet_id
        print(f"  → Logged analysis {analysis_id} (pet: {pet_id or 'unassigned'})")
    except Exception as e:
        print(f"  ⚠ Failed to log analysis: {e}")


@app.get("/")
async def root():
    return {
        "status": "healthy",
        "service": "Etho API",
        "version": "17.1.0",
        "engine": f"{GEMINI_MODEL} + yolo11-pose",
        "pose_tracking": _yolo.available,
        "audio_analysis": _audio.available,
        "features": [
            "YOLO11-Pose keypoint detection",
            "Spinal curvature measurement",
            "Acoustic measurement (pitch, tonality, purr-band)",
            "Annotated video + image output",
            "DogFACS / Feline Grimace Scale analysis",
            "Instrument scoring (FGS / observable stress subset)",
            "Morton's motivation-structural rules",
            "Breed morphology normalisation",
            "Two-pass hallucination prevention",
            "Longitudinal pet records + trend baselines",
            "Pre-consultation vet reports",
        ],
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "gemini_configured": bool(os.environ.get("GEMINI_API_KEY")),
        "yolo_available": _yolo.available,
        "audio_available": _audio.available,
        "data_dir": pet_store.DATA_DIR,
        "version": "17.1.0",
    }


@app.post("/api/video/upload")
async def upload_and_analyze(
    file: UploadFile = File(...),
    mode: str = Query(default="full", description="Analysis mode: full or quick"),
    use_cache: bool = Query(default=True, description="Use cached results if available"),
    annotate: bool = Query(default=True, description="Generate annotated video overlay"),
    pet_id: Optional[str] = Query(default=None, description="Pet profile to log this analysis to"),
    context: Optional[str] = Query(default=None, description="Capture context tag: weekly_baseline | incident | post_vet | other"),
    auth: dict = Depends(get_auth),
):
    """
    Upload a video and receive comprehensive ethological analysis plus an
    annotated video with pose overlays and behavioural insight markers.

    Steps:
    1. YOLO11-Pose: bounding boxes, skeleton, spinal angle, head tilt
    2. Gemini Pass 1: scene verification (ground truth lock)
    3. Gemini Pass 2: ethological analysis with YOLO metrics as context
    4. Video annotator: renders bounding boxes, skeleton, breed tags,
       timeline events, pet-POV text, and distress meter onto every frame
    5. Returns JSON analysis + annotated_video_id for download
    """
    # Validate pet ownership BEFORE the expensive pipeline runs — an invalid
    # pet_id should fail in milliseconds, not after a full Gemini analysis.
    if pet_id:
        _authorized_pet(pet_id, auth)

    # Lazy cleanup of old annotated videos
    cleanup_old_videos(max_age_secs=7200)

    allowed_types = {
        "video/mp4", "video/quicktime", "video/x-msvideo",
        "video/webm", "video/x-matroska",
    }
    content_type = file.content_type or "video/mp4"
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {content_type}. Allowed: mp4, mov, avi, webm",
        )

    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > 100 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Video too large. Maximum size is 100MB.")

    print(f"\n{'='*60}")
    print(f"NEW ANALYSIS REQUEST")
    print(f"{'='*60}")
    print(f"  File: {file.filename}")
    print(f"  Size: {file_size / (1024*1024):.2f} MB")
    print(f"  Type: {content_type}")
    print(f"  Mode: {mode}  |  Annotate: {annotate}  |  YOLO: {_yolo.available}")

    temp_path = None
    try:
        ext = os.path.splitext(file.filename or "video.mp4")[1] or ".mp4"
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            temp_path = tmp.name
            shutil.copyfileobj(file.file, tmp)
        print(f"  Temp: {temp_path}")

        # ── Step 1: YOLO pose detection ───────────────────────────────────
        pose_frames: list = []
        pose_metrics: dict = {}
        if annotate and _yolo.available:
            print("\nStep 1/4: YOLO11-Pose detection...")
            pose_frames = _yolo.process_video(temp_path)
            pose_metrics = _yolo.summarize_metrics(pose_frames)
            print(f"  → Coverage: {pose_metrics.get('detection_coverage', 0):.0%}, "
                  f"spinal: {pose_metrics.get('spinal_curvature', {}).get('mean_deg', 'n/a')}°")
        else:
            print("\nStep 1/4: YOLO skipped (unavailable or annotate=false)")

        # ── Step 1b: Audio acoustic measurement ───────────────────────────
        audio_metrics: dict = {}
        if _audio.available:
            print("\nStep 1b: Audio acoustic analysis...")
            audio_metrics = _audio.analyze(temp_path)
            if audio_metrics.get("audio_present"):
                pitch = audio_metrics.get("pitch", {}).get("mean_hz", "n/a")
                print(f"  → Events: {audio_metrics.get('vocalization_event_count', 0)}, "
                      f"mean pitch: {pitch} Hz, "
                      f"coverage: {audio_metrics.get('vocal_activity_coverage', 0):.0%}")
            else:
                print("  → No usable audio track")
        else:
            print("\nStep 1b: Audio skipped (ffmpeg/scipy unavailable)")

        # ── Step 2+3: Gemini two-pass analysis ────────────────────────────
        print("\nStep 2-3/4: Gemini ethological analysis...")
        result = analyze_video(temp_path, use_cache=use_cache, pose_metrics=pose_metrics,
                               audio_metrics=audio_metrics)

        if result.get("error"):
            error_type = result.get("error_type", "unknown")
            if error_type == "no_pet_detected":
                return JSONResponse(status_code=200, content={"success": True, "data": result})
            raise HTTPException(status_code=500, detail=result.get("message", "Analysis failed"))

        # ── Step 4: Generate annotated video ─────────────────────────────
        if annotate:
            print("\nStep 4/4: Rendering annotated video...")
            video_id = annotate_video(temp_path, pose_frames, result)
            if video_id:
                result["annotated_video_id"] = video_id
                print(f"  → Video ID: {video_id}")
            else:
                print("  ⚠ Annotation failed (video still returned)")

        # ── Step 5: Capture-quality feedback + longitudinal log ──────────
        result["capture_quality"] = capture_quality.assess(
            "video", pose_metrics, audio_metrics,
            probe_video_meta(temp_path), yolo_available=_yolo.available,
        )
        _log_to_history(pet_id, result, "video", file.filename, file_size,
                        owner_id=auth["owner_id"], context=context)

        return {"success": True, "data": result}

    except HTTPException:
        raise
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
                print("  → Cleaned up temp file")
            except OSError:
                pass


@app.post("/api/image/upload")
async def upload_and_analyze_image(
    file: UploadFile = File(...),
    annotate: bool = Query(default=True, description="Generate annotated image overlay"),
    pet_id: Optional[str] = Query(default=None, description="Pet profile to log this analysis to"),
    context: Optional[str] = Query(default=None, description="Capture context tag: weekly_baseline | incident | post_vet | other"),
    auth: dict = Depends(get_auth),
):
    """
    Upload a still image for single-moment ethological analysis.
    Runs YOLO pose on the frame and Gemini two-pass in image mode (no audio,
    single-entry timeline, FGS scored from the still). Logged to the pet's
    longitudinal record like video analyses.
    """
    if pet_id:
        _authorized_pet(pet_id, auth)

    cleanup_old_videos(max_age_secs=7200)

    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    content_type = file.content_type or "image/jpeg"
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {content_type}. Allowed: jpeg, png, webp",
        )

    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large. Maximum size is 20MB.")

    print(f"\nNEW IMAGE ANALYSIS: {file.filename} ({file_size / 1024:.0f} KB)")

    temp_path = None
    try:
        ext = os.path.splitext(file.filename or "photo.jpg")[1] or ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            temp_path = tmp.name
            shutil.copyfileobj(file.file, tmp)

        pose_frames: list = []
        pose_metrics: dict = {}
        if _yolo.available:
            pose_frames = _yolo.process_image(temp_path)
            pose_metrics = _yolo.summarize_metrics(pose_frames)

        result = analyze_video(temp_path, pose_metrics=pose_metrics, media_kind="image")

        if result.get("error"):
            if result.get("error_type") == "no_pet_detected":
                return JSONResponse(status_code=200, content={"success": True, "data": result})
            raise HTTPException(status_code=500, detail=result.get("message", "Analysis failed"))

        if annotate:
            media_id = annotate_image(temp_path, pose_frames, result)
            if media_id:
                result["annotated_video_id"] = media_id

        result["capture_quality"] = capture_quality.assess(
            "image", pose_metrics, None,
            probe_image_meta(temp_path), yolo_available=_yolo.available,
        )
        _log_to_history(pet_id, result, "image", file.filename, file_size,
                        owner_id=auth["owner_id"], context=context)

        return {"success": True, "data": result}

    except HTTPException:
        raise
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


# ── Owners (per-guardian API keys) ───────────────────────────────────────────

class OwnerCreate(BaseModel):
    name: str
    email: Optional[str] = None


@app.post("/api/owners")
async def create_owner(owner: OwnerCreate, auth: dict = Depends(get_auth)):
    """Create a guardian account and mint their personal API key (admin only).
    The raw key is returned ONCE and never stored — only its SHA-256 hash."""
    if auth["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin key required")
    created, raw_key = pet_store.create_owner(owner.name, owner.email)
    return {"success": True, "owner": created, "api_key": raw_key,
            "note": "Store this key now — it cannot be retrieved again."}


@app.get("/api/owners")
async def get_owners(auth: dict = Depends(get_auth)):
    """Owner roster with pet counts (admin only). Keys are never exposed."""
    if auth["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin key required")
    return {"success": True, "owners": pet_store.list_owners()}


# ── Capture protocol ─────────────────────────────────────────────────────────

@app.get("/api/capture-protocol")
async def get_capture_protocol():
    """Versioned capture guidance for the frontend: weekly-baseline rules,
    incident-capture rules, photo framing, and the available context tags.
    Public — contains no user data."""
    return {"success": True, "protocol": capture_quality.CAPTURE_PROTOCOL}


# ── Pet profiles & longitudinal record ───────────────────────────────────────

@app.post("/api/pets")
async def create_pet(pet: PetCreate, auth: dict = Depends(get_auth)):
    """Create a pet profile, owned by the calling guardian. Analyses uploaded
    with ?pet_id=<id> accumulate into this pet's longitudinal record."""
    created = pet_store.create_pet(pet.model_dump(), owner_id=auth["owner_id"])
    return {"success": True, "pet": created}


@app.get("/api/pets")
async def get_pets(auth: dict = Depends(get_auth)):
    """Owner keys see only their own pets; the admin key sees all."""
    return {"success": True, "pets": pet_store.list_pets(owner_id=auth["owner_id"])}


@app.get("/api/pets/{pet_id}")
async def get_pet(pet_id: str, auth: dict = Depends(get_auth)):
    pet = _authorized_pet(pet_id, auth)
    return {
        "success": True,
        "pet": pet,
        "weight_assessment": breed_reference.assess_weight(
            pet.get("species"), pet.get("breed"), pet.get("weight_kg")),
    }


@app.patch("/api/pets/{pet_id}")
async def update_pet(pet_id: str, patch: PetUpdate, auth: dict = Depends(get_auth)):
    _authorized_pet(pet_id, auth)
    data = {k: v for k, v in patch.model_dump().items() if v is not None}
    return {"success": True, "pet": pet_store.update_pet(pet_id, data)}


@app.get("/api/pets/{pet_id}/history")
async def get_pet_history(pet_id: str, limit: int = Query(default=200, le=500),
                          auth: dict = Depends(get_auth)):
    """Chronological indexed metrics for timeline/chart rendering."""
    _authorized_pet(pet_id, auth)
    return {"success": True, "history": pet_store.get_history(pet_id, limit=limit)}


@app.get("/api/pets/{pet_id}/timeline")
async def get_pet_timeline(pet_id: str, limit: int = Query(default=200, le=500),
                           auth: dict = Depends(get_auth)):
    """Unified chronological feed for a scrubbable timeline UI: analyses and
    weight entries merged, each analysis carrying its own per-asset distress
    curve (sparkline-ready), zone, instrument total, capture-quality grade,
    and context tag — no per-item follow-up fetches needed."""
    _authorized_pet(pet_id, auth)
    return {"success": True, "timeline": pet_store.get_timeline_feed(pet_id, limit=limit)}


class WeightCreate(BaseModel):
    weight_kg: float
    note: Optional[str] = None
    recorded_at: Optional[str] = None   # ISO timestamp; defaults to now


@app.post("/api/pets/{pet_id}/weights")
async def add_pet_weight(pet_id: str, entry: WeightCreate,
                         auth: dict = Depends(get_auth)):
    """Log a weight measurement. Also updates the profile's current weight
    and returns the fresh breed-range screening assessment."""
    pet = _authorized_pet(pet_id, auth)
    if not (0.05 <= entry.weight_kg <= 150):
        raise HTTPException(status_code=400, detail="Implausible weight_kg")
    saved = pet_store.add_weight(pet_id, entry.weight_kg, entry.note, entry.recorded_at)
    return {
        "success": True,
        "weight": saved,
        "weight_assessment": breed_reference.assess_weight(
            pet.get("species"), pet.get("breed"), entry.weight_kg),
    }


@app.get("/api/pets/{pet_id}/weights")
async def get_pet_weights(pet_id: str, auth: dict = Depends(get_auth)):
    pet = _authorized_pet(pet_id, auth)
    return {
        "success": True,
        "weights": pet_store.get_weights(pet_id),
        "weight_assessment": breed_reference.assess_weight(
            pet.get("species"), pet.get("breed"), pet.get("weight_kg")),
    }


@app.get("/api/pets/{pet_id}/trends")
async def get_pet_trends(pet_id: str, auth: dict = Depends(get_auth)):
    """Baseline, deviation, slope, and red flags — transparent math, each pet
    compared only against its own history."""
    _authorized_pet(pet_id, auth)
    return {"success": True, "trends": pet_store.compute_trends(pet_id)}


@app.get("/api/analyses/{analysis_id}")
async def get_analysis(analysis_id: str, auth: dict = Depends(get_auth)):
    """Full stored record (complete raw result JSON) for one analysis."""
    rec = pet_store.get_analysis(analysis_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if auth["role"] == "owner" and rec.get("owner_id") != auth["owner_id"]:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"success": True, "analysis": rec}


@app.get("/api/pets/{pet_id}/vet-report")
async def get_vet_report(
    pet_id: str,
    reason: Optional[str] = Query(default=None, description="Guardian-stated reason for visit"),
    format: str = Query(default="json", description="json or markdown"),
    auth: dict = Depends(get_auth),
):
    """
    Pre-consultation report: signalment, observation log (measured vs
    AI-estimated columns separated), instrument scores, transparent trend
    math, recurring markers, methodology & limitations, disclaimer.
    Observations only — never diagnoses.
    """
    _authorized_pet(pet_id, auth)
    report = vet_report.build_report(pet_id, reason_for_visit=reason)
    if not report:
        raise HTTPException(status_code=404, detail="Pet not found")
    if format == "markdown":
        return PlainTextResponse(
            vet_report.render_markdown(report),
            media_type="text/markdown",
        )
    return {"success": True, "report": report}


@app.get("/api/video/annotated/{video_id}")
async def download_annotated_video(video_id: str):
    """
    Download the annotated media (video or image) produced during analysis.
    The ID is returned in the analysis response as annotated_video_id.
    Files are ephemeral and cleaned up after 2 hours.
    """
    # Basic validation to prevent path traversal
    if not video_id.replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid video ID")

    path = get_annotated_video_path(video_id)
    if not path:
        raise HTTPException(status_code=404, detail="Annotated media not found or expired")

    is_image = path.endswith(".jpg")
    return FileResponse(
        path,
        media_type="image/jpeg" if is_image else "video/mp4",
        filename=f"etho-analysis-{video_id}{'.jpg' if is_image else '.mp4'}",
    )


@app.get("/api/models")
async def list_models():
    return {
        "models": [
            {
                "id": GEMINI_MODEL,
                "name": "Gemini 2.0 Flash",
                "description": "Full video understanding with native multimodal processing",
                "capabilities": [
                    "video_analysis", "audio_analysis",
                    "temporal_understanding", "structured_output",
                ],
                "max_video_size_mb": 100,
                "max_video_duration_minutes": 60,
            }
        ],
        "pose_model": {
            "id": "yolo11n-pose",
            "available": _yolo.available,
            "description": "Real-time keypoint detection for bounding boxes, skeleton overlay, and spinal angle measurement",
        },
        "default": GEMINI_MODEL,
    }


@app.get("/api/models/available")
async def get_available_models(
    prefer: str = Query(default="flash", description="Tier preference: flash | pro | flash-lite"),
    include_preview: bool = Query(default=False),
    auth: dict = Depends(get_auth),
):
    """Query the Gemini API for reachable models and rank them for this
    pipeline (admin only — it consumes the configured API key).

    Reports the active model alongside the recommendation so an upgrade is a
    deliberate decision. Changing models still means setting GEMINI_MODEL;
    this endpoint never switches anything by itself.
    """
    if auth["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin key required")
    try:
        available = model_selector.list_available_models()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Model discovery failed: {e}")

    ranked = model_selector.rank_models(available, prefer_tier=prefer,
                                        include_preview=include_preview)
    recommended = ranked[0]["id"] if ranked else None
    return {
        "success": True,
        "active_model": GEMINI_MODEL,
        "recommended": recommended,
        "upgrade_available": bool(recommended and recommended != GEMINI_MODEL),
        "candidates": ranked[:12],
        "total_reachable": len(available),
        "note": ("Set GEMINI_MODEL to change the analysis model, then run "
                 "scripts/repeatability_study.py before trusting new trend "
                 "data. Stored analyses record the model that produced them."),
    }


@app.get("/api/research/bundle", dependencies=[Depends(get_auth)])
async def download_research_bundle():
    """
    Download a ZIP archive of the complete Etho research pack:
    MODEL_GUIDE.md, all framework reference cards, and references.bib.
    Useful for priming a new AI model with the full ethological framework.
    """
    research_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "research")
    if not os.path.isdir(research_dir):
        raise HTTPException(status_code=404, detail="Research directory not found")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fname in sorted(os.listdir(research_dir)):
            if fname.endswith((".md", ".bib")):
                fpath = os.path.join(research_dir, fname)
                zf.write(fpath, arcname=f"etho-research/{fname}")

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=etho-research-pack.zip"},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    print(f"Unhandled exception: {exc}")
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"error": True, "error_type": "internal_error", "message": str(exc)},
    )
