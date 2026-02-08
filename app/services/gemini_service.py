"""
Gemini Video Analysis Service for Etho
Full video understanding with complete ethological research framework
"""

import os
import json
import time
import re
import google.generativeai as genai
from ..prompts.ethological_prompt import ETHOLOGICAL_SYSTEM_PROMPT

# Configure Gemini
def get_gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    genai.configure(api_key=api_key)
    return genai


def upload_video_to_gemini(video_path: str):
    """
    Upload video to Gemini File API for processing.
    Gemini can handle full video understanding natively.
    """
    print(f"  → Uploading video to Gemini...")
    
    # Determine mime type
    ext = os.path.splitext(video_path)[1].lower()
    mime_types = {
        '.mp4': 'video/mp4',
        '.mov': 'video/quicktime',
        '.avi': 'video/x-msvideo',
        '.webm': 'video/webm',
        '.mkv': 'video/x-matroska',
    }
    mime_type = mime_types.get(ext, 'video/mp4')
    
    # Upload file
    video_file = genai.upload_file(path=video_path, mime_type=mime_type)
    print(f"  → Uploaded: {video_file.name}")
    
    # Wait for processing
    print(f"  → Waiting for Gemini to process video...")
    while video_file.state.name == "PROCESSING":
        time.sleep(2)
        video_file = genai.get_file(video_file.name)
    
    if video_file.state.name == "FAILED":
        raise ValueError(f"Video processing failed: {video_file.state.name}")
    
    print(f"  ✓ Video ready for analysis")
    return video_file


def analyze_video_with_gemini(video_file, prompt: str):
    """
    Run analysis on uploaded video using Gemini's native video understanding.
    This is the heart of Etho - full multimodal analysis with research framework.
    """
    print(f"  → Running ethological analysis...")
    
    # Use Gemini 2.0 Flash for video understanding
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config={
            "temperature": 0.3,  # Lower for more consistent analysis
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
            "response_mime_type": "application/json",
        }
    )
    
    # Generate content with video + prompt
    response = model.generate_content(
        [video_file, prompt],
        request_options={"timeout": 300}  # 5 minute timeout for long videos
    )
    
    return response.text


def parse_json_response(response_text: str) -> dict:
    """
    Parse JSON from Gemini response, handling potential formatting issues.
    """
    # Try direct parse first
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON from markdown code blocks
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Try to find JSON object in response
    json_match = re.search(r'\{[\s\S]*\}', response_text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    
    # Return error structure
    return {
        "error": True,
        "error_type": "parse_error",
        "message": "Failed to parse JSON response",
        "raw_response": response_text[:1000]
    }


def validate_and_enrich_response(result: dict) -> dict:
    """
    Validate response structure and add any missing fields with defaults.
    """
    # Ensure required top-level fields
    defaults = {
        "pet_detected": True,
        "species": "unknown",
        "breed_detected": "unknown",
        "morphology_type": "standard",
        "morphology_adjustments_applied": [],
        "video_type": "single_shot",
        "video_context": "Pet video analysis",
        "overall_assessment": {
            "distress_score": 50,
            "zone": "yellow",
            "zone_label": "MODERATE",
            "confidence": "medium",
            "primary_state": "alert",
            "summary": "Analysis in progress"
        },
        "visual_analysis": {
            "facs_codes_detected": [],
            "key_observations": [],
            "body_posture": "Not assessed",
            "confidence": "medium"
        },
        "audio_analysis": {
            "vocalizations_detected": [],
            "solicitation_purr_detected": False
        },
        "timeline": [],
        "interpret_lines": [],
        "advisory": {
            "headline": "Continue monitoring",
            "detailed_recommendations": [],
            "urgency": "routine"
        }
    }
    
    # Merge defaults with result
    for key, default_value in defaults.items():
        if key not in result:
            result[key] = default_value
        elif isinstance(default_value, dict) and isinstance(result.get(key), dict):
            for subkey, subdefault in default_value.items():
                if subkey not in result[key]:
                    result[key][subkey] = subdefault
    
    # Validate zone consistency
    distress = result.get("overall_assessment", {}).get("distress_score", 50)
    if distress <= 33:
        result["overall_assessment"]["zone"] = "green"
        result["overall_assessment"]["zone_label"] = "LOW"
    elif distress <= 66:
        result["overall_assessment"]["zone"] = "yellow"
        result["overall_assessment"]["zone_label"] = "MODERATE"
    else:
        result["overall_assessment"]["zone"] = "red"
        result["overall_assessment"]["zone_label"] = "ELEVATED"
    
    # Ensure interpret_lines are 6 words or less
    if "interpret_lines" in result:
        for line in result["interpret_lines"]:
            if "first_person_interpretation" in line:
                words = line["first_person_interpretation"].split()
                if len(words) > 6:
                    line["first_person_interpretation"] = " ".join(words[:6])
    
    return result


def analyze_video(video_path: str, use_cache: bool = True) -> dict:
    """
    Main entry point for video analysis.
    Uploads video to Gemini and runs full ethological analysis.
    
    Args:
        video_path: Path to the video file
        use_cache: Whether to use cached results (not implemented yet)
    
    Returns:
        Complete ethological analysis result
    """
    print("\n" + "="*60)
    print("ETHO ANALYSIS - Gemini Video Understanding")
    print("="*60)
    
    video_file = None
    
    try:
        # Initialize Gemini
        get_gemini_client()
        
        # Step 1: Upload video
        print("\nStep 1/2: Uploading video to Gemini...")
        video_file = upload_video_to_gemini(video_path)
        
        # Step 2: Run ethological analysis
        print("\nStep 2/2: Running ethological analysis...")
        
        analysis_prompt = f"""
{ETHOLOGICAL_SYSTEM_PROMPT}

Analyze this pet video comprehensively using the ethological research frameworks above.

Pay close attention to:
1. MICRO-EXPRESSIONS: Brief facial signals (lip licks, whale eye, ear flicks, brow raises)
2. BODY LANGUAGE: Posture, weight distribution, tail position, muscle tension
3. VOCALIZATIONS: Any sounds, their pitch, duration, and pattern (apply Morton's Rules)
4. TEMPORAL CHANGES: How the pet's state changes throughout the video
5. CONTEXT: What's happening in the environment that might affect the pet
6. BREED MORPHOLOGY: Apply appropriate normalization rules for the detected breed

CRITICAL OUTPUT RULES:
- All interpret_lines first_person_interpretation MUST be 6 words or fewer - these are subtitles
- All context_tags MUST be 5 words or fewer
- Always cite specific FACS codes (EAD101, AU145, AD137, etc.) for dogs
- Always use FGS scoring for cats when pain signals are present
- Note any morphology adjustments applied
- For compilations, mention "This compilation shows multiple moments" in summary
- Provide at least 3-5 timeline markers with research basis
- Be CONSERVATIVE with green zone - if in doubt, use yellow
- NEVER say a hissing, growling, or cowering animal is "relaxed"

Return your analysis as valid JSON matching the expected schema.
"""
        
        response_text = analyze_video_with_gemini(video_file, analysis_prompt)
        result = parse_json_response(response_text)
        
        # Check for parse errors
        if result.get("error") and result.get("error_type") == "parse_error":
            print(f"  ⚠ Parse error, returning raw response")
            return result
        
        # Handle no pet detected
        if result.get("pet_detected") == False:
            return {
                "error": True,
                "error_type": "no_pet_detected",
                "message": result.get("message", "No pet detected in video"),
                "_model_used": "gemini-2.0-flash",
                "_from_cache": False
            }
        
        # Validate and enrich
        result = validate_and_enrich_response(result)
        
        # Add metadata
        result["_model_used"] = "gemini-2.0-flash"
        result["_from_cache"] = False
        result["_analysis_version"] = "etho-v13-gemini"
        
        print(f"\n✓ Analysis complete!")
        print(f"  Species: {result.get('species', 'unknown')}")
        print(f"  Breed: {result.get('breed_detected', 'unknown')}")
        print(f"  Distress: {result.get('overall_assessment', {}).get('distress_score', 'N/A')}")
        print(f"  Zone: {result.get('overall_assessment', {}).get('zone', 'N/A')}")
        
        return result
        
    except Exception as e:
        print(f"\n✗ Analysis failed: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            "error": True,
            "error_type": "analysis_failed",
            "message": str(e),
            "_model_used": "gemini-2.0-flash",
            "_from_cache": False
        }
    
    finally:
        # Clean up uploaded file
        if video_file:
            try:
                genai.delete_file(video_file.name)
                print(f"  → Cleaned up uploaded file")
            except:
                pass
