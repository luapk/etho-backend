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
from .breed_reference import assess_weight

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
    for rec in full_results:
        created_at, result = rec["created_at"], rec["result"]
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

    weights = pet_store.get_weights(pet_id)
    weight_block = {
        "entries": weights,
        "assessment": assess_weight(pet.get("species"), pet.get("breed"),
                                    pet.get("weight_kg")),
    }
    if len(weights) >= 2:
        first, last = weights[0], weights[-1]
        delta = round(last["weight_kg"] - first["weight_kg"], 2)
        pct = round(delta / first["weight_kg"] * 100, 1) if first["weight_kg"] else None
        weight_block["change"] = {
            "from_kg": first["weight_kg"], "to_kg": last["weight_kg"],
            "delta_kg": delta, "delta_percent": pct,
            "from_date": first["recorded_at"], "to_date": last["recorded_at"],
        }

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
        "respiratory": {
            "entries": [
                {"created_at": h["created_at"],
                 "breaths_per_min": h["resp_rate_bpm"],
                 "confidence": h.get("resp_confidence")}
                for h in history if h.get("resp_rate_bpm") is not None
            ],
            "threshold_note": ("Published sleeping-RR screening threshold: "
                               "> 30/min sustained. Measured ONLY from clips "
                               "the guardian tagged as sleeping."),
        },
        "weight": weight_block,
        "observations": history,
        "recurring_markers": markers,
        "system_versions": [
            {"pipeline": p, "prompt": pr, "model": m} for (p, pr, m) in versions
        ],
        "methodology": {
            "measured_metrics": (
                "Pet detection and framing are computed by a YOLO11 detector. "
                "Pitch (F0), tonality (spectral flatness) and 220-520 Hz "
                "purr-band energy are computed by signal processing from the "
                "audio track. Activity level, movement rhythm, tremor "
                "(4-12 Hz) and postural sway are derived from frame-to-frame "
                "motion. Skeletal pose estimation is NOT performed: the "
                "available keypoint models are human-trained and fit human "
                "anatomy to animals, so spinal-curvature and head-tilt "
                "figures are deliberately not reported. Gait, stride and "
                "weight-bearing symmetry are not measured at all — force "
                "plates and pressure walkways remain the clinical standard."
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
            "respiratory": (
                "Sleeping respiratory rate is measured by signal processing "
                "(chest-motion displacement, spectral analysis) ONLY from "
                "clips the guardian explicitly tagged as showing the pet "
                "asleep; clips with too much movement are rejected rather "
                "than reported. The > 30/min screening threshold is from "
                "veterinary cardiology home-monitoring literature and is "
                "reported, not interpreted."
            ),
            "weight_screening": (
                "Weight is compared against typical adult breed ranges "
                "(sexes combined) as a rough screen only. Body condition "
                "score (BCS) assessed hands-on remains the clinical standard."
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
        # Reported as a measured gradient, not as a prognosis: whether a
        # +2 pts/week drift inside the calm band means anything clinically is
        # the clinician's call, so the row states the number, the span, and
        # whether it exceeds this animal's own variability.
        exceeds = ("exceeds this pet's own SD" if sl.get("exceeds_variation")
                   else "within this pet's own SD — not distinguishable from "
                        "normal variation")
        add(f"- **Trend**: {sl['direction']} — {sl['points_per_week']:+.2f} "
            f"points/week over {sl['span_weeks']} weeks (n={sl['n']}); "
            f"total change {sl['total_change']:+.1f} points, {exceeds}.")
    else:
        add("- Trend slope: not yet computable (needs >= 4 observations).")
    add("")

    if t.get("red_flags"):
        add("## Flagged Events")
        add("")
        for f in t["red_flags"]:
            add(f"- `{f['created_at']}` — **{f['type']}**: {f['detail']}")
        add("")

    wb = report.get("weight", {})
    wa = wb.get("assessment", {})
    if wb.get("entries") or wa.get("status") not in (None, "no_weight_recorded"):
        add("## Weight")
        add("")
        if wa.get("reference_range_kg"):
            lo, hi = wa["reference_range_kg"]
            status = wa["status"].replace("_", " ")
            outside = (f" ({wa['percent_outside_range']}% outside)"
                       if wa.get("percent_outside_range") else "")
            add(f"- **Latest**: {wa['weight_kg']} kg — **{status}**{outside} "
                f"vs typical adult range {lo}-{hi} kg "
                f"({wa.get('matched_breed') or wa.get('reference_source')}).")
        elif wa.get("status") == "no_reference":
            add(f"- **Latest**: {wa.get('weight_kg')} kg — no breed reference "
                f"range available.")
        if wb.get("change"):
            c = wb["change"]
            add(f"- **Change**: {c['delta_kg']:+} kg ({c['delta_percent']:+}%) "
                f"from {c['from_date'][:10]} to {c['to_date'][:10]}.")
        if wb.get("entries"):
            add("")
            add("| Date | Weight (kg) | Note |")
            add("|---|---|---|")
            for w in wb["entries"]:
                add(f"| {w['recorded_at'][:10]} | {w['weight_kg']} | {w.get('note') or '—'} |")
        add("")
        add(f"> {wa.get('note', '')}")
        add("")

    resp = report.get("respiratory", {})
    if resp.get("entries"):
        add("## Sleeping Respiratory Rate (measured)")
        add("")
        add("Measured only from guardian-tagged SLEEPING clips; awake or "
            "moving clips are rejected, not reported.")
        add("")
        add("| Date | Breaths/min | Confidence |")
        add("|---|---|---|")
        for e in resp["entries"]:
            flag = " **[> 30/min]**" if e["breaths_per_min"] and e["breaths_per_min"] > 30 else ""
            add(f"| {e['created_at'][:10]} | {e['breaths_per_min']}{flag} "
                f"| {e.get('confidence') or '—'} |")
        add("")
        add(f"> {resp['threshold_note']}")
        add("")

    add("## Observation Log")
    add("")
    show_spine = any(h.get("spinal_mean_deg") is not None
                     for h in report["observations"])
    measured_cols = ("Spine, " if show_spine else "") + "Vocal events, Pitch"
    add(f"AI-estimated columns: Distress, Zone, Instrument. "
        f"Measured columns: {measured_cols}. Quality is the technical capture "
        f"grade — weigh fair/poor observations accordingly.")
    add("")
    spine_h = "Spine mean | " if show_spine else ""
    spine_sep = "---|" if show_spine else ""
    add(f"| Date (UTC) | Media | Quality | Distress | Zone | Instrument | {spine_h}"
        f"Vocal events | Pitch mean | State |")
    add(f"|---|---|---|---|---|---|{spine_sep}---|---|---|")
    for h in report["observations"]:
        instrument = (f"{h['instrument_total']}/{int(h['instrument_max'])}"
                      if h.get("instrument_total") is not None
                      and h.get("instrument_max") else "—")
        media = h.get("media_type") or "—"
        if h.get("context"):
            media = f"{media} ({h['context']})"
        spine_c = f"{_fmt(h['spinal_mean_deg'], '°')} | " if show_spine else ""
        add(f"| {h['created_at']} | {media} | {_fmt(h.get('quality_grade'))} "
            f"| {_fmt(h['distress_score'])} | {_fmt(h['zone'])} "
            f"| {instrument} | {spine_c}"
            f"{_fmt(h['vocal_event_count'])} | {_fmt(h['pitch_mean_hz'], ' Hz')} "
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
    add(f"- **Respiratory rate:** {meth['respiratory']}")
    add(f"- **Weight screening:** {meth['weight_screening']}")
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
