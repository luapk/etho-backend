"""
Capture-protocol guidance and per-submission quality assessment.

Standardised capture is the cheapest noise reduction available to a
longitudinal behaviour record: the same pet filmed in the same room at the
same time of week produces comparable observations; ad-hoc clips produce
noise that no model upgrade can remove. This module has two halves:

  1. CAPTURE_PROTOCOL — versioned, structured guidance the frontend renders
     (weekly baseline cadence, incident capture, photo framing for the FGS).
  2. assess() — measured quality feedback attached to every analysis as a
     `capture_quality` block. Every check reports the measured value, the
     threshold applied, and concrete advice — the same transparency rule as
     the vet report. Users learn the protocol by using the tool.

Grades: good (all checks pass) / fair (any warning) / poor (any failure).
Quality is FEEDBACK, not a gate — a poor clip is still analysed, because an
incident clip of a limping dog is valuable even if it's dark and shaky.
"""

PROTOCOL_VERSION = "1.1"

CAPTURE_PROTOCOL = {
    "protocol_version": PROTOCOL_VERSION,
    "why_standardise": (
        "Trend analysis compares each pet against its own history. Filming "
        "under consistent conditions (same room, similar time of day, similar "
        "lighting) means changes in the data reflect changes in the PET, not "
        "changes in the camera work. One consistent 30-60s clip per week "
        "builds a scientifically useful baseline."
    ),
    "contexts": [
        {"tag": "weekly_baseline", "label": "Weekly baseline",
         "description": "Routine clip under standard conditions — the backbone of the record."},
        {"tag": "incident", "label": "Incident",
         "description": "Something concerning is happening right now (limping, distress, conflict)."},
        {"tag": "post_vet", "label": "Post-vet check",
         "description": "Follow-up after treatment or medication change."},
        {"tag": "sleeping_baseline", "label": "Sleeping (breathing rate)",
         "description": "Your pet FULLY ASLEEP — the only context where "
                        "breathing rate is measured. Meaningless on an awake pet."},
        {"tag": "other", "label": "Other", "description": "Anything else."},
    ],
    "video_baseline": {
        "title": "Weekly baseline clip",
        "rules": [
            "30-60 seconds, phone held landscape",
            "Same room and similar time of day each week",
            "Good, even lighting — avoid filming against a window",
            "Keep the whole pet in frame; follow them at a calm pace",
            "Let them behave freely — don't call, lure, or prompt them",
            "Keep background noise low so vocalisations are analysable",
            "Include the face clearly at least once (facial-signal scoring)",
        ],
    },
    "video_incident": {
        "title": "Incident capture",
        "rules": [
            "Safety first — never provoke or approach a distressed animal to film it",
            "Start filming as soon as possible; context before/after is valuable",
            "Keep filming through the episode if safe — duration reveals patterns",
            "Don't switch rooms/lights mid-clip if avoidable",
            "Tag the upload as 'incident' so it isn't mixed into baseline trends",
        ],
    },
    "sleeping_srr": {
        "title": "Sleeping breathing-rate clip (SRR)",
        "requires_sleeping_pet": True,
        "why": (
            "Sleeping respiratory rate is the one home measurement with "
            "published veterinary thresholds behind it — vets already ask "
            "cardiac patients' owners to count it by hand. It is ONLY valid "
            "while the pet is fully asleep: an awake, moving, or panting "
            "animal makes the number meaningless, so Etho refuses to report "
            "a rate from those clips."
        ),
        "rules": [
            "Pet must be FULLY ASLEEP — not dozing, not settling, asleep",
            "Not panting, and not within an hour of exercise or stress",
            "Prop the phone still (lean it on something) — do not hand-hold",
            "Whole chest/flank visible; film from the side if possible",
            "30-60 seconds; longer is better for accuracy",
            "Don't zoom, don't move the camera, don't wake them",
            "Tag the upload as 'Sleeping (breathing rate)'",
        ],
    },
    "photo": {
        "title": "Photos (facial scoring)",
        "rules": [
            "Front-on or slight angle, at the pet's eye level",
            "Ears, eyes, muzzle and whiskers all visible (these are the scored items)",
            "Neutral moment — not mid-yawn, mid-meow, or mid-play",
            "Sharp focus and good light on the face",
        ],
    },
}

# Thresholds (stated in every check result so nothing is a black box)
_COVERAGE_PASS, _COVERAGE_WARN = 0.8, 0.5
_DURATION_MIN, _DURATION_IDEAL_LO, _DURATION_IDEAL_HI = 10, 20, 90
_BRIGHT_PASS, _BRIGHT_WARN = 70, 40
_MIN_DIMENSION = 480
_FACE_PASS = 0.4   # face located in >= 40% of pet-visible frames


def _check(name, status, measured, threshold, advice):
    return {"check": name, "status": status, "measured": measured,
            "threshold": threshold, "advice": advice}


def assess(media_type: str, pose_metrics: dict = None,
           audio_metrics: dict = None, media_meta: dict = None,
           yolo_available: bool = True, respiration: dict = None) -> dict:
    """Grade a submission's technical capture quality from already-computed
    data. Never raises; unknown inputs degrade to 'unknown' status checks."""
    pose_metrics = pose_metrics or {}
    audio_metrics = audio_metrics or {}
    media_meta = media_meta or {}
    checks = []

    # ── Framing: was the pet actually in frame? (video, needs YOLO) ──
    if media_type == "video":
        cov = pose_metrics.get("detection_coverage")
        if cov is not None and yolo_available:
            if cov >= _COVERAGE_PASS:
                checks.append(_check("framing", "pass", f"pet in frame {cov:.0%} of clip",
                                     f">= {_COVERAGE_PASS:.0%}", None))
            elif cov >= _COVERAGE_WARN:
                checks.append(_check("framing", "warn", f"pet in frame {cov:.0%} of clip",
                                     f">= {_COVERAGE_PASS:.0%}",
                                     "Keep the whole pet in frame — hold landscape and follow calmly."))
            else:
                checks.append(_check("framing", "fail", f"pet in frame only {cov:.0%} of clip",
                                     f">= {_COVERAGE_WARN:.0%}",
                                     "Most of this clip has no detectable pet. Re-film keeping them centred."))
        else:
            checks.append(_check("framing", "unknown", None, None,
                                 "Pose tracking unavailable — framing not assessed."))

    # ── Duration (video) ──
    if media_type == "video":
        dur = media_meta.get("duration_sec")
        if dur is not None:
            if dur < _DURATION_MIN:
                checks.append(_check("duration", "fail", f"{dur}s", f">= {_DURATION_MIN}s",
                                     "Too short to capture a behavioural sequence — aim for 30-60 seconds."))
            elif dur < _DURATION_IDEAL_LO:
                checks.append(_check("duration", "warn", f"{dur}s",
                                     f"{_DURATION_IDEAL_LO}-{_DURATION_IDEAL_HI}s ideal",
                                     "Usable, but 30-60 seconds gives a fuller behavioural picture."))
            elif dur <= _DURATION_IDEAL_HI:
                checks.append(_check("duration", "pass", f"{dur}s",
                                     f"{_DURATION_IDEAL_LO}-{_DURATION_IDEAL_HI}s ideal", None))
            else:
                checks.append(_check("duration", "warn", f"{dur}s",
                                     f"{_DURATION_IDEAL_LO}-{_DURATION_IDEAL_HI}s ideal",
                                     "Long clips dilute the analysis — 30-60 seconds is the sweet spot."))

    # ── Audio present? (video) ──
    if media_type == "video":
        if audio_metrics.get("audio_present"):
            checks.append(_check("audio", "pass", "audio track present", "present", None))
        elif audio_metrics:
            checks.append(_check("audio", "warn", "no usable audio",
                                 "audio track present",
                                 "No audio — vocal analysis skipped. Check the mic isn't muted/covered."))
        else:
            checks.append(_check("audio", "unknown", None, None,
                                 "Audio analysis unavailable — not assessed."))

    # ── Brightness (both) ──
    bright = media_meta.get("brightness")
    if bright is not None:
        if bright >= _BRIGHT_PASS:
            checks.append(_check("lighting", "pass", f"mean brightness {bright}/255",
                                 f">= {_BRIGHT_PASS}", None))
        elif bright >= _BRIGHT_WARN:
            checks.append(_check("lighting", "warn", f"mean brightness {bright}/255",
                                 f">= {_BRIGHT_PASS}",
                                 "Dim footage weakens facial-signal scoring — add light or film by a window (not against it)."))
        else:
            checks.append(_check("lighting", "fail", f"mean brightness {bright}/255",
                                 f">= {_BRIGHT_WARN}",
                                 "Too dark for reliable visual analysis — re-film with more light."))

    # ── Resolution (both) ──
    w, h = media_meta.get("width"), media_meta.get("height")
    if w and h:
        short_side = min(w, h)
        if short_side >= _MIN_DIMENSION:
            checks.append(_check("resolution", "pass", f"{w}x{h}",
                                 f"short side >= {_MIN_DIMENSION}px", None))
        else:
            checks.append(_check("resolution", "warn", f"{w}x{h}",
                                 f"short side >= {_MIN_DIMENSION}px",
                                 "Low resolution limits keypoint and facial detail — use the main camera, not zoom."))

    # ── Face visibility (facial-instrument scoreability, both media) ──
    face = pose_metrics.get("face_visibility")
    if face is not None and yolo_available:
        if face >= _FACE_PASS:
            checks.append(_check("face_visibility", "pass",
                                 f"face located in {face:.0%} of pet-visible frames",
                                 f">= {_FACE_PASS:.0%}", None))
        else:
            checks.append(_check("face_visibility", "warn",
                                 f"face located in {face:.0%} of pet-visible frames",
                                 f">= {_FACE_PASS:.0%}",
                                 "Face rarely visible — grimace/facial items may not be scorable. "
                                 "Include a clear front-on view of the face at least once."))

    # ── Pet visible at all? (image) ──
    if media_type == "image" and yolo_available:
        cov = pose_metrics.get("detection_coverage")
        if cov is not None:
            if cov > 0:
                checks.append(_check("pet_visible", "pass", "pet detected", "detected", None))
            else:
                checks.append(_check("pet_visible", "warn", "no pet detected by pose model",
                                     "detected",
                                     "Pose model found no cat/dog — the AI analysis may still work, but framing per the photo guide helps."))

    # ── Respiratory measurability (sleeping_baseline clips only) ──
    if respiration is not None:
        if respiration.get("usable"):
            checks.append(_check(
                "respiration", "pass",
                f"{respiration['breaths_per_min']} breaths/min "
                f"({respiration.get('confidence')} confidence)",
                "measurable from a sleeping clip", None))
        else:
            checks.append(_check(
                "respiration", "warn",
                respiration.get("reason", "not measurable"),
                "pet fully asleep, camera propped still, 30s+",
                "Breathing rate needs a SLEEPING pet: prop the camera still, "
                "keep the chest/flank in frame, and film for 30-60 seconds "
                "without waking them."))

    statuses = {c["status"] for c in checks}
    grade = "poor" if "fail" in statuses else ("fair" if "warn" in statuses else "good")
    advice = [c["advice"] for c in checks if c["advice"] and c["status"] in ("warn", "fail")]

    return {
        "grade": grade,
        "checks": checks,
        "advice": advice,
        "protocol_version": PROTOCOL_VERSION,
        "note": "Quality feedback only — the analysis always runs. Incident clips are valuable even when imperfect.",
    }
