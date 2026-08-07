"""
Persistent pet-profile and analysis-history store.

This is the longitudinal layer that turns Etho from a one-shot analyzer into
a record pet parents build over time. SQLite via the stdlib — no new
dependencies, trivially portable to Postgres later.

Design principles for scientific validity:
  - Every analysis row stores the COMPLETE raw result JSON (provenance) plus
    extracted, indexed metric columns for trend queries.
  - Every row is stamped with pipeline_version, prompt_version, and model IDs
    so longitudinal comparisons can account for system changes.
  - Objective measurements (YOLO pose, DSP acoustics) and AI-inferred values
    (distress score, instrument items) are stored distinctly and never mixed.
  - Timestamps are UTC ISO-8601.

Storage location: $DATA_DIR/etho.db (default ./data). On Railway the container
filesystem is ephemeral across deploys — mount a volume (e.g. at /data) and
set DATA_DIR=/data for real persistence.
"""

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

DATA_DIR = os.environ.get("DATA_DIR", "data")

_lock = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pets (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    species     TEXT,
    breed       TEXT,
    sex         TEXT,
    birthdate   TEXT,
    weight_kg   REAL,
    notes       TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analyses (
    id                  TEXT PRIMARY KEY,
    pet_id              TEXT,
    created_at          TEXT NOT NULL,
    media_type          TEXT,               -- 'video' | 'image'
    source_filename     TEXT,
    file_size_bytes     INTEGER,

    -- AI-inferred (Gemini)
    distress_score      INTEGER,
    zone                TEXT,
    confidence          TEXT,
    primary_state       TEXT,
    species_detected    TEXT,
    breed_detected      TEXT,
    urgency             TEXT,
    instrument          TEXT,
    instrument_total    REAL,
    instrument_max      REAL,
    instrument_scorable INTEGER,

    -- Objectively measured (YOLO pose)
    spinal_mean_deg     REAL,
    spinal_max_deg      REAL,
    detection_coverage  REAL,

    -- Objectively measured (audio DSP)
    vocal_event_count   INTEGER,
    pitch_mean_hz       REAL,
    purr_possible       INTEGER,

    -- Provenance
    pipeline_version    TEXT,
    prompt_version      TEXT,
    model_used          TEXT,
    full_json           TEXT NOT NULL,

    FOREIGN KEY (pet_id) REFERENCES pets (id)
);

CREATE INDEX IF NOT EXISTS idx_analyses_pet_time
    ON analyses (pet_id, created_at);
"""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(os.path.join(DATA_DIR, "etho.db"))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _lock, _connect() as conn:
        conn.executescript(_SCHEMA)


# ── Pets ─────────────────────────────────────────────────────────────────────

_PET_FIELDS = ("name", "species", "breed", "sex", "birthdate", "weight_kg", "notes")


def create_pet(data: dict) -> dict:
    pet_id = str(uuid.uuid4())
    now = _utcnow()
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO pets (id, name, species, breed, sex, birthdate, weight_kg, "
            "notes, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (pet_id, data.get("name", "Unnamed"), data.get("species"),
             data.get("breed"), data.get("sex"), data.get("birthdate"),
             data.get("weight_kg"), data.get("notes"), now, now),
        )
    return get_pet(pet_id)


def update_pet(pet_id: str, data: dict) -> dict:
    sets, vals = [], []
    for f in _PET_FIELDS:
        if f in data:
            sets.append(f"{f} = ?")
            vals.append(data[f])
    if sets:
        sets.append("updated_at = ?")
        vals.append(_utcnow())
        vals.append(pet_id)
        with _lock, _connect() as conn:
            conn.execute(f"UPDATE pets SET {', '.join(sets)} WHERE id = ?", vals)
    return get_pet(pet_id)


def get_pet(pet_id: str):
    with _lock, _connect() as conn:
        row = conn.execute("SELECT * FROM pets WHERE id = ?", (pet_id,)).fetchone()
    return dict(row) if row else None


def list_pets() -> list:
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT p.*, COUNT(a.id) AS analysis_count, MAX(a.created_at) AS last_analysis_at "
            "FROM pets p LEFT JOIN analyses a ON a.pet_id = p.id "
            "GROUP BY p.id ORDER BY p.created_at"
        ).fetchall()
    return [dict(r) for r in rows]


# ── Analyses ─────────────────────────────────────────────────────────────────

def log_analysis(pet_id, result: dict, media_type: str,
                 source_filename: str = None, file_size_bytes: int = None) -> str:
    """Extract indexed metrics from a pipeline result and persist the full
    record. Returns the new analysis id. pet_id may be None (unassigned)."""
    analysis_id = str(uuid.uuid4())
    oa = result.get("overall_assessment", {}) or {}
    pm = result.get("_pose_metrics", {}) or {}
    am = result.get("_audio_metrics", {}) or {}
    ins = result.get("instrument_scores", {}) or {}
    sc = pm.get("spinal_curvature", {}) or {}
    pitch = am.get("pitch", {}) or {}
    purr = am.get("solicitation_purr", {}) or {}

    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO analyses (id, pet_id, created_at, media_type, source_filename, "
            "file_size_bytes, distress_score, zone, confidence, primary_state, "
            "species_detected, breed_detected, urgency, instrument, instrument_total, "
            "instrument_max, instrument_scorable, spinal_mean_deg, spinal_max_deg, "
            "detection_coverage, vocal_event_count, pitch_mean_hz, purr_possible, "
            "pipeline_version, prompt_version, model_used, full_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                analysis_id, pet_id, _utcnow(), media_type, source_filename,
                file_size_bytes,
                oa.get("distress_score"), oa.get("zone"), oa.get("confidence"),
                oa.get("primary_state"),
                result.get("species"), result.get("breed_detected"),
                (result.get("advisory") or {}).get("urgency"),
                ins.get("instrument"), ins.get("total"), ins.get("max_total"),
                ins.get("items_scorable"),
                sc.get("mean_deg"), sc.get("max_deg"),
                pm.get("detection_coverage"),
                am.get("vocalization_event_count"),
                pitch.get("mean_hz"),
                1 if purr.get("possible") else 0 if am else None,
                result.get("_analysis_version"),
                result.get("_prompt_version"),
                result.get("_model_used"),
                json.dumps(result),
            ),
        )
    return analysis_id


def get_history(pet_id: str, limit: int = 200) -> list:
    """Chronological indexed metrics for a pet (oldest first). Excludes the
    full JSON blob — use get_analysis for a complete record."""
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT id, created_at, media_type, source_filename, distress_score, zone, "
            "confidence, primary_state, species_detected, breed_detected, urgency, "
            "instrument, instrument_total, instrument_max, instrument_scorable, "
            "spinal_mean_deg, spinal_max_deg, detection_coverage, vocal_event_count, "
            "pitch_mean_hz, purr_possible, pipeline_version, prompt_version, model_used "
            "FROM analyses WHERE pet_id = ? ORDER BY created_at LIMIT ?",
            (pet_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_full_results(pet_id: str, limit: int = 200) -> list:
    """(created_at, full result dict) pairs for a pet, oldest first. Used by
    the vet-report builder to aggregate markers/FACS codes across records."""
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT created_at, full_json FROM analyses "
            "WHERE pet_id = ? ORDER BY created_at LIMIT ?",
            (pet_id, limit),
        ).fetchall()
    return [(r["created_at"], json.loads(r["full_json"])) for r in rows]


def get_analysis(analysis_id: str):
    with _lock, _connect() as conn:
        row = conn.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
    if not row:
        return None
    rec = dict(row)
    rec["full_json"] = json.loads(rec["full_json"])
    return rec


# ── Trends & baseline ────────────────────────────────────────────────────────

def compute_trends(pet_id: str) -> dict:
    """Transparent, simple statistics over a pet's history. Each pet serves as
    its own control (intra-subject comparison) — absolute scores across pets
    are not comparable, but deviation from a pet's own baseline is meaningful.

    Baseline = mean/std of all observations EXCLUDING the most recent one, so
    the latest observation can be assessed against it. Requires >= 3 records
    for a baseline, >= 4 for a slope.
    """
    history = get_history(pet_id)
    n = len(history)
    out = {"observation_count": n, "baseline": None, "latest": None, "slope": None}
    if n == 0:
        return out

    latest = history[-1]
    out["latest"] = {
        "created_at": latest["created_at"],
        "distress_score": latest["distress_score"],
        "zone": latest["zone"],
        "instrument_total": latest["instrument_total"],
    }

    scores = [(h["created_at"], h["distress_score"]) for h in history
              if h["distress_score"] is not None]
    if len(scores) >= 3:
        prior = [s for _, s in scores[:-1]]
        mean = sum(prior) / len(prior)
        var = sum((s - mean) ** 2 for s in prior) / len(prior)
        std = var ** 0.5
        latest_score = scores[-1][1]
        deviation_sigma = round((latest_score - mean) / std, 2) if std > 0 else 0.0
        out["baseline"] = {
            "mean": round(mean, 1),
            "std": round(std, 1),
            "n": len(prior),
            "latest_deviation_sigma": deviation_sigma,
            "flag": abs(deviation_sigma) >= 1.5 and std > 0,
        }

    if len(scores) >= 4:
        # Least-squares slope of distress over time, in points per week.
        t0 = datetime.fromisoformat(scores[0][0])
        xs = [(datetime.fromisoformat(ts) - t0).total_seconds() / 604800.0
              for ts, _ in scores]
        ys = [s for _, s in scores]
        nx = len(xs)
        mx, my = sum(xs) / nx, sum(ys) / nx
        denom = sum((x - mx) ** 2 for x in xs)
        if denom > 0:
            slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom
            out["slope"] = {
                "points_per_week": round(slope, 2),
                "direction": ("worsening" if slope > 1.0 else
                              "improving" if slope < -1.0 else "stable"),
                "span_weeks": round(xs[-1], 1),
                "n": nx,
            }

    # Red flags across history
    flags = []
    for h in history:
        if h["zone"] == "red":
            flags.append({"created_at": h["created_at"], "type": "red_zone",
                          "detail": f"Distress {h['distress_score']}"})
        if h["urgency"] in ("elevated", "critical"):
            flags.append({"created_at": h["created_at"], "type": "urgency",
                          "detail": f"Advisory urgency: {h['urgency']}"})
        if (h["instrument"] == "feline_grimace_scale"
                and h["instrument_total"] is not None and h["instrument_total"] >= 4):
            flags.append({"created_at": h["created_at"], "type": "fgs_threshold",
                          "detail": f"FGS {h['instrument_total']}/10 (published "
                                    f"analgesia-consideration threshold is >= 4/10)"})
    out["red_flags"] = flags
    return out
