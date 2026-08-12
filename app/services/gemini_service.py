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
from ..prompts.ethological_prompt import ETHOLOGICAL_SYSTEM_PROMPT, PROMPT_VERSION
from . import model_selector
from .respiration_service import SRR_THRESHOLD_BPM as SRR_THRESHOLD

# Model is configurable so upgrades are a config change, not a deploy of new
# code. Every stored analysis is stamped with the model that produced it
# (model_used column), so longitudinal records stay interpretable across
# upgrades.
#
# Pinned by default — a longitudinal record needs a stable instrument, so
# model changes should be deliberate (scripts/check_models.py to see what's
# available, then the repeatability study to confirm scores stay consistent).
# GEMINI_MODEL=auto resolves the newest suitable model once at import,
# falling back to the pinned default if discovery fails.
GEMINI_MODEL = model_selector.resolve_model(
    os.environ.get("GEMINI_MODEL", model_selector.STABLE_DEFAULT),
    prefer_tier=os.environ.get("GEMINI_MODEL_TIER", "flash"),
)

# Configure Gemini
def get_gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    genai.configure(api_key=api_key)
    return genai


def upload_video_to_gemini(video_path: str):
    """
    Upload media (video or image) to Gemini File API for processing.
    Gemini handles both natively; videos get a processing wait.
    """
    print(f"  → Uploading media to Gemini...")

    # Determine mime type
    ext = os.path.splitext(video_path)[1].lower()
    mime_types = {
        '.mp4': 'video/mp4',
        '.mov': 'video/quicktime',
        '.avi': 'video/x-msvideo',
        '.webm': 'video/webm',
        '.mkv': 'video/x-matroska',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.webp': 'image/webp',
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


def run_scene_verification(video_file, media_kind: str = "video") -> dict:
    """
    PASS 1: Scene verification - What is ACTUALLY in this media?
    This prevents hallucinations by establishing ground truth first.

    The wording is media-specific, and that matters more here than anywhere
    else in the pipeline. Pass 2 treats this object as a hard constraint it
    cannot contradict, so a question that presumes duration ("what sounds can
    you hear", "what does the animal DO") aimed at a photograph doesn't just
    produce one bad field — it mints a fabricated ground truth that the whole
    analysis is then obliged to honour. Asking a still only what a still can
    answer is what keeps the lock trustworthy.
    """
    print(f"  → Pass 1: Scene verification ({media_kind})...")
    
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        generation_config={
            "temperature": 0.1,  # Very low for factual accuracy
            "top_p": 0.95,
            "max_output_tokens": 2048,
            "response_mime_type": "application/json",
        }
    )
    
    if media_kind == "image":
        scene_prompt = """
SCENE VERIFICATION - This is a SINGLE PHOTOGRAPH. Answer ONLY what is visible
in this one frame. Do NOT infer, assume, or imagine anything that isn't
clearly visible, and do NOT describe motion or sound: a photograph contains
neither. If you cannot tell whether the animal was moving, that is the correct
answer.

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
    "visible_posture": ["the main animal's POSTURE and POSITION as frozen here — e.g. 'lying on left side', 'ears flattened back', 'tail tucked under body'. Positions, not actions."],
    "framing": "close-up of face / head and shoulders / whole body / partial — and whether the face is visible",
    "scene_summary": "2 sentences describing ONLY what you can verify seeing in this frame"
}

CRITICAL:
- NO verbs of motion. Not 'walking', 'wagging', 'approaching', 'trembling'.
  Describe the pose, not what produced it.
- NO sounds. There is no audio in a photograph.
- NO sequence. There is no before or after in a photograph.
- List ALL animals you can see, not just the main pet
- Be extremely literal and factual
"""
    else:
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


def _build_audio_section(audio_metrics: dict) -> str:
    """Render measured acoustics as a ground-truth block for Pass 2, mirroring
    the YOLO pose section. Measured values are objective; Morton labels prime."""
    if not audio_metrics or not audio_metrics.get("audio_present"):
        return ""

    s = "\n## AUDIO ACOUSTIC MEASUREMENTS (Signal-Processing Ground Truth)\n"
    s += ("These are objectively measured from the audio track (pitch via "
          "autocorrelation, tonality via spectral flatness, 220-520 Hz "
          "solicitation-purr band). Cite them when making vocalization claims.\n\n")

    cov = audio_metrics.get("vocal_activity_coverage", 0)
    dur = audio_metrics.get("duration_analyzed_sec", 0)
    s += f"AUDIO ANALYSED: {dur}s  |  VOCAL ACTIVITY COVERAGE: {cov:.0%}\n"

    if "pitch" in audio_metrics:
        p = audio_metrics["pitch"]
        s += f"PITCH (F0): mean {p['mean_hz']} Hz (range {p['min_hz']}-{p['max_hz']} Hz)\n"
    ton = audio_metrics.get("tonality", {})
    if ton:
        s += (f"TONALITY: mean spectral flatness {ton.get('mean_flatness')} "
              f"— {ton.get('interpretation')} "
              f"(Morton: tonal=fear/appeasement, noisy/rough=threat)\n")
    purr = audio_metrics.get("solicitation_purr", {})
    if purr:
        s += (f"SOLICITATION-PURR BAND (220-520 Hz): peak ratio "
              f"{purr.get('peak_purr_band_ratio')} — "
              f"{'POSSIBLE solicitation purr' if purr.get('possible') else 'not indicated'} "
              f"(heuristic; confirm audibly)\n")

    events = audio_metrics.get("vocalization_events", [])
    if events:
        s += f"\nMEASURED VOCALIZATION EVENTS ({audio_metrics.get('vocalization_event_count', len(events))} total):\n"
        for ev in events:
            mm = int(ev["timestamp_sec"] // 60)
            ss = int(ev["timestamp_sec"] % 60)
            pitch = f"{ev['pitch_hz']}Hz" if ev.get("pitch_hz") is not None else "unvoiced"
            s += (f"  - {mm}:{ss:02d} dur {ev['duration_sec']}s, {pitch} "
                  f"{ev.get('pitch_contour', '')}, {ev.get('tonality', '')} "
                  f"→ {ev.get('morton_inference', '')}\n")

    s += (
        "\nINTEGRATION RULE: When describing vocalizations, cite these measured "
        "acoustics, e.g. 'growl measured at 180 Hz, noisy spectrum (Morton: low + "
        "rough = threat)' rather than vague terms. You identify WHAT each sound is "
        "(bark/meow/growl/purr/whine); the measurements tell you its pitch and "
        "quality. If your identification conflicts with a measurement, report both "
        "and note the discrepancy.\n"
        "\nPHYSICAL CONSTRAINTS ON IDENTIFICATION — these are properties of the "
        "sound, not preferences, and context cannot override them:\n"
        "  - A cat PURR has a fundamental of roughly 20-40 Hz. The 220-520 Hz "
        "band above is the CRY embedded in a solicitation purr, not the purr "
        "itself. A tonal sound measured above ~600 Hz is NOT a purr no matter "
        "how relaxed the animal looks — it is a meow, chirp or trill. Relaxed "
        "body language is evidence about the ANIMAL, never about the frequency.\n"
        "  - A growl is low and broadband; a measured high, tonal sound is not "
        "a growl.\n"
        "  - Purring and meowing are different vocalizations and can co-occur; "
        "name the one the measurement supports, and say if you believe another "
        "is present but unmeasured.\n"
    )
    return s


def _build_resp_section(respiration: dict) -> str:
    """Measured sleeping respiratory rate for Pass 2 — only for clips the
    guardian tagged as sleeping, and only when the DSP judged it usable."""
    if not respiration or not respiration.get("usable"):
        return ""
    bpm = respiration["breaths_per_min"]
    s = "\n## RESPIRATORY MEASUREMENT (Sleeping clip — Signal-Processing Ground Truth)\n"
    s += (f"SLEEPING RESPIRATORY RATE: {bpm} breaths/min "
          f"({respiration.get('confidence')} confidence, "
          f"{respiration.get('window_sec')}s window, measured from chest "
          f"motion)\n")
    s += (f"CONTEXT: {respiration.get('threshold_note')}\n"
          "INTEGRATION RULE: This clip was submitted as a SLEEPING baseline. "
          "Cite this measured rate in any respiratory observation. If the "
          f"rate exceeds {SRR_THRESHOLD} breaths/min, note it as exceeding "
          "the published sleeping-RR screening threshold and recommend "
          "discussing with a vet — do NOT name a diagnosis. If the animal "
          "does not appear asleep in this clip, say so explicitly: the "
          "measurement is only valid for a sleeping pet.\n")
    return s


_IMAGE_MODE_ADDENDUM = """
## IMAGE MODE
This submission is a SINGLE STILL IMAGE, not a video. A still supports a
different — and in one respect stronger — kind of claim than a clip, so adapt
rather than producing a thinner video analysis.

STRUCTURE
- timeline: exactly one entry at timestamp "0:00" describing the captured moment
- interpret_lines: at most one entry at "0:00"
- audio_analysis: empty lists, solicitation_purr_detected false (no audio exists)
- video_type: "single_image"

WHAT YOU CANNOT SEE IN A STILL
A frozen frame carries no duration, so anything defined by change over time is
unobservable here. Do NOT report, and do NOT let it influence the score:
- movement of any kind — pacing, tail wagging, trembling, approaching, fleeing,
  circling, shifting weight
- tail-wag lateralisation (Quaranta 2007 requires wag direction over time)
- vocalizations, purring, panting sounds, breathing rate
- sequences, escalation, settling, or "then"/"before"/"after" narration
- repetition or frequency of any behaviour

A posture can be described as it appears ("weight shifted onto the hind legs",
"tail held low") — that is visible. What it was doing a second earlier is not.

WHAT A STILL SUPPORTS WELL
Facial action units, body posture, ear and tail POSITION, pupil and eye
aperture, muscle tension, and piloerection are all readable from one frame.
The Feline Grimace Scale in particular was VALIDATED on still images, so for a
cat this is the instrument's intended input, not a compromise — score it
carefully and say so in the confidence reasoning.

CONFIDENCE
State plainly that this is a single moment. A calm frame does not establish a
calm animal, and a tense frame does not establish sustained distress; one
photo is one sample of a behaviour that varies. Reflect that in `confidence`
rather than hedging the observations themselves.
"""


def analyze_video_with_context(video_file, scene_context: dict, pose_metrics: dict = None,
                               audio_metrics: dict = None, media_kind: str = "video",
                               respiration: dict = None) -> str:
    """
    PASS 2: Full ethological analysis WITH scene context locked in.
    The AI must analyze based on the verified scene, not hallucinated context.
    pose_metrics: optional YOLO-derived measurements injected as objective ground truth.
    audio_metrics: optional signal-processing acoustics injected as ground truth.
    media_kind: "video" or "image" — images get a single-moment addendum.
    """
    print(f"  → Pass 2: Ethological analysis with verified context...")
    
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
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
    
    # Build optional YOLO pose section
    pose_section = ""
    if pose_metrics:
        pose_section = "\n## YOLO11-POSE MEASUREMENTS (Computer Vision Ground Truth)\n"
        pose_section += "These are objectively measured from video frames — cite them when making posture claims.\n\n"
        cov = pose_metrics.get("detection_coverage", 0)
        pose_section += f"PET DETECTION COVERAGE: {cov:.0%} of sampled frames\n"
        # Only measurements that passed their reliability gates are presented
        # as ground truth. A pose model trained on humans can emit confident
        # nonsense on a quadruped, and stating it here would have Gemini cite
        # a fabricated posture as fact.
        if "spinal_curvature" in pose_metrics:
            sc = pose_metrics["spinal_curvature"]
            if sc.get("reliable", True):
                pose_section += (f"SPINAL CURVATURE: mean {sc['mean_deg']}°, "
                                 f"peak {sc['max_deg']}° — "
                                 f"{sc.get('interpretation', '')}\n")
            else:
                pose_section += (
                    "SPINAL CURVATURE: NOT RELIABLY MEASURABLE on this clip "
                    f"({sc.get('unreliable_reason', 'failed validity checks')}). "
                    "Do NOT cite any spinal angle. Assess posture visually and "
                    "say so plainly.\n")
        if "head_tilt" in pose_metrics:
            ht = pose_metrics["head_tilt"]
            if ht.get("reliable", True):
                pose_section += (f"HEAD TILT: mean {ht['mean_deg']}°, "
                                 f"max {ht['max_abs_deg']}°\n")
            else:
                pose_section += ("HEAD TILT: not reliably measurable on this "
                                 "clip — do not cite a tilt angle.\n")
        if "face_visibility" in pose_metrics:
            fv = pose_metrics["face_visibility"]
            pose_section += f"FACE VISIBILITY: {fv:.0%} of pet-visible frames\n"
            if fv < 0.4:
                pose_section += (
                    "NOTE: The face is rarely visible in this footage. Score facial "
                    "instrument items (grimace/FACS) ONLY from moments where the face "
                    "is genuinely assessable — otherwise mark them visible=false. Do "
                    "not infer facial signals from body posture.\n"
                )
        pose_section += (
            "\nINTEGRATION RULE: When describing posture, write e.g. "
            "'shows 22° spinal curvature (YOLO-measured), consistent with submissive posture' "
            "rather than vague terms like 'appears hunched'.\n"
        )

    audio_section = _build_audio_section(audio_metrics)
    resp_section = _build_resp_section(respiration)
    image_section = _IMAGE_MODE_ADDENDUM if media_kind == "image" else ""

    context_str = f"""
## VERIFIED SCENE CONTEXT (You must base your analysis on THIS, not assumptions)

SETTING: {setting}

MAIN PET(S) VISIBLE: {json.dumps(animals)}

OTHER ANIMALS PRESENT: {json.dumps(other_animals) if other_animals else 'None'}

OBJECTS VISIBLE: {', '.join(objects) if objects else 'None specified'}

ACTIONS OBSERVED: {', '.join(actions) if actions else 'None specified'}

SCENE SUMMARY: {scene_summary}

AUDIO: {scene_context.get('audio_description', 'Not analyzed')}
{pose_section}{audio_section}{resp_section}{image_section}
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
- A cat breathing with an OPEN MOUTH (not vocalizing) is an urgent red flag: note it prominently and set advisory urgency to critical

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
        },
        "instrument_scores": {
            "instrument": "not_scored",
            "items": [],
            "total": None,
            "max_total": None,
            "items_scorable": 0,
            "caveat": "Instrument not scored for this submission"
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
    
    # Validate instrument scores: clamp item scores to [0, max], recompute the
    # total from visible items only, never trust a self-reported total.
    ins = result.get("instrument_scores")
    if isinstance(ins, dict) and isinstance(ins.get("items"), list):
        total = 0.0
        scorable = 0
        any_scored = False
        for item in ins["items"]:
            if not isinstance(item, dict):
                continue
            max_score = item.get("max", 2) or 2
            if item.get("visible") is False or item.get("score") is None:
                item["score"] = None
                continue
            try:
                score = float(item["score"])
            except (TypeError, ValueError):
                item["score"] = None
                continue
            item["score"] = max(0, min(score, max_score))
            total += item["score"]
            scorable += 1
            any_scored = True
        if any_scored:
            ins["total"] = round(total, 1)
            ins["items_scorable"] = scorable
        else:
            ins["total"] = None
            ins["items_scorable"] = 0

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


def enforce_image_mode(result: dict) -> dict:
    """Hold a still-image analysis to what a still can actually support.

    The prompt asks for this, but asking isn't enough — the same reason
    instrument totals are recomputed rather than trusted. A model handed a
    photo will sometimes still emit a multi-entry timeline or a vocalization,
    and once that reaches the record it is indistinguishable from an observed
    one: a timeline implies a sequence nobody watched, and a "detected" bark
    implies audio that does not exist in a JPEG.

    So the structure is clamped here. What the model saw in the frame is kept
    in full; only claims that require duration or sound are removed.
    """
    audio = result.get("audio_analysis")
    if isinstance(audio, dict):
        audio["vocalizations_detected"] = []
        audio["environmental_sounds"] = []
        audio["solicitation_purr_detected"] = False
        audio["not_applicable"] = "Single image — no audio track exists."

    # One frame is one moment. Extra entries would be invented sequence.
    for key in ("timeline", "interpret_lines"):
        entries = result.get(key)
        if isinstance(entries, list) and entries:
            first = entries[0]
            if isinstance(first, dict):
                first["timestamp"] = "0:00"
            result[key] = [first]

    result["video_type"] = "single_image"
    return result


def analyze_video(video_path: str, use_cache: bool = True, pose_metrics: dict = None,
                  audio_metrics: dict = None, media_kind: str = "video",
                  respiration: dict = None) -> dict:
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
        scene_context = run_scene_verification(video_file, media_kind)
        
        # Log what we found
        print(f"  → Animals found: {scene_context.get('animals_visible', [])}")
        print(f"  → Other animals: {scene_context.get('other_animals_present', [])}")
        print(f"  → Setting: {scene_context.get('setting', 'unknown')}")
        
        # Step 3: Run ethological analysis (PASS 2) with verified context + pose data
        if pose_metrics:
            print(f"\nStep 3/3: Running ethological analysis (pose metrics injected)...")
        else:
            print("\nStep 3/3: Running ethological analysis with verified context...")
        
        response_text = analyze_video_with_context(video_file, scene_context, pose_metrics,
                                                   audio_metrics, media_kind, respiration)
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
                "_model_used": GEMINI_MODEL,
                "_verified_scene": scene_context,
                "_from_cache": False
            }
        
        # Validate and enrich with scene context
        result = validate_and_enrich_response(result, scene_context)
        if media_kind == "image":
            result = enforce_image_mode(result)

        # Add metadata
        result["_model_used"] = GEMINI_MODEL
        result["_from_cache"] = False
        result["_analysis_version"] = "etho-v17-longitudinal"
        result["_prompt_version"] = PROMPT_VERSION
        result["_media_kind"] = media_kind
        if pose_metrics:
            result["_pose_metrics"] = pose_metrics
        if audio_metrics:
            result["_audio_metrics"] = audio_metrics
        if respiration:
            result["_respiration"] = respiration
        
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
            "_model_used": GEMINI_MODEL,
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
