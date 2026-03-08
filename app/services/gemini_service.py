"""
Gemini Video Analysis Service for Etho
Full video understanding with complete ethological research framework
TWO-PASS VERIFICATION SYSTEM to prevent hallucinations
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


def run_scene_verification(video_file) -> dict:
    """
    PASS 1: Scene verification - What is ACTUALLY in this video?
    This prevents hallucinations by establishing ground truth first.
    """
    print(f"  → Pass 1: Scene verification...")
    
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config={
            "temperature": 0.1,  # Very low for factual accuracy
            "top_p": 0.95,
            "max_output_tokens": 2048,
            "response_mime_type": "application/json",
        }
    )
    
    scene_prompt = """
SCENE VERIFICATION - Answer ONLY what you can directly observe in this video.
Do NOT infer, assume, or imagine anything that isn't clearly visible.

Respond with JSON:
{
    "animals_visible": [
        {"type": "cat/dog/bird/rodent/etc", "description": "brief physical description", "count": 1}
    ],
    "other_animals_present": [
        {"type": "animal type", "description": "what kind", "location": "where in frame"}
    ],
    "humans_visible": true/false,
    "setting": "indoor/outdoor and specific location type you can SEE",
    "objects_visible": ["list only objects you can CLEARLY see"],
    "key_actions": ["list what the main animal ACTUALLY DOES - be specific"],
    "audio_description": "what sounds can you HEAR in this video",
    "video_duration_estimate": "approximately X seconds",
    "scene_summary": "2 sentences describing ONLY what you can verify seeing"
}

CRITICAL: 
- If you see a cat watching small animals in a cage, say that
- If you see a cat at a door, say that
- Do NOT confuse one scenario for another
- List ALL animals you can see, not just the main pet
- Be extremely literal and factual
"""
    
    response = model.generate_content(
        [video_file, scene_prompt],
        request_options={"timeout": 120}
    )
    
    try:
        scene_data = json.loads(response.text)
        print(f"  ✓ Scene verified: {scene_data.get('scene_summary', 'No summary')[:80]}...")
        return scene_data
    except:
        # Try to extract JSON
        json_match = re.search(r'\{[\s\S]*\}', response.text)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except:
                pass
        return {"scene_summary": "Scene verification failed", "animals_visible": []}


def analyze_video_with_context(video_file, scene_context: dict) -> str:
    """
    PASS 2: Full ethological analysis WITH scene context locked in.
    The AI must analyze based on the verified scene, not hallucinated context.
    """
    print(f"  → Pass 2: Ethological analysis with verified context...")
    
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config={
            "temperature": 0.3,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
            "response_mime_type": "application/json",
        }
    )
    
    # Build context string from scene verification
    animals = scene_context.get('animals_visible', [])
    other_animals = scene_context.get('other_animals_present', [])
    objects = scene_context.get('objects_visible', [])
    actions = scene_context.get('key_actions', [])
    setting = scene_context.get('setting', 'unknown')
    scene_summary = scene_context.get('scene_summary', '')
    
    context_str = f"""
## VERIFIED SCENE CONTEXT (You must base your analysis on THIS, not assumptions)

SETTING: {setting}

MAIN PET(S) VISIBLE: {json.dumps(animals)}

OTHER ANIMALS PRESENT: {json.dumps(other_animals) if other_animals else 'None'}

OBJECTS VISIBLE: {', '.join(objects) if objects else 'None specified'}

ACTIONS OBSERVED: {', '.join(actions) if actions else 'None specified'}

SCENE SUMMARY: {scene_summary}

AUDIO: {scene_context.get('audio_description', 'Not analyzed')}

---

CRITICAL INSTRUCTION: Your analysis MUST be consistent with the verified scene above.
- If other animals are present, this is likely a predator-prey or inter-species interaction
- If a door is mentioned, verify it's actually about a door, not something else
- Do NOT invent scenarios that contradict the verified scene
- The scene summary is ground truth - your analysis must match it
"""
    
    analysis_prompt = f"""
{ETHOLOGICAL_SYSTEM_PROMPT}

{context_str}

Now analyze this pet video using the ethological research frameworks.
Your analysis MUST be consistent with the VERIFIED SCENE CONTEXT above.

SPECIAL CONSIDERATIONS:
- If other animals are present (prey animals, other pets), analyze the interaction dynamics
- A cat watching guinea pigs/hamsters/birds is showing PREDATORY INTEREST, not door frustration
- A dog watching squirrels is showing PREY DRIVE, not anxiety
- Inter-species interactions require careful assessment of both animals' safety

Pay close attention to:
1. MICRO-EXPRESSIONS: Brief facial signals
2. BODY LANGUAGE: Posture, weight distribution, tail position, muscle tension
3. VOCALIZATIONS: Any sounds and their meaning per Morton's Rules
4. INTER-SPECIES DYNAMICS: If other animals present, assess predator-prey dynamics
5. CONTEXT: The VERIFIED scene context above is your ground truth
6. BREED MORPHOLOGY: Apply appropriate normalization rules

Return your analysis as valid JSON matching the expected schema.
"""
    
    response = model.generate_content(
        [video_file, analysis_prompt],
        request_options={"timeout": 300}
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


def validate_and_enrich_response(result: dict, scene_context: dict) -> dict:
    """
    Validate response structure and add any missing fields with defaults.
    Also inject verified scene context.
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
            "environmental_sounds": [],
            "solicitation_purr_detected": False
        },
        "timeline": [],
        "interpret_lines": [],
        "behavioral_markers": [],
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
    
    # Inject verified scene context
    result["_verified_scene"] = scene_context
    
    # Check for other animals - adjust analysis if predator-prey situation
    other_animals = scene_context.get('other_animals_present', [])
    if other_animals:
        result["_interaction_type"] = "inter_species"
        # Add warning if predator-prey and scored too low
        prey_types = ['guinea pig', 'hamster', 'bird', 'rabbit', 'mouse', 'fish', 'gerbil', 'rat']
        has_prey = any(
            any(prey in str(a.get('type', '')).lower() or prey in str(a.get('description', '')).lower() 
                for prey in prey_types)
            for a in other_animals
        )
        if has_prey and result.get('species', '').lower() in ['cat', 'dog']:
            # This is a predator-prey situation - ensure score reflects this
            if result.get('overall_assessment', {}).get('distress_score', 50) < 40:
                result['overall_assessment']['distress_score'] = max(45, result['overall_assessment']['distress_score'])
                result['overall_assessment']['zone'] = 'yellow'
                result['overall_assessment']['zone_label'] = 'MODERATE'
            # Add predator-prey note to advisory
            if 'advisory' not in result:
                result['advisory'] = {}
            result['advisory']['predator_prey_warning'] = True
            result['advisory']['headline'] = "Monitor inter-species interaction closely"
    
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
    
    # Ensure interpret_lines have proper format
    if "interpret_lines" in result:
        for line in result["interpret_lines"]:
            # Handle both pet_pov and first_person_interpretation
            text_field = line.get("pet_pov") or line.get("first_person_interpretation", "")
            if text_field:
                words = text_field.split()
                if len(words) > 10:
                    line["pet_pov"] = " ".join(words[:10])
                    line["first_person_interpretation"] = " ".join(words[:10])
    
    return result


def analyze_video(video_path: str, use_cache: bool = True) -> dict:
    """
    Main entry point for video analysis.
    Uses TWO-PASS VERIFICATION to prevent hallucinations:
    1. Scene verification - establish ground truth
    2. Ethological analysis - analyze with locked context
    
    Args:
        video_path: Path to the video file
        use_cache: Whether to use cached results (not implemented yet)
    
    Returns:
        Complete ethological analysis result
    """
    print("\n" + "="*60)
    print("ETHO ANALYSIS - Two-Pass Verification System")
    print("="*60)
    
    video_file = None
    
    try:
        # Initialize Gemini
        get_gemini_client()
        
        # Step 1: Upload video
        print("\nStep 1/3: Uploading video to Gemini...")
        video_file = upload_video_to_gemini(video_path)
        
        # Step 2: Scene verification (PASS 1)
        print("\nStep 2/3: Verifying scene content...")
        scene_context = run_scene_verification(video_file)
        
        # Log what we found
        print(f"  → Animals found: {scene_context.get('animals_visible', [])}")
        print(f"  → Other animals: {scene_context.get('other_animals_present', [])}")
        print(f"  → Setting: {scene_context.get('setting', 'unknown')}")
        
        # Step 3: Run ethological analysis (PASS 2) with verified context
        print("\nStep 3/3: Running ethological analysis with verified context...")
        
        response_text = analyze_video_with_context(video_file, scene_context)
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
                "_verified_scene": scene_context,
                "_from_cache": False
            }
        
        # Validate and enrich with scene context
        result = validate_and_enrich_response(result, scene_context)
        
        # Add metadata
        result["_model_used"] = "gemini-2.0-flash"
        result["_from_cache"] = False
        result["_analysis_version"] = "etho-v15-verified"
        
        print(f"\n✓ Analysis complete!")
        print(f"  Species: {result.get('species', 'unknown')}")
        print(f"  Breed: {result.get('breed_detected', 'unknown')}")
        print(f"  Distress: {result.get('overall_assessment', {}).get('distress_score', 'N/A')}")
        print(f"  Zone: {result.get('overall_assessment', {}).get('zone', 'N/A')}")
        if result.get('_interaction_type') == 'inter_species':
            print(f"  ⚠ Inter-species interaction detected!")
        
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
