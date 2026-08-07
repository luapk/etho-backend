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

import hashlib
import json
import os
import secrets
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

def _resolve_data_dir() -> str:
    """Where the longitudinal database lives.

    Order: explicit DATA_DIR wins; otherwise use Railway's mounted volume if
    one is attached (RAILWAY_VOLUME_MOUNT_PATH is set by the platform); else
    fall back to ./data, which on a container filesystem is WIPED ON EVERY
    REDEPLOY. Auto-detecting the volume means mounting one in Railway is
    sufficient — no matching env var to remember.
    """
    explicit = os.environ.get("DATA_DIR")
    if explicit:
        return explicit
    volume = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
    if volume:
        return volume
    return "data"


DATA_DIR = _resolve_data_dir()

_lock = threading.Lock()


def storage_status() -> dict:
    """Plain-English description of whether records will survive a redeploy.
    Used by startup logging and /health so misconfiguration is visible
    rather than discovered when data disappears."""
    explicit = bool(os.environ.get("DATA_DIR"))
    volume = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
    on_railway = bool(os.environ.get("RAILWAY_ENVIRONMENT")
                      or os.environ.get("RAILWAY_PROJECT_ID") or volume)

    if volume and not explicit:
        source = "railway_volume_autodetected"
    elif explicit:
        source = "DATA_DIR"
    else:
        source = "default"

    # A path under a mounted volume persists; anything else on Railway does not.
    persistent = bool(volume) or (explicit and not on_railway)

    writable = False
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        probe = os.path.join(DATA_DIR, ".write_probe")
        with open(probe, "w") as fh:
            fh.write("ok")
        os.unlink(probe)
        writable = True
    except OSError:
        pass

    if not writable:
        message = f"Cannot write to {DATA_DIR} — pet records cannot be saved."
    elif persistent:
        message = f"Records are saved to {DATA_DIR} and survive redeploys."
    elif on_railway:
        message = (f"Records are saved to {DATA_DIR}, which is WIPED ON EVERY "
                   f"REDEPLOY. Mount a volume in Railway to keep pet history.")
    else:
        message = f"Records are saved to {DATA_DIR} (local directory)."

    return {
        "data_dir": DATA_DIR,
        "source": source,
        "persistent": persistent,
        "writable": writable,
        "on_railway": on_railway,
        "message": message,
    }

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

CREATE TABLE IF NOT EXISTS owners (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    email        TEXT,
    api_key_hash TEXT NOT NULL UNIQUE,   -- SHA-256 of the raw key; raw is never stored
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS weights (
    id          TEXT PRIMARY KEY,
    pet_id      TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    weight_kg   REAL NOT NULL,
    note        TEXT,
    FOREIGN KEY (pet_id) REFERENCES pets (id)
);

CREATE INDEX IF NOT EXISTS idx_weights_pet_time
    ON weights (pet_id, recorded_at);
"""

# Columns added after the original v17 schema — applied idempotently on
# startup so existing databases migrate in place.
_MIGRATIONS = [
    ("pets", "owner_id", "TEXT"),
    ("analyses", "owner_id", "TEXT"),
    ("analyses", "context", "TEXT"),        # capture context tag, e.g. weekly_baseline
    ("analyses", "quality_grade", "TEXT"),  # good|fair|poor — so trend views can
                                            # de-emphasise low-quality observations
    ("analyses", "resp_rate_bpm", "REAL"),      # measured sleeping respiratory rate
    ("analyses", "resp_confidence", "TEXT"),    # high|medium — only usable rates stored
    # created_at holds WHEN THE BEHAVIOUR HAPPENED (capture time when known),
    # because every trend and baseline is ordered by observation date.
    # uploaded_at records when it reached us; capture_time_source says how
    # the date is known (exif|video_metadata|filename|unknown).
    ("analyses", "uploaded_at", "TEXT"),
    ("analyses", "capture_time_source", "TEXT"),
    ("analyses", "activity_level", "REAL"),     # measured motion energy
    ("analyses", "tremor_detected", "INTEGER"),
    ("analyses", "cough_like_count", "INTEGER"),
]


def _ensure_column(conn, table: str, col: str, decl: str):
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    if col not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


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
        for table, col, decl in _MIGRATIONS:
            _ensure_column(conn, table, col, decl)


# ── Owners (per-guardian API keys) ───────────────────────────────────────────

def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def create_owner(name: str, email: str = None) -> tuple:
    """Create an owner and mint their API key. Returns (owner, raw_key).
    The raw key is returned exactly once — only its hash is stored."""
    raw_key = "etho_" + secrets.token_urlsafe(32)
    owner_id = str(uuid.uuid4())
    now = _utcnow()
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO owners (id, name, email, api_key_hash, created_at) "
            "VALUES (?,?,?,?,?)",
            (owner_id, name, email, _hash_key(raw_key), now),
        )
    owner = {"id": owner_id, "name": name, "email": email, "created_at": now}
    return owner, raw_key


def get_owner_by_key(raw_key: str):
    """Resolve a raw API key to its owner (constant work: one hash + lookup)."""
    if not raw_key:
        return None
    with _lock, _connect() as conn:
        row = conn.execute(
            "SELECT id, name, email, created_at FROM owners WHERE api_key_hash = ?",
            (_hash_key(raw_key),),
        ).fetchone()
    return dict(row) if row else None


def list_owners() -> list:
    """Owner roster with pet counts. Never exposes key hashes."""
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT o.id, o.name, o.email, o.created_at, COUNT(p.id) AS pet_count "
            "FROM owners o LEFT JOIN pets p ON p.owner_id = o.id "
            "GROUP BY o.id ORDER BY o.created_at"
        ).fetchall()
    return [dict(r) for r in rows]


# ── Pets ─────────────────────────────────────────────────────────────────────

_PET_FIELDS = ("name", "species", "breed", "sex", "birthdate", "weight_kg", "notes")


def create_pet(data: dict, owner_id: str = None) -> dict:
    pet_id = str(uuid.uuid4())
    now = _utcnow()
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO pets (id, name, species, breed, sex, birthdate, weight_kg, "
            "notes, created_at, updated_at, owner_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (pet_id, data.get("name", "Unnamed"), data.get("species"),
             data.get("breed"), data.get("sex"), data.get("birthdate"),
             data.get("weight_kg"), data.get("notes"), now, now, owner_id),
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


def list_pets(owner_id: str = None) -> list:
    """All pets (admin) or only one owner's pets when owner_id is given."""
    where = "WHERE p.owner_id = ?" if owner_id else ""
    params = (owner_id,) if owner_id else ()
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT p.*, COUNT(a.id) AS analysis_count, MAX(a.created_at) AS last_analysis_at "
            f"FROM pets p LEFT JOIN analyses a ON a.pet_id = p.id {where} "
            "GROUP BY p.id ORDER BY p.created_at",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


# ── Analyses ─────────────────────────────────────────────────────────────────

def log_analysis(pet_id, result: dict, media_type: str,
                 source_filename: str = None, file_size_bytes: int = None,
                 owner_id: str = None, context: str = None,
                 observed_at: str = None,
                 capture_time_source: str = None) -> str:
    """Extract indexed metrics from a pipeline result and persist the full
    record. Returns the new analysis id. pet_id may be None (unassigned).
    context is the guardian-declared capture context (e.g. weekly_baseline)."""
    analysis_id = str(uuid.uuid4())
    now = _utcnow()
    # The record's date is when the media was CAPTURED when we can tell —
    # otherwise a bulk backlog import would stack months of history onto
    # a single day and destroy the longitudinal record.
    created_at = observed_at or now
    oa = result.get("overall_assessment", {}) or {}
    pm = result.get("_pose_metrics", {}) or {}
    am = result.get("_audio_metrics", {}) or {}
    ins = result.get("instrument_scores", {}) or {}
    cq = result.get("capture_quality", {}) or {}
    resp = result.get("_respiration", {}) or {}
    hs = result.get("_health_signals", {}) or {}
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
            "pipeline_version, prompt_version, model_used, full_json, owner_id, context, "
            "quality_grade, resp_rate_bpm, resp_confidence, uploaded_at, "
            "capture_time_source, activity_level, tremor_detected, cough_like_count) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                analysis_id, pet_id, created_at, media_type, source_filename,
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
                owner_id,
                context,
                cq.get("grade"),
                resp.get("breaths_per_min") if resp.get("usable") else None,
                resp.get("confidence") if resp.get("usable") else None,
                now,
                capture_time_source,
                (hs.get("activity_level") or {}).get("value"),
                1 if (hs.get("tremor") or {}).get("detected") else (0 if hs else None),
                (am.get("cough_like_events") or {}).get("count"),
            ),
        )
    return analysis_id


def get_history(pet_id: str, limit: int = 200) -> list:
    """Chronological indexed metrics for a pet (oldest first). Excludes the
    full JSON blob — use get_analysis for a complete record."""
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT id, created_at, uploaded_at, capture_time_source, media_type, context, "
            "quality_grade, resp_rate_bpm, resp_confidence, activity_level, "
            "tremor_detected, cough_like_count, source_filename, distress_score, zone, "
            "confidence, primary_state, species_detected, breed_detected, urgency, "
            "instrument, instrument_total, instrument_max, instrument_scorable, "
            "spinal_mean_deg, spinal_max_deg, detection_coverage, vocal_event_count, "
            "pitch_mean_hz, purr_possible, pipeline_version, prompt_version, model_used "
            "FROM analyses WHERE pet_id = ? ORDER BY created_at LIMIT ?",
            (pet_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_full_results(pet_id: str, limit: int = 200) -> list:
    """Full records for a pet, oldest first: dicts of {id, created_at,
    context, result}. Used by the vet-report builder and the timeline feed."""
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT id, created_at, context, full_json FROM analyses "
            "WHERE pet_id = ? ORDER BY created_at, id LIMIT ?",
            (pet_id, limit),
        ).fetchall()
    return [{"id": r["id"], "created_at": r["created_at"],
             "context": r["context"], "result": json.loads(r["full_json"])}
            for r in rows]


def get_analysis(analysis_id: str):
    with _lock, _connect() as conn:
        row = conn.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
    if not row:
        return None
    rec = dict(row)
    rec["full_json"] = json.loads(rec["full_json"])
    return rec


# ── Weight log ───────────────────────────────────────────────────────────────

def add_weight(pet_id: str, weight_kg: float, note: str = None,
               recorded_at: str = None) -> dict:
    """Append a weight entry and sync the profile's current weight_kg so the
    signalment always shows the latest measurement."""
    entry_id = str(uuid.uuid4())
    when = recorded_at or _utcnow()
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO weights (id, pet_id, recorded_at, weight_kg, note) "
            "VALUES (?,?,?,?,?)",
            (entry_id, pet_id, when, weight_kg, note),
        )
        conn.execute(
            "UPDATE pets SET weight_kg = ?, updated_at = ? WHERE id = ?",
            (weight_kg, _utcnow(), pet_id),
        )
    return {"id": entry_id, "pet_id": pet_id, "recorded_at": when,
            "weight_kg": weight_kg, "note": note}


def get_weights(pet_id: str) -> list:
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT id, recorded_at, weight_kg, note FROM weights "
            "WHERE pet_id = ? ORDER BY recorded_at",
            (pet_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Unified timeline feed ────────────────────────────────────────────────────

def _ts_to_seconds(ts) -> float:
    """Parse '0:05', '1:02:03', or a bare number into seconds."""
    try:
        if isinstance(ts, (int, float)):
            return float(ts)
        parts = [float(p) for p in str(ts).split(":")]
        secs = 0.0
        for p in parts:
            secs = secs * 60 + p
        return secs
    except (ValueError, TypeError):
        return 0.0


def get_timeline_feed(pet_id: str, limit: int = 200) -> list:
    """One chronological feed merging analyses and weight entries, built for
    a scrubbable timeline UI. Each analysis item carries its own per-asset
    distress curve (extracted from the stored `timeline` array) so the
    frontend can render inline sparklines without fetching full records."""
    items = []

    for rec in get_full_results(pet_id, limit=limit):
        result = rec["result"]
        oa = result.get("overall_assessment", {}) or {}
        ins = result.get("instrument_scores", {}) or {}
        cq = result.get("capture_quality", {}) or {}
        curve = []
        for ev in result.get("timeline", []) or []:
            if isinstance(ev, dict) and ev.get("distress_score") is not None:
                curve.append({
                    "t_sec": _ts_to_seconds(ev.get("timestamp", 0)),
                    "distress_score": ev.get("distress_score"),
                    "zone": ev.get("zone"),
                })
        curve.sort(key=lambda p: p["t_sec"])
        items.append({
            "type": "analysis",
            "date": rec["created_at"],
            "analysis_id": rec["id"],
            "media_type": result.get("_media_kind", "video"),
            "context": rec["context"],
            "distress_score": oa.get("distress_score"),
            "zone": oa.get("zone"),
            "primary_state": oa.get("primary_state"),
            "instrument_total": ins.get("total"),
            "instrument_max": ins.get("max_total"),
            "quality_grade": cq.get("grade"),
            "srr_bpm": (result.get("_respiration", {}) or {}).get("breaths_per_min")
                       if (result.get("_respiration", {}) or {}).get("usable") else None,
            "distress_curve": curve,
        })

    for w in get_weights(pet_id):
        items.append({
            "type": "weight",
            "date": w["recorded_at"],
            "weight_kg": w["weight_kg"],
            "note": w["note"],
        })

    items.sort(key=lambda i: i["date"])
    return items


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
        if (h.get("resp_rate_bpm") is not None
                and h["resp_rate_bpm"] > 30):
            flags.append({"created_at": h["created_at"], "type": "srr_threshold",
                          "detail": (f"Sleeping respiratory rate "
                                     f"{h['resp_rate_bpm']}/min measured "
                                     f"({h.get('resp_confidence')} confidence) — "
                                     f"published screening threshold is > 30/min "
                                     f"sustained (reported, not interpreted)")})
    out["red_flags"] = flags
    return out
