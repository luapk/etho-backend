"""
Gemini model discovery and selection.

Two jobs, deliberately separated:

  1. RANKING (pure, testable, no network): given a list of model ids, decide
     which best fits this pipeline's needs — a stable, current, multimodal
     model that can ingest video with audio.
  2. RESOLUTION (network): ask the Gemini API what this key can actually
     reach, then apply the ranking.

Why the default is pinned, not automatic
----------------------------------------
Every stored analysis is compared against the same pet's own history. If the
model silently changes between observations, a shift in distress score could
be the pet or could be the model — and you cannot tell which. So
`GEMINI_MODEL` defaults to an explicit pinned id, and upgrading is a
deliberate act (run scripts/check_models.py, then set the env var, then
re-run the repeatability study).

`GEMINI_MODEL=auto` is supported for convenience: it resolves ONCE at module
load (never per-request), logs loudly what it picked, and falls back to the
pinned default if discovery fails for any reason. Records are stamped with
the resolved id either way, so the history stays interpretable.
"""

import re

# The pinned fallback: used when GEMINI_MODEL is unset, and when auto
# resolution cannot reach the API.
STABLE_DEFAULT = "gemini-2.5-flash"

# Model families that cannot serve this pipeline (no video+audio understanding
# via generateContent), matched as substrings of the model id.
_EXCLUDE_SUBSTRINGS = (
    "embedding", "aqa", "imagen", "veo", "gemma", "learnlm",
    "tts", "image-generation", "native-audio", "computer-use", "robotics",
)

_VERSION_RE = re.compile(r"gemini-(\d+)(?:\.(\d+))?")
# Trailing date/build snapshots: -05-20, -0827, -001
_DATED_RE = re.compile(r"-\d{2}-\d{2}$|-\d{3,4}$")
_PREVIEW_MARKERS = ("preview", "exp", "experimental", "thinking")

_TIER_ORDER = {"pro": 3, "flash": 2, "flash-lite": 1, "other": 0}


def strip_prefix(model_id: str) -> str:
    """'models/gemini-2.5-flash' -> 'gemini-2.5-flash'."""
    return model_id.split("/", 1)[-1] if "/" in model_id else model_id


def parse_model(model_id: str) -> dict:
    """Structural metadata for a model id. Pure string work, no network."""
    mid = strip_prefix(model_id)
    m = _VERSION_RE.search(mid)
    if m:
        version = (int(m.group(1)), int(m.group(2) or 0))
    else:
        version = (0, 0)

    if "flash-lite" in mid:
        tier = "flash-lite"
    elif "flash" in mid:
        tier = "flash"
    elif "pro" in mid:
        tier = "pro"
    else:
        tier = "other"

    return {
        "id": mid,
        "version": version,
        "tier": tier,
        "preview": any(k in mid for k in _PREVIEW_MARKERS),
        "dated": bool(_DATED_RE.search(mid)),
        "usable": is_usable(mid),
    }


def is_usable(model_id: str) -> bool:
    """True if the id looks like a multimodal Gemini model this pipeline can
    drive. Conservative: unknown families are excluded rather than risked."""
    mid = strip_prefix(model_id).lower()
    if not mid.startswith("gemini-"):
        return False
    return not any(bad in mid for bad in _EXCLUDE_SUBSTRINGS)


def _sort_key(info: dict, prefer_tier: str):
    """Higher sorts first.

    Order of precedence:
      1. tier match — an explicit cost/latency choice the caller made
      2. version    — newer generation
      3. stability  — stable over preview (only matters if previews included)
      4. bare alias — 'gemini-2.5-flash' over 'gemini-2.5-flash-05-20',
                      because the alias tracks the current stable snapshot
      5. tier rank  — pro > flash > flash-lite as a final tiebreak
    """
    return (
        1 if info["tier"] == prefer_tier else 0,
        info["version"],
        0 if info["preview"] else 1,
        0 if info["dated"] else 1,
        _TIER_ORDER.get(info["tier"], 0),
    )


def rank_models(model_ids, prefer_tier: str = "flash",
                include_preview: bool = False) -> list:
    """Best-first list of parsed candidates, unusable families dropped.

    prefer_tier: 'flash' (default — the cost/latency fit for per-clip video
    analysis), 'pro' for maximum reasoning, or 'flash-lite' for cheapest.
    """
    infos = [parse_model(m) for m in model_ids]
    infos = [i for i in infos if i["usable"]]
    if not include_preview:
        infos = [i for i in infos if not i["preview"]]
    return sorted(infos, key=lambda i: _sort_key(i, prefer_tier), reverse=True)


def select_model(model_ids, prefer_tier: str = "flash",
                 include_preview: bool = False):
    """Best model id from the list, or None if nothing qualifies."""
    ranked = rank_models(model_ids, prefer_tier, include_preview)
    return ranked[0]["id"] if ranked else None


# ── Network layer ────────────────────────────────────────────────────────────

def list_available_models(api_key: str = None) -> list:
    """Model ids this API key can reach that support generateContent.

    Raises on transport/auth failure — callers that must not fail (runtime
    resolution) catch it; the CLI lets it surface.
    """
    import os
    import google.generativeai as genai

    genai.configure(api_key=api_key or os.environ.get("GEMINI_API_KEY"))
    ids = []
    for m in genai.list_models():
        methods = getattr(m, "supported_generation_methods", []) or []
        if "generateContent" in methods:
            ids.append(strip_prefix(m.name))
    return ids


def resolve_model(configured: str, prefer_tier: str = "flash") -> str:
    """Turn the GEMINI_MODEL setting into a concrete model id.

    Anything other than 'auto' is returned verbatim — an explicit pin is
    honoured exactly, including ids this code has never heard of. 'auto'
    queries the API once and falls back to STABLE_DEFAULT on any failure,
    so a discovery outage can never take the pipeline down.
    """
    if not configured:
        return STABLE_DEFAULT
    if configured.strip().lower() != "auto":
        return configured

    try:
        available = list_available_models()
        picked = select_model(available, prefer_tier=prefer_tier)
        if picked:
            print(f"  ✓ GEMINI_MODEL=auto resolved to {picked} "
                  f"({len(available)} models available)")
            return picked
        print(f"  ⚠ GEMINI_MODEL=auto found no suitable model — "
              f"using {STABLE_DEFAULT}")
    except Exception as e:
        print(f"  ⚠ GEMINI_MODEL=auto discovery failed ({e}) — "
              f"using {STABLE_DEFAULT}")
    return STABLE_DEFAULT
