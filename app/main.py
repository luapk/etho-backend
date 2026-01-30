"""
Etho Backend API v2.0
FastAPI server for pet behavior analysis using Gemini AI
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import time

from app.services.gemini_service import (
    analyze_video,
    analyze_audio_only,
    get_cache_stats,
    clear_cache,
    VOCALIZATION_COLORS,
    FGS_THRESHOLDS
)

app = FastAPI(
    title="Etho API",
    description="AI-powered pet behavior analysis using ethological frameworks",
    version="2.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://localhost:3000",
        "https://ethovitals.com",
        "https://www.ethovitals.com",
        "https://*.vercel.app",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class AnalysisResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    processing_time: float
    model_used: Optional[str] = None
    from_cache: bool = False


class CacheStatsResponse(BaseModel):
    entries: int
    oldest_entry: Optional[float]
    newest_entry: Optional[float]


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: float


# Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version="2.0.0",
        timestamp=time.time()
    )


@app.post("/api/video/upload", response_model=AnalysisResponse)
async def upload_and_analyze_video(
    file: UploadFile = File(...),
    mode: str = Query(default="full", description="Analysis mode: 'full' or 'quick'"),
    use_cache: bool = Query(default=True, description="Use cached results if available")
):
    """
    Upload a video for comprehensive ethological analysis.
    
    - **file**: Video file (mp4, mov, avi, webm supported)
    - **mode**: 'full' for complete analysis, 'quick' for brief assessment
    - **use_cache**: Whether to return cached results for identical videos
    
    Returns structured analysis including:
    - Overall distress assessment (0-100 scale with traffic light zones)
    - Visual analysis (DogFACS/FGS action units)
    - Audio analysis (vocalization classification)
    - Timeline of behavioral events
    - First-person interpretations
    - Actionable recommendations
    """
    start_time = time.time()
    
    # Validate file type
    allowed_extensions = [".mp4", ".mov", ".avi", ".webm", ".mkv"]
    filename = file.filename or "video.mp4"
    
    if not any(filename.lower().endswith(ext) for ext in allowed_extensions):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Read video data
    try:
        video_data = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to read video file: {str(e)}"
        )
    
    # Validate file size (max 100MB)
    max_size = 100 * 1024 * 1024
    if len(video_data) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: 100MB"
        )
    
    # Analyze video
    try:
        result = analyze_video(
            video_data=video_data,
            filename=filename,
            use_cache=use_cache,
            analysis_mode=mode
        )
        
        # Check if result contains an error from the service
        if result.get("error"):
            print(f"Analysis returned error: {result.get('error_message', 'Unknown error')}")
            # Still return the result - it has fallback data
            
    except Exception as e:
        import traceback
        print(f"Analysis exception: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )
    
    processing_time = time.time() - start_time
    
    return AnalysisResponse(
        success=not result.get("error", False),
        data=result,
        processing_time=processing_time,
        model_used=result.get("_model_used"),
        from_cache=result.get("_from_cache", False)
    )


@app.post("/api/video/audio-analysis")
async def analyze_video_audio(
    file: UploadFile = File(...)
):
    """
    Analyze only the audio track from a video for detailed vocalization analysis.
    
    Returns:
    - Timestamped vocalization events
    - Acoustic parameters (pitch, tonality, duration)
    - Classification and meaning
    - Color codes for visualization
    """
    start_time = time.time()
    
    video_data = await file.read()
    filename = file.filename or "video.mp4"
    
    result = analyze_audio_only(video_data, filename)
    
    return {
        "success": not result.get("error", False),
        "data": result,
        "processing_time": time.time() - start_time
    }


@app.get("/api/video/cache/stats", response_model=CacheStatsResponse)
async def get_analysis_cache_stats():
    """Get cache statistics"""
    stats = get_cache_stats()
    return CacheStatsResponse(**stats)


@app.delete("/api/video/cache")
async def clear_analysis_cache():
    """Clear the analysis cache"""
    clear_cache()
    return {"success": True, "message": "Cache cleared"}


@app.get("/api/reference/colors")
async def get_vocalization_colors():
    """Get color codes for vocalization visualization"""
    return VOCALIZATION_COLORS


@app.get("/api/reference/fgs-thresholds")
async def get_fgs_thresholds():
    """Get Feline Grimace Scale threshold values"""
    return FGS_THRESHOLDS


@app.get("/api/reference/frameworks")
async def get_analysis_frameworks():
    """Get information about the ethological frameworks used"""
    return {
        "visual_analysis": {
            "dogs": {
                "name": "DogFACS",
                "full_name": "Dog Facial Action Coding System",
                "citation": "Waller et al. (2013)",
                "description": "Objective coding of facial muscle movements in dogs",
                "key_action_units": {
                    "EAD102": "Ears Adductor - ears together, positive anticipation",
                    "EAD103": "Ears Flattener - ears back, negative valence",
                    "AU145": "Blink - rapid blinking indicates stress",
                    "AU25": "Lips Part - oral tension",
                    "AU26": "Jaw Drop - stress indicator",
                    "AD137": "Nose Lick - displacement behavior, key stress signal"
                }
            },
            "cats": {
                "name": "Feline Grimace Scale",
                "citation": "Evangelista et al. (2019)",
                "description": "Validated tool for acute pain assessment in cats",
                "action_units": ["Ear Position", "Orbital Tightening", "Muzzle Tension", "Whiskers Position", "Head Position"],
                "scoring": "Each AU scored 0-2, ratio score ≥0.39 indicates likely pain",
                "validation": "ICC = 0.89, Cronbach's alpha = 0.89"
            }
        },
        "audio_analysis": {
            "foundation": {
                "name": "Morton's Motivation-Structural Rules",
                "citation": "Morton (1977)",
                "principle": "Low pitch + noisy = aggression; High pitch + tonal = fear/appeasement"
            },
            "dogs": {
                "barks": {
                    "citation": "Pongrácz et al. (2005, 2006)",
                    "parameters": ["Fundamental frequency", "Harmonic-to-noise ratio", "Inter-bark interval", "Duration"]
                },
                "growls": {
                    "citation": "Faragó et al. (2017)",
                    "contexts": ["Food guarding", "Threatening stranger", "Play"],
                    "note": "Humans and dogs can distinguish contexts despite subtle acoustic differences"
                }
            },
            "cats": {
                "meows": {
                    "citation": "Schötz et al. (Meowsic Project, 2016-2022)",
                    "key_finding": "f0 contour (rising/falling/flat) primary meaning carrier"
                },
                "purrs": {
                    "citation": "McComb et al. (2009)",
                    "key_finding": "Solicitation purrs contain embedded 220-520 Hz 'cry' component"
                }
            }
        },
        "distress_scoring": {
            "scale": "0-100",
            "zones": {
                "green": {"range": "0-33", "meaning": "Positive valence / relaxed"},
                "yellow": {"range": "34-66", "meaning": "Caution / frustration / mild stress"},
                "red": {"range": "67-100", "meaning": "Negative valence / distress / pain / fear"}
            }
        }
    }


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
