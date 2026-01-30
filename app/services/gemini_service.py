"""
Gemini Service v3.0
Uses google-generativeai SDK (deprecated but still working)
"""

from dotenv import load_dotenv
load_dotenv()

import os
import json
import hashlib
import time
import re
import base64
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

import google.generativeai as genai

# Import the research-backed prompt
from app.prompts.ethological_prompt import ETHOLOGICAL_SYSTEM_PROMPT, QUICK_ANALYSIS_PROMPT

# Cache for storing analysis results
_analysis_cache: Dict[str, Dict[str, Any]] = {}

# Configure on module load
_configured = False


def configure_genai():
    """Configure the Gemini API"""
    global _configured
    if _configured:
        return
    
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    
    genai.configure(api_key=api_key)
    _configured = True
    print("Gemini API configured")


def get_video_hash(video_data: bytes) -> str:
    """Generate MD5 hash of video for caching"""
    return hashlib.md5(video_data).hexdigest()


def check_cache(video_hash: str) -> Optional[Dict[str, Any]]:
    """Check if analysis exists in cache"""
    if video_hash in _analysis_cache:
        cached = _analysis_cache[video_hash]
        if time.time() - cached.get("timestamp", 0) < 86400:
            return cached.get("result")
    return None


def store_cache(video_hash: str, result: Dict[str, Any]) -> None:
    """Store analysis result in cache"""
    _analysis_cache[video_hash] = {
        "result": result,
        "timestamp": time.time()
    }


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics"""
    return {
        "entries": len(_analysis_cache),
        "oldest_entry": min(
            (v.get("timestamp", 0) for v in _analysis_cache.values()),
            default=None
        ),
        "newest_entry": max(
            (v.get("timestamp", 0) for v in _analysis_cache.values()),
            default=None
        )
    }


def clear_cache() -> None:
    """Clear the analysis cache"""
    _analysis_cache.clear()


def get_available_model() -> Tuple[str, Any]:
    """Find an available Gemini model."""
    configure_genai()
    
    # Models to try - stable ones first
    models_to_try = [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash-latest",
        "gemini-1.5-pro-latest",
        "gemini-pro-vision",
    ]
    
    for model_name in models_to_try:
        try:
            print(f"Trying model: {model_name}")
            model = genai.GenerativeModel(model_name)
            # Quick test
            response = model.generate_content("Say OK")
            if response and response.text:
                print(f"Successfully connected to model: {model_name}")
                return model_name, model
        except Exception as e:
            print(f"Model {model_name} failed: {e}")
            continue
    
    raise RuntimeError("No suitable Gemini model available")


def parse_gemini_response(response_text: str) -> Dict[str, Any]:
    """Parse Gemini response, handling both JSON and markdown-wrapped JSON"""
    if not response_text:
        return {"parse_error": True, "raw_response": "Empty response"}
    
    # Try to extract JSON from markdown code blocks
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to find raw JSON
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            json_str = json_match.group(0)
        else:
            return {
                "parse_error": True,
                "raw_response": response_text[:500],
                "overall_assessment": {
                    "distress_score": 50,
                    "zone": "yellow",
                    "confidence": "low",
                    "primary_state": "unknown"
                }
            }
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        return {
            "parse_error": True,
            "error_detail": str(e),
            "raw_response": response_text[:500],
            "overall_assessment": {
                "distress_score": 50,
                "zone": "yellow",
                "confidence": "low",
                "primary_state": "unknown"
            }
        }


def simplify_marker(marker: str) -> str:
    """Convert technical markers to 2-word human-readable labels"""
    simplifications = {
        "EAD101": "Ears Forward",
        "EAD102": "Ears Alert", 
        "EAD103": "Ears Back",
        "AD137": "Lip Licking",
        "AD19": "Tongue Out",
    }
    
    for code, simple in simplifications.items():
        if code.lower() in marker.lower():
            return simple
    
    words = marker.split()
    if len(words) <= 3:
        return marker
    return " ".join(words[:2])


def validate_and_enrich_response(result: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and enrich the response with defaults"""
    
    if "overall_assessment" not in result:
        result["overall_assessment"] = {
            "distress_score": 50,
            "zone": "yellow",
            "confidence": "low",
            "primary_state": "unknown"
        }
    
    assessment = result["overall_assessment"]
    
    if "distress_score" not in assessment:
        assessment["distress_score"] = 50
    else:
        assessment["distress_score"] = max(0, min(100, assessment["distress_score"]))
    
    score = assessment["distress_score"]
    if score <= 33:
        assessment["zone"] = "green"
    elif score <= 66:
        assessment["zone"] = "yellow"
    else:
        assessment["zone"] = "red"
    
    if "timeline" not in result:
        result["timeline"] = []
    
    if "visual_analysis" in result:
        if "action_units_detected" in result["visual_analysis"]:
            result["visual_analysis"]["action_units_detected"] = [
                simplify_marker(m) for m in result["visual_analysis"]["action_units_detected"]
            ]
    
    if "interpret_lines" not in result:
        result["interpret_lines"] = []
    
    if "advisory" not in result:
        result["advisory"] = {
            "headline": "Continue monitoring your pet's behavior.",
            "detailed_recommendations": [],
            "urgency": "routine"
        }
    
    result["_metadata"] = {
        "analysis_version": "3.0",
        "timestamp": time.time()
    }
    
    return result


def analyze_video(
    video_data: bytes,
    filename: str = "video.mp4",
    use_cache: bool = True,
    analysis_mode: str = "full"
) -> Dict[str, Any]:
    """Analyze a pet video using Gemini."""
    
    # Check cache first
    video_hash = get_video_hash(video_data)
    if use_cache:
        cached = check_cache(video_hash)
        if cached:
            cached["_from_cache"] = True
            return cached
    
    # Get model
    model_name, model = get_available_model()
    
    # Determine mime type
    extension = Path(filename).suffix.lower()
    mime_types = {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska"
    }
    mime_type = mime_types.get(extension, "video/mp4")
    
    # Build prompt
    if analysis_mode == "quick":
        system_prompt = QUICK_ANALYSIS_PROMPT
    else:
        system_prompt = ETHOLOGICAL_SYSTEM_PROMPT
    
    full_prompt = f"""{system_prompt}

Analyze this video and return a JSON object with this structure:
{{
    "pet_detected": true,
    "species": "dog" or "cat",
    "breed_detected": "breed name or null",
    "breed_confidence": "high/medium/low",
    "video_context": "brief description of setting",
    "video_type": "single_moment" or "compilation",
    "overall_assessment": {{
        "distress_score": 0-100,
        "zone": "green/yellow/red",
        "zone_label": "LOW/MODERATE/ELEVATED",
        "confidence": "high/medium/low",
        "primary_state": "relaxed/alert/anxious/fearful/playful/etc",
        "summary": "2-3 sentence assessment"
    }},
    "visual_analysis": {{
        "facs_codes_detected": [{{"code": "EAD101", "description": "Ears forward"}}],
        "key_observations": ["observable behaviors"],
        "body_posture": "description"
    }},
    "audio_analysis": {{
        "vocalizations_detected": [
            {{
                "timestamp_start": "0:05",
                "timestamp_end": "0:07",
                "type": "bark/meow/whine/growl/purr",
                "interpretation": "what it likely means"
            }}
        ]
    }},
    "timeline": [
        {{
            "timestamp": "0:00",
            "context_tag": "2-word description",
            "distress_score": 0-100,
            "zone": "green/yellow/red",
            "observation": "what the pet is doing"
        }}
    ],
    "interpret_lines": [
        {{
            "timestamp": "0:03",
            "first_person_interpretation": "I feel curious about this...",
            "zone": "green/yellow/red"
        }}
    ],
    "advisory": {{
        "headline": "Contextual recommendation",
        "detailed_recommendations": ["specific advice"],
        "urgency": "routine/monitor/intervene/urgent"
    }}
}}

If NO dog or cat is visible, return:
{{"pet_detected": false, "message": "No pet detected"}}

Return ONLY valid JSON, no markdown."""

    try:
        # Create video part
        video_part = {
            "mime_type": mime_type,
            "data": base64.b64encode(video_data).decode('utf-8')
        }
        
        print(f"Sending video to {model_name}, size: {len(video_data)} bytes")
        
        response = model.generate_content(
            [
                full_prompt,
                {"inline_data": video_part}
            ],
            generation_config={
                "temperature": 0.2,
                "max_output_tokens": 8192
            }
        )
        
        response_text = response.text if response else ""
        print(f"Gemini response received, length: {len(response_text)}")
        
        result = parse_gemini_response(response_text)
        
        # Check for pet detection failure
        if result.get("pet_detected") == False:
            return {
                "error": True,
                "error_type": "no_pet_detected",
                "message": result.get("message", "No pet detected in video"),
                "_model_used": model_name,
                "_from_cache": False
            }
        
        result = validate_and_enrich_response(result)
        result["_model_used"] = model_name
        result["_from_cache"] = False
        
        if use_cache:
            store_cache(video_hash, result)
        
        return result
        
    except Exception as e:
        import traceback
        print(f"Gemini analysis error: {str(e)}")
        print(traceback.format_exc())
        return {
            "error": True,
            "error_message": str(e),
            "error_type": type(e).__name__,
            "overall_assessment": {
                "distress_score": 50,
                "zone": "yellow",
                "confidence": "low",
                "primary_state": "error"
            },
            "timeline": [],
            "interpret_lines": [],
            "advisory": {
                "headline": "Analysis could not be completed. Please try again.",
                "detailed_recommendations": [],
                "urgency": "routine"
            },
            "_model_used": model_name if 'model_name' in dir() else "unknown",
            "_from_cache": False
        }


def analyze_audio_only(
    video_data: bytes,
    filename: str = "video.mp4"
) -> Dict[str, Any]:
    """Analyze only the audio track from a video"""
    from app.prompts.ethological_prompt import AUDIO_ANALYSIS_PROMPT
    
    model_name, model = get_available_model()
    
    extension = Path(filename).suffix.lower()
    mime_types = {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".webm": "video/webm"
    }
    mime_type = mime_types.get(extension, "video/mp4")
    
    try:
        video_part = {
            "mime_type": mime_type,
            "data": base64.b64encode(video_data).decode('utf-8')
        }
        
        response = model.generate_content(
            [
                AUDIO_ANALYSIS_PROMPT,
                {"inline_data": video_part}
            ],
            generation_config={
                "temperature": 0.2,
                "max_output_tokens": 4096
            }
        )
        
        return parse_gemini_response(response.text)
        
    except Exception as e:
        return {
            "error": True,
            "error_message": str(e),
            "vocalizations": []
        }
