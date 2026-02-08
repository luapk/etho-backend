"""
Etho API v13 - Gemini-Powered Pet Behavior Analysis
Full video understanding with complete ethological research framework
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import tempfile
import os
import shutil

from .services.gemini_service import analyze_video

app = FastAPI(
    title="Etho API",
    description="AI-powered pet behavior analysis using ethological research frameworks",
    version="13.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Etho API",
        "version": "13.0.0",
        "engine": "gemini-2.0-flash",
        "features": [
            "Full video understanding",
            "DogFACS analysis",
            "Feline Grimace Scale",
            "Morton's motivation-structural rules",
            "Breed morphology normalization",
            "C-BARQ behavioral priors"
        ]
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    gemini_key = os.environ.get("GEMINI_API_KEY")
    return {
        "status": "healthy",
        "gemini_configured": bool(gemini_key),
        "version": "13.0.0"
    }


@app.post("/api/video/upload")
async def upload_and_analyze(
    file: UploadFile = File(...),
    mode: str = Query(default="full", description="Analysis mode: full or quick"),
    use_cache: bool = Query(default=True, description="Use cached results if available")
):
    """
    Upload a video and receive comprehensive ethological analysis.
    
    This endpoint:
    1. Accepts video upload (mp4, mov, avi, webm)
    2. Uploads to Gemini File API
    3. Runs full ethological analysis with research frameworks
    4. Returns structured JSON with distress scoring, FACS codes, timeline
    """
    
    # Validate file type
    allowed_types = ["video/mp4", "video/quicktime", "video/x-msvideo", "video/webm", "video/x-matroska"]
    content_type = file.content_type or "video/mp4"
    
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {content_type}. Allowed: mp4, mov, avi, webm"
        )
    
    # Check file size (max 100MB for Gemini)
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Seek back to start
    
    if file_size > 100 * 1024 * 1024:  # 100MB
        raise HTTPException(
            status_code=400,
            detail="Video too large. Maximum size is 100MB."
        )
    
    print(f"\n{'='*60}")
    print(f"NEW ANALYSIS REQUEST")
    print(f"{'='*60}")
    print(f"  File: {file.filename}")
    print(f"  Size: {file_size / (1024*1024):.2f} MB")
    print(f"  Type: {content_type}")
    print(f"  Mode: {mode}")
    
    # Save to temp file
    temp_path = None
    try:
        # Create temp file with proper extension
        ext = os.path.splitext(file.filename or "video.mp4")[1] or ".mp4"
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
            temp_path = temp_file.name
            shutil.copyfileobj(file.file, temp_file)
        
        print(f"  Temp: {temp_path}")
        
        # Run analysis
        result = analyze_video(temp_path, use_cache=use_cache)
        
        # Check for errors
        if result.get("error"):
            error_type = result.get("error_type", "unknown")
            message = result.get("message", "Analysis failed")
            
            if error_type == "no_pet_detected":
                return JSONResponse(
                    status_code=200,  # Not an error, just no pet found
                    content={"success": True, "data": result}
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=message
                )
        
        # Wrap successful result in expected format
        return {"success": True, "data": result}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"  ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )
    finally:
        # Clean up temp file
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
                print(f"  → Cleaned up temp file")
            except:
                pass


@app.get("/api/models")
async def list_models():
    """List available analysis models"""
    return {
        "models": [
            {
                "id": "gemini-2.0-flash",
                "name": "Gemini 2.0 Flash",
                "description": "Full video understanding with native multimodal processing",
                "capabilities": [
                    "video_analysis",
                    "audio_analysis", 
                    "temporal_understanding",
                    "structured_output"
                ],
                "max_video_size_mb": 100,
                "max_video_duration_minutes": 60
            }
        ],
        "default": "gemini-2.0-flash"
    }


# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    print(f"Unhandled exception: {exc}")
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "error_type": "internal_error",
            "message": str(exc)
        }
    )
