"""Model discovery/ranking logic. Pure string work — no API key needed."""
import sys, types

for name in ['google', 'google.generativeai', 'cv2']:
    sys.modules[name] = types.ModuleType(name)
sys.modules['google'].generativeai = sys.modules['google.generativeai']

from app.services.model_selector import (
    STABLE_DEFAULT, parse_model, is_usable, rank_models, select_model,
    resolve_model, strip_prefix,
)

ok = fail = 0
def check(name, cond, detail=""):
    global ok, fail
    if cond: ok += 1; print(f"  PASS {name}")
    else: fail += 1; print(f"  FAIL {name} {detail}")

# A realistic listing: current + legacy + preview + non-video families
LISTING = [
    "models/gemini-2.5-flash",
    "models/gemini-2.5-pro",
    "models/gemini-2.5-flash-lite",
    "models/gemini-2.5-flash-preview-05-20",
    "models/gemini-2.0-flash",
    "models/gemini-2.0-flash-exp",
    "models/gemini-1.5-pro",
    "models/text-embedding-004",
    "models/imagen-3.0-generate-002",
    "models/veo-2.0-generate-001",
    "models/gemma-3-27b-it",
]

# ── Parsing ──
check("strips models/ prefix", strip_prefix("models/gemini-2.5-flash") == "gemini-2.5-flash")
p = parse_model("models/gemini-2.5-flash")
check("parses version", p["version"] == (2, 5), p)
check("parses tier flash", p["tier"] == "flash")
check("stable not flagged preview", not p["preview"] and not p["dated"])
check("flash-lite is its own tier", parse_model("gemini-2.5-flash-lite")["tier"] == "flash-lite")
check("pro tier", parse_model("gemini-2.5-pro")["tier"] == "pro")
check("preview flagged", parse_model("gemini-2.5-flash-preview-05-20")["preview"])
check("dated snapshot flagged", parse_model("gemini-2.5-flash-preview-05-20")["dated"])
check("exp flagged preview", parse_model("gemini-2.0-flash-exp")["preview"])
check("major-only version parses", parse_model("gemini-3-pro")["version"] == (3, 0))

# ── Usability filter ──
for bad in ["text-embedding-004", "imagen-3.0-generate-002", "veo-2.0-generate-001",
            "gemma-3-27b-it", "gemini-2.5-flash-tts", "gemini-2.0-flash-native-audio"]:
    check(f"excludes {bad[:28]}", not is_usable(bad))
check("includes gemini-2.5-flash", is_usable("gemini-2.5-flash"))
check("includes unknown future gemini", is_usable("gemini-4.0-flash"))

# ── Ranking ──
ranked = rank_models(LISTING)
ids = [r["id"] for r in ranked]
check("picks newest stable flash", ids[0] == "gemini-2.5-flash", ids[:3])
check("previews excluded by default", not any("preview" in i or "exp" in i for i in ids), ids)
check("non-video families excluded",
      not any(k in " ".join(ids) for k in ("embedding", "imagen", "veo", "gemma")), ids)
check("newer flash beats older flash",
      ids.index("gemini-2.5-flash") < ids.index("gemini-2.0-flash"))
check("preferred tier beats other tiers",
      ids.index("gemini-2.5-flash") < ids.index("gemini-2.5-pro"))

check("prefer=pro picks pro", select_model(LISTING, prefer_tier="pro") == "gemini-2.5-pro")
check("prefer=flash-lite picks lite",
      select_model(LISTING, prefer_tier="flash-lite") == "gemini-2.5-flash-lite")
check("include_preview keeps stable first (alias over snapshot)",
      select_model(LISTING, include_preview=True) == "gemini-2.5-flash")
check("include_preview widens the pool",
      len(rank_models(LISTING, include_preview=True)) > len(ranked))

# Bare alias preferred over an equivalent dated snapshot
check("alias beats dated snapshot",
      select_model(["gemini-2.5-flash-001", "gemini-2.5-flash"]) == "gemini-2.5-flash")
# A future generation wins within the preferred tier
check("future generation wins",
      select_model(LISTING + ["gemini-3.0-flash"]) == "gemini-3.0-flash")
check("empty listing -> None", select_model([]) is None)
check("only-unusable listing -> None", select_model(["text-embedding-004"]) is None)

# ── Resolution ──
check("explicit pin returned verbatim",
      resolve_model("gemini-2.0-flash") == "gemini-2.0-flash")
check("unknown pin honoured verbatim",
      resolve_model("gemini-9.9-custom") == "gemini-9.9-custom")
check("empty falls back to default", resolve_model("") == STABLE_DEFAULT)
# 'auto' with no reachable API must fall back, never raise
check("auto falls back when discovery fails", resolve_model("auto") == STABLE_DEFAULT)
check("AUTO case-insensitive", resolve_model("  AUTO  ") == STABLE_DEFAULT)

print(f"\n{'='*40}\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
