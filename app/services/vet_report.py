"""
Pre-consultation veterinary report builder.

Compiles a pet's longitudinal analysis history into a structured document a
guardian can hand to their vet before an appointment. Framing rules that make
this credible to a clinician rather than AI noise:

  1. OBSERVATIONS, NEVER DIAGNOSES — the report presents measured and
     AI-estimated observations with dates; interpretation is left to the vet.
  2. MEASURED vs INFERRED are separated — YOLO/DSP numbers are labelled
     "measured"; distress scores and instrument items are labelled
     "AI-estimated from video/images".
  3. TRANSPARENT MATH — baseline, deviation, and slope formulas are stated in
     the methodology section so nothing is a black box.
  4. FULL PROVENANCE — every observation lists the pipeline/prompt/model
     versions that produced it.

Returned as structured JSON plus a rendered Markdown document (the frontend
can print/export to PDF).
"""

from datetime import datetime, timezone

from . import pet_store

DISCLAIMER = (
    "This is an AI-assisted observational summary generated from "
    "guardian-submitted videos and images. It is NOT a diagnosis and NOT a "
    "substitute for clinical examination. Scores are screening aids: the "
    "distress score is an unvalidated AI estimate; instrument scores follow "
    "published item definitions but were scored by an AI system, not a "
    "trained observer. Media quality, camera angle, and context affect all "
    "values. Intended to support, not replace, veterinary judgement."
)


def _age_string(birthdate: str):
    if not birthdate:
        return None
    try:
        bd = datetime.fromisoformat(birthdate)
        if bd.tzinfo is None:
            bd = bd.replace(tzinfo=timezone.utc)
        days = (datetime.now(timezone.utc) - bd).days
        years, rem_days = divmod(days, 365)
        months = rem_days // 30
        return f"{years}y {months}m"
    except ValueError:
        return None


def _fmt(v, suffix=""):
    return f"{v}{suffix}" if v is not None else "—"


def _aggregate_markers(full_results: list) -> list:
    """Count recurring behavioural markers/FACS codes across all records."""
    counts: dict = {}
    for created_at, result in full_results:
        seen_this_record = set()
        for m in result.get("behavioral_markers", []) or []:
            key = (m.get("code") or m.get("marker") or "").strip()
            if not key or key in seen_this_record:
                continue
            seen_this_record.add(key)
            entry = counts.setdefault(key, {
                "marker": m.get("marker", key),
                "code": m.get("code"),
                "records": 0,
                "first_seen": created_at,
                "last_seen": created_at,
                "zones": set(),
            })
            entry["records"] += 1
            entry["last_seen"] = created_at
            if m.get("zone"):
                entry["zones"].add(m["zone"])
    out = []
    for e in counts.values():
        e["zones"] = sorted(e["zones"])
        out.append(e)
    out.sort(key=lambda e: e["records"], reverse=True)
    return out


def build_report(pet_id: str, reason_for_visit: str = None) -> dict:
    """Assemble the structured report. Returns None if the pet is unknown."""
    pet = pet_store.get_pet(pet_id)
    if not pet:
        return None

    history = pet_store.get_history(pet_id)
    trends = pet_store.compute_trends(pet_id)
    full_results = pet_store.get_full_results(pet_id)
    markers = _aggregate_markers(full_results)

    versions = sorted({
        (h.get("pipeline_version"), h.get("prompt_version"), h.get("model_used"))
        for h in history
    })

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reason_for_visit": reason_for_visit,
        "signalment": {
            "name": pet["name"],
            "species": pet.get("species"),
            "breed": pet.get("breed"),
            "sex": pet.get("sex"),
            "birthdate": pet.get("birthdate"),
            "age": _age_string(pet.get("birthdate")),
            "weight_kg": pet.get("weight_kg"),
            "guardian_notes": pet.get("notes"),
        },
        "period": {
            "first_observation": history[0]["created_at"] if history else None,
            "last_observation": history[-1]["created_at"] if history else None,
            "observation_count": len(history),
        },
        "trends": trends,
        "observations": history,
        "recurring_markers": markers,
        "system_versions": [
            {"pipeline": p, "prompt": pr, "model": m} for (p, pr, m) in versions
        ],
        "methodology": {
            "measured_metrics": (
                "Spinal curvature and head tilt are computed by YOLO11 pose "
                "estimation (human COCO-17 keypoints applied to animals — "
                "approximate, trend-useful). Pitch (F0), tonality (spectral "
                "flatness) and 220-520 Hz purr-band energy are computed by "
                "signal processing from the audio track."
            ),
            "ai_estimated_metrics": (
                "Distress score (0-100, unvalidated screening estimate), zone, "
                "behavioural markers, and instrument item scores are produced "
                "by a multimodal AI (Gemini) constrained by a two-pass scene "
                "verification protocol and the measured metrics above."
            ),
            "instruments": (
                "Cats: Feline Grimace Scale (Evangelista et al., 2019), 5 items "
                "0-2, total /10; published threshold >= 4/10 is reported, not "
                "interpreted. Dogs: an OBSERVABLE SUBSET of Glasgow CMPS-SF "
                "categories scored from video at a distance — explicitly not a "
                "validated administration."
            ),
            "baseline_math": (
                "Baseline = mean +/- SD of all observations except the latest "
                "(minimum 3). Deviation is reported in SD units; |dev| >= 1.5 "
                "SD is flagged. Trend slope = least-squares fit of distress "
                "over time (points/week, minimum 4 observations). Each pet is "
                "compared only against its own history."
            ),
        },
        "disclaimer": DISCLAIMER,
    }
    return report


# ── Markdown rendering ───────────────────────────────────────────────────────

def render_markdown(report: dict) -> str:
    s = report["signalment"]
    p = report["period"]
    t = report["trends"]

    lines = []
    add = lines.append
    add(f"# Pre-Consultation Behaviour Summary — {s['name']}")
    add("")
    add(f"*Generated {report['generated_at']} by Etho (AI-assisted observation log)*")
    add("")
    if report.get("reason_for_visit"):
        add(f"**Reason for visit (guardian-stated):** {report['reason_for_visit']}")
        add("")

    add("## Signalment")
    add("")
    add(f"| | |")
    add(f"|---|---|")
    add(f"| Species | {_fmt(s['species'])} |")
    add(f"| Breed | {_fmt(s['breed'])} |")
    add(f"| Sex | {_fmt(s['sex'])} |")
    add(f"| Age | {_fmt(s['age'])} (DOB {_fmt(s['birthdate'])}) |")
    add(f"| Weight | {_fmt(s['weight_kg'], ' kg')} |")
    if s.get("guardian_notes"):
        add(f"| Guardian notes | {s['guardian_notes']} |")
    add("")

    add("## Observation Period")
    add("")
    add(f"{p['observation_count']} AI-analysed observation(s) from "
        f"{_fmt(p['first_observation'])} to {_fmt(p['last_observation'])}.")
    add("")

    add("## Trend Summary")
    add("")
    if t.get("baseline"):
        b = t["baseline"]
        flag = " **[FLAG: deviation >= 1.5 SD]**" if b["flag"] else ""
        add(f"- **Baseline distress** (n={b['n']}): {b['mean']} +/- {b['std']} "
            f"(AI-estimated, 0-100). Latest deviation: "
            f"{b['latest_deviation_sigma']} SD{flag}")
    else:
        add("- Baseline: not yet established (needs >= 3 observations).")
    if t.get("slope"):
        sl = t["slope"]
        add(f"- **Trend**: {sl['direction']} — {sl['points_per_week']:+.2f} "
            f"points/week over {sl['span_weeks']} weeks (n={sl['n']}).")
    else:
        add("- Trend slope: not yet computable (needs >= 4 observations).")
    add("")

    if t.get("red_flags"):
        add("## Flagged Events")
        add("")
        for f in t["red_flags"]:
            add(f"- `{f['created_at']}` — **{f['type']}**: {f['detail']}")
        add("")

    add("## Observation Log")
    add("")
    add("AI-estimated columns: Distress, Zone, Instrument. "
        "Measured columns: Spine, Vocal events, Pitch.")
    add("")
    add("| Date (UTC) | Media | Distress | Zone | Instrument | Spine mean | "
        "Vocal events | Pitch mean | State |")
    add("|---|---|---|---|---|---|---|---|---|")
    for h in report["observations"]:
        instrument = (f"{h['instrument_total']}/{int(h['instrument_max'])}"
                      if h.get("instrument_total") is not None
                      and h.get("instrument_max") else "—")
        add(f"| {h['created_at']} | {_fmt(h['media_type'])} "
            f"| {_fmt(h['distress_score'])} | {_fmt(h['zone'])} "
            f"| {instrument} | {_fmt(h['spinal_mean_deg'], '°')} "
            f"| {_fmt(h['vocal_event_count'])} | {_fmt(h['pitch_mean_hz'], ' Hz')} "
            f"| {_fmt(h['primary_state'])} |")
    add("")

    if report["recurring_markers"]:
        add("## Recurring Behavioural Markers")
        add("")
        add("| Marker | Code | Seen in # records | First | Last | Zones |")
        add("|---|---|---|---|---|---|")
        for m in report["recurring_markers"][:15]:
            add(f"| {m['marker']} | {_fmt(m['code'])} | {m['records']} "
                f"| {m['first_seen'][:10]} | {m['last_seen'][:10]} "
                f"| {', '.join(m['zones']) or '—'} |")
        add("")

    add("## Methodology & Limitations")
    add("")
    meth = report["methodology"]
    add(f"- **Measured metrics:** {meth['measured_metrics']}")
    add(f"- **AI-estimated metrics:** {meth['ai_estimated_metrics']}")
    add(f"- **Instruments:** {meth['instruments']}")
    add(f"- **Baseline math:** {meth['baseline_math']}")
    add("- **System versions used:** " + "; ".join(
        f"pipeline {v['pipeline'] or '?'} / prompt {v['prompt'] or '?'} / "
        f"model {v['model'] or '?'}" for v in report["system_versions"]) + ".")
    add("")

    add("---")
    add("")
    add(f"> {report['disclaimer']}")
    add("")
    return "\n".join(lines)
