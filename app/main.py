"""
Etho API v16 - YOLO11-Pose + Gemini Pet Behaviour Analysis
Full video understanding with pose estimation, annotated video output,
and complete ethological research framework.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
import tempfile
import os
import shutil
import zipfile
import io

from .services.gemini_service import analyze_video
from .services.yolo_pose_service import YoloPoseService
from .services.audio_service import AudioService
from .services.video_annotator import (
    annotate_video,
    get_annotated_video_path,
    cleanup_old_videos,
)

_API_KEY = os.environ.get("API_KEY", "")


async def require_api_key(x_api_key: str = Header(default="", alias="X-API-Key")):
    """Reject requests that don't carry the correct API key.
    If API_KEY env var is not set the check is skipped (local dev convenience)."""
    if _API_KEY and x_api_key != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


app = FastAPI(
    title="Etho API",
    description="AI-powered pet behaviour analysis — YOLO11-Pose + Gemini",
    version="16.0.0",
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


@app.get("/")
async def root():
    return {
        "status": "healthy",
        "service": "Etho API",
        "version": "16.0.0",
        "engine": "gemini-2.0-flash + yolo11-pose",
        "pose_tracking": _yolo.available,
        "audio_analysis": _audio.available,
        "features": [
            "YOLO11-Pose keypoint detection",
            "Spinal curvature measurement",
            "Acoustic measurement (pitch, tonality, purr-band)",
            "Annotated video output",
            "DogFACS / Feline Grimace Scale analysis",
            "Morton's motivation-structural rules",
            "Breed morphology normalisation",
            "Two-pass hallucination prevention",
        ],
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "gemini_configured": bool(os.environ.get("GEMINI_API_KEY")),
        "yolo_available": _yolo.available,
        "audio_available": _audio.available,
        "version": "16.0.0",
    }


@app.post("/api/video/upload", dependencies=[Depends(require_api_key)])
async def upload_and_analyze(
    file: UploadFile = File(...),
    mode: str = Query(default="full", description="Analysis mode: full or quick"),
    use_cache: bool = Query(default=True, description="Use cached results if available"),
    annotate: bool = Query(default=True, description="Generate annotated video overlay"),
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


@app.get("/api/video/annotated/{video_id}")
async def download_annotated_video(video_id: str):
    """
    Download the annotated video produced during analysis.
    The video_id is returned in the analysis response as annotated_video_id.
    Videos are ephemeral and cleaned up after 2 hours.
    """
    # Basic validation to prevent path traversal
    if not video_id.replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid video ID")

    path = get_annotated_video_path(video_id)
    if not path:
        raise HTTPException(status_code=404, detail="Annotated video not found or expired")

    return FileResponse(
        path,
        media_type="video/mp4",
        filename=f"etho-analysis-{video_id}.mp4",
    )


@app.get("/api/models")
async def list_models():
    return {
        "models": [
            {
                "id": "gemini-2.0-flash",
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
        "default": "gemini-2.0-flash",
    }


@app.get("/api/research/bundle", dependencies=[Depends(require_api_key)])
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
