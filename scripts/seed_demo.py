"""
Seed the longitudinal store with realistic demo data.

Creates two demo pets with weeks of analysis history, weight logs, and
capture contexts so the timeline feed, trends, baselines, red flags, and
vet report all have something real to show — no Gemini key, YOLO weights,
or media files required. This exercises the exact same code paths as real
uploads (pet_store.log_analysis), so what you see is what production
produces.

  Miso  (cat, Siamese)  — a worsening arc: distress and Feline Grimace
        Scale climb over 9 weeks, weight declines, ends with an incident.
        Trips every red-flag rule: baseline deviation, worsening slope,
        FGS >= 4/10, red zone, elevated urgency.
  Bruno (dog, Labrador) — a healthy control: stable distress, weight in
        range, no flags. Shows what "nothing to worry about" looks like.

Usage:
    PYTHONPATH=. python scripts/seed_demo.py          # uses $DATA_DIR or ./data
    DATA_DIR=/data PYTHONPATH=. python scripts/seed_demo.py

Then try:
    GET /api/pets
    GET /api/pets/{id}/timeline
    GET /api/pets/{id}/trends
    GET /api/pets/{id}/vet-report?format=markdown&reason=demo
"""

import sys
from datetime import datetime, timedelta, timezone

from app.services import pet_store


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _analysis(species, breed, distress, state, fgs_total, curve, markers,
              spinal_mean, vocal_events, pitch_hz, media_kind="video",
              quality="good", urgency="routine"):
    """A result dict shaped exactly like the real pipeline output."""
    zone = "green" if distress <= 33 else ("yellow" if distress <= 66 else "red")
    instrument = ("feline_grimace_scale" if species == "cat"
                  else "canine_observable_stress_subset")
    r = {
        "species": species,
        "breed_detected": breed,
        "overall_assessment": {
            "distress_score": distress, "zone": zone,
            "confidence": "high", "primary_state": state,
            "summary": f"Demo observation — {state}.",
        },
        "advisory": {"urgency": urgency, "headline": "Demo advisory"},
        "instrument_scores": {
            "instrument": instrument, "total": fgs_total, "max_total": 10,
            "items_scorable": 5,
        },
        "timeline": [
            {"timestamp": f"0:{t:02d}", "distress_score": s,
             "zone": "green" if s <= 33 else ("yellow" if s <= 66 else "red"),
             "event_type": "behavioral", "event_description": "demo event"}
            for t, s in curve
        ],
        "behavioral_markers": [
            {"marker": m, "code": c, "zone": zone, "verified": True}
            for m, c in markers
        ],
        "capture_quality": {"grade": quality, "checks": [], "advice": []},
        "_media_kind": media_kind,
        "_analysis_version": "etho-v17-longitudinal",
        "_prompt_version": "6.1",
        "_model_used": "demo-seed",
    }
    if media_kind == "video":
        r["_pose_metrics"] = {
            "detection_coverage": 0.9,
            "spinal_curvature": {"mean_deg": spinal_mean,
                                 "max_deg": round(spinal_mean * 1.6, 1),
                                 "interpretation": "demo"},
        }
        r["_audio_metrics"] = {
            "audio_present": True,
            "vocalization_event_count": vocal_events,
            "pitch": {"mean_hz": pitch_hz, "min_hz": pitch_hz - 80,
                      "max_hz": pitch_hz + 120},
            "tonality": {"mean_flatness": 0.4, "interpretation": "mixed"},
            "solicitation_purr": {"possible": False, "peak_purr_band_ratio": 0.1},
        }
    return r


def _log_at(when, pet_id, result, media_type, context, filename):
    """Log an analysis with a controlled timestamp."""
    real = pet_store._utcnow
    pet_store._utcnow = lambda: _iso(when)
    try:
        return pet_store.log_analysis(pet_id, result, media_type=media_type,
                                      source_filename=filename, context=context)
    finally:
        pet_store._utcnow = real


def seed():
    pet_store.init_db()

    existing = [p["name"] for p in pet_store.list_pets()]
    if "Miso (demo)" in existing or "Bruno (demo)" in existing:
        print("Demo pets already exist — nothing seeded.")
        print("Delete $DATA_DIR/etho.db (or use a fresh DATA_DIR) to reseed.")
        return 1

    now = datetime.now(timezone.utc)

    # ── Miso: worsening cat ─────────────────────────────────────────────
    miso = pet_store.create_pet({
        "name": "Miso (demo)", "species": "cat", "breed": "Siamese",
        "sex": "female", "birthdate": "2019-03-01",
        "notes": "Demo pet — worsening arc. Indoor cat, recent house move.",
    })
    arc = [  # (weeks_ago, distress, state, fgs, spinal, vocal, pitch, context)
        (9, 22, "relaxed",         1, 8.0, 1, 420, "weekly_baseline"),
        (8, 25, "relaxed",         1, 9.0, 2, 430, "weekly_baseline"),
        (7, 24, "alert",           2, 9.5, 1, 425, "weekly_baseline"),
        (6, 28, "alert",           2, 11.0, 3, 450, "weekly_baseline"),
        (5, 30, "alert",           2, 12.0, 3, 455, "weekly_baseline"),
        (4, 35, "tense",           3, 14.5, 4, 480, "weekly_baseline"),
        (3, 42, "tense/withdrawn", 4, 17.0, 5, 510, "weekly_baseline"),
        (2, 50, "withdrawn",       4, 19.5, 6, 540, "weekly_baseline"),
        (1, 58, "distressed",      5, 22.0, 7, 570, "weekly_baseline"),
    ]
    for weeks, d, state, fgs, spine, vocal, pitch, ctx in arc:
        when = now - timedelta(weeks=weeks)
        curve = [(0, max(5, d - 12)), (10, d - 5), (25, d + 8), (45, d)]
        markers = [("Ears flattened/rotated", "EAD103")] if d > 26 else []
        if fgs >= 4:
            markers.append(("Orbital tightening", "AU145"))
        _log_at(when, miso["id"],
                _analysis("cat", "Siamese", d, state, fgs, curve, markers,
                          spine, vocal, pitch),
                "video", ctx, f"miso_week{weeks}.mp4")
    # Final incident, red zone
    _log_at(now - timedelta(days=2), miso["id"],
            _analysis("cat", "Siamese", 72, "acute distress", 6,
                      [(0, 55), (8, 78), (20, 74), (35, 68)],
                      [("Ears flattened/rotated", "EAD103"),
                       ("Orbital tightening", "AU145"),
                       ("Piloerection", None)],
                      26.0, 9, 640, quality="fair", urgency="elevated"),
            "video", "incident", "miso_incident.mp4")
    # Declining weight log
    for weeks, kg in [(9, 4.4), (6, 4.3), (4, 4.1), (2, 4.0), (0, 3.9)]:
        pet_store.add_weight(miso["id"], kg,
                             note="demo", recorded_at=_iso(now - timedelta(weeks=weeks)))

    # ── Bruno: stable dog ───────────────────────────────────────────────
    bruno = pet_store.create_pet({
        "name": "Bruno (demo)", "species": "dog", "breed": "Labrador Retriever",
        "sex": "male", "birthdate": "2021-06-15",
        "notes": "Demo pet — healthy control.",
    })
    for weeks, d, state in [(6, 30, "playful"), (5, 26, "relaxed"),
                            (4, 32, "alert"), (3, 27, "relaxed"),
                            (2, 29, "playful"), (1, 25, "relaxed")]:
        when = now - timedelta(weeks=weeks)
        curve = [(0, d + 6), (12, d - 4), (30, d + 3), (50, d - 2)]
        _log_at(when, bruno["id"],
                _analysis("dog", "Labrador Retriever", d, state, 1, curve,
                          [("Loose tail wag", None)], 7.5, 4, 320),
                "video", "weekly_baseline", f"bruno_week{weeks}.mp4")
    for weeks, kg in [(6, 28.5), (3, 28.8), (0, 29.0)]:
        pet_store.add_weight(bruno["id"], kg,
                             note="demo", recorded_at=_iso(now - timedelta(weeks=weeks)))

    print("Seeded demo data into", pet_store.DATA_DIR)
    print(f"  Miso  (worsening cat):  {miso['id']}")
    print(f"  Bruno (healthy dog):    {bruno['id']}")
    print("\nTry:")
    print(f"  curl localhost:8000/api/pets")
    print(f"  curl localhost:8000/api/pets/{miso['id']}/timeline")
    print(f"  curl localhost:8000/api/pets/{miso['id']}/trends")
    print(f"  curl 'localhost:8000/api/pets/{miso['id']}/vet-report?format=markdown&reason=demo'")
    return 0


if __name__ == "__main__":
    sys.exit(seed())
