"""
Persistent media library for the longitudinal record.

The analysis pipeline works on a temp file and throws it away, and annotated
output lives in /tmp for two hours. That is fine for a one-shot analysis and
useless for a record: a timeline of scores with no pictures is a spreadsheet,
and a guardian scrolling back six months should see the clip that produced the
number, not just the number.

So each logged analysis keeps two artefacts under $DATA_DIR/media/ (the
Railway volume, not /tmp):

  {analysis_id}.mp4 | .jpg    the ANNOTATED media — detection box, distress
                              meter, event captions. Playable in the detail
                              view. This is the big one.
  {analysis_id}_poster.jpg    a downscaled still for the timeline filmstrip,
                              tens of KB.

Two deliberate rules:

  1. **Posters are never evicted.** They are small enough that thousands fit in
     a few hundred MB, and a timeline that loses its pictures loses the thing
     that makes it readable. Full media is evicted oldest-first once the
     library passes MEDIA_MAX_MB, so a volume can't silently fill up and start
     failing writes for the database sharing it.
  2. **Nothing here is load-bearing.** Every function swallows its own errors
     and reports absence. A missing poster degrades the timeline card to the
     text it showed before; it never fails an analysis that already succeeded.

The poster is cut from the ANNOTATED file on purpose: a thumbnail with the
detection box drawn on it shows the guardian, at a glance, that the tool
actually found their pet in that clip.
"""

import os
import shutil
from typing import Optional

from . import pet_store

# Full media beyond this is evicted oldest-first. Chosen to sit well under a
# default Railway volume while leaving room for the database.
DEFAULT_BUDGET_MB = 2000
BUDGET_MB = int(os.environ.get("MEDIA_MAX_MB", DEFAULT_BUDGET_MB))

# Longest edge of a poster. Big enough for a retina filmstrip tile, small
# enough that a thousand of them is a rounding error on the volume.
POSTER_MAX_EDGE = 480
POSTER_QUALITY = 80

# Fraction into the clip the poster frame is taken from. Not 0.0: the first
# frame of a phone video is often a blurred hand-off as the camera settles.
POSTER_SEEK = 0.4

_VIDEO_EXT = ".mp4"
_IMAGE_EXT = ".jpg"


# Small, permanent artefacts. Evicting these would cost the product something
# the record can't replace, and they're tens of KB each. Kept as one predicate
# because three separate places have to agree on what survives.
_KEEP_SUFFIXES = ("_poster.jpg", "_avatar.jpg", "_wallpaper.jpg")


def _is_permanent(filename: str) -> bool:
    return filename.endswith(_KEEP_SUFFIXES)


def media_root() -> str:
    """The media directory, created on demand. Lives beside the database so a
    single mounted volume covers both."""
    root = os.path.join(pet_store.DATA_DIR, "media")
    os.makedirs(root, exist_ok=True)
    return root


def _safe(analysis_id: str) -> bool:
    """IDs are UUID4s. Anything else is a path-traversal attempt."""
    return bool(analysis_id) and analysis_id.replace("-", "").isalnum()


def poster_path(analysis_id: str) -> Optional[str]:
    """Path to the stored poster, or None if there isn't one."""
    if not _safe(analysis_id):
        return None
    p = os.path.join(media_root(), f"{analysis_id}_poster.jpg")
    return p if os.path.exists(p) else None


def media_path(analysis_id: str) -> Optional[str]:
    """Path to the stored annotated media, or None if it was never saved or
    has since been evicted."""
    if not _safe(analysis_id):
        return None
    for ext in (_VIDEO_EXT, _IMAGE_EXT):
        p = os.path.join(media_root(), f"{analysis_id}{ext}")
        if os.path.exists(p):
            return p
    return None


def has_poster(analysis_id: str) -> bool:
    return poster_path(analysis_id) is not None


def has_media(analysis_id: str) -> bool:
    return media_path(analysis_id) is not None


def _write_poster(source_path: str, dest_path: str, is_video: bool) -> bool:
    """Downscale a frame of `source_path` into a JPEG poster."""
    try:
        import cv2
    except Exception:
        return False
    try:
        if is_video:
            cap = cv2.VideoCapture(source_path)
            if not cap.isOpened():
                return False
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            if total > 1:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * POSTER_SEEK))
            ok, frame = cap.read()
            if not ok:
                # Seeking can fail on some containers — fall back to frame 0.
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = cap.read()
            cap.release()
            if not ok or frame is None:
                return False
        else:
            frame = cv2.imread(source_path)
            if frame is None:
                return False

        h, w = frame.shape[:2]
        longest = max(h, w)
        if longest > POSTER_MAX_EDGE:
            scale = POSTER_MAX_EDGE / float(longest)
            frame = cv2.resize(frame, (max(1, int(w * scale)), max(1, int(h * scale))),
                               interpolation=cv2.INTER_AREA)
        return bool(cv2.imwrite(dest_path, frame,
                                [int(cv2.IMWRITE_JPEG_QUALITY), POSTER_QUALITY]))
    except Exception:
        return False


# ── Pet avatars ──────────────────────────────────────────────────────────────
# A profile picture the guardian chooses, as opposed to a poster the pipeline
# cuts. Square-cropped so a list of pets reads as a list of faces rather than a
# jumble of aspect ratios.
AVATAR_EDGE = 512


def avatar_path(pet_id: str) -> Optional[str]:
    if not _safe(pet_id):
        return None
    p = os.path.join(media_root(), f"{pet_id}_avatar.jpg")
    return p if os.path.exists(p) else None


def has_avatar(pet_id: str) -> bool:
    return avatar_path(pet_id) is not None


def save_avatar(pet_id: str, source_path: str) -> bool:
    """Store a square, downscaled profile picture for a pet.

    Centre-cropped to a square before scaling: a phone photo is portrait or
    landscape, and squashing it to fit a round tile distorts the animal's face,
    which is the one thing the picture is for.
    """
    if not _safe(pet_id) or not source_path or not os.path.exists(source_path):
        return False
    try:
        import cv2
    except Exception:
        return False
    try:
        img = cv2.imread(source_path)
        if img is None:
            return False
        h, w = img.shape[:2]
        side = min(h, w)
        top, left = (h - side) // 2, (w - side) // 2
        img = img[top:top + side, left:left + side]
        if side > AVATAR_EDGE:
            img = cv2.resize(img, (AVATAR_EDGE, AVATAR_EDGE),
                             interpolation=cv2.INTER_AREA)
        return bool(cv2.imwrite(os.path.join(media_root(), f"{pet_id}_avatar.jpg"),
                                img, [int(cv2.IMWRITE_JPEG_QUALITY), 85]))
    except Exception as e:
        print(f"  ⚠ Could not store avatar for {pet_id}: {e}")
        return False


def delete_avatar(pet_id: str) -> bool:
    path = avatar_path(pet_id)
    if not path:
        return False
    try:
        os.unlink(path)
        return True
    except OSError:
        return False


# ── Wallpaper ────────────────────────────────────────────────────────────────
# The full-screen background behind the whole app while this pet is open.
#
# Uploaded from the guardian's camera roll, or copied from the profile picture
# — deliberately NOT offered from the stored captures, because everything the
# library keeps is ANNOTATED: detection box, distress meter, caption strips. A
# wallpaper with a green rectangle and "Distress 22 - LOW" burned into it is a
# screenshot of the tool, not a picture of the animal.
#
# Not square-cropped like the avatar: this is displayed with object-fit cover
# across every phone shape there is, and cropping twice throws away the margin
# the browser needs to do that well.
WALLPAPER_MAX_EDGE = 1440
WALLPAPER_QUALITY = 82


def wallpaper_path(pet_id: str) -> Optional[str]:
    if not _safe(pet_id):
        return None
    p = os.path.join(media_root(), f"{pet_id}_wallpaper.jpg")
    return p if os.path.exists(p) else None


def has_wallpaper(pet_id: str) -> bool:
    return wallpaper_path(pet_id) is not None


def save_wallpaper(pet_id: str, source_path: str) -> bool:
    """Store a pet's background photo, scaled down but not reshaped."""
    if not _safe(pet_id) or not source_path or not os.path.exists(source_path):
        return False
    try:
        import cv2
    except Exception:
        return False
    try:
        img = cv2.imread(source_path)
        if img is None:
            return False
        h, w = img.shape[:2]
        longest = max(h, w)
        if longest > WALLPAPER_MAX_EDGE:
            k = WALLPAPER_MAX_EDGE / longest
            img = cv2.resize(img, (max(1, int(w * k)), max(1, int(h * k))),
                             interpolation=cv2.INTER_AREA)
        return bool(cv2.imwrite(os.path.join(media_root(), f"{pet_id}_wallpaper.jpg"),
                                img, [int(cv2.IMWRITE_JPEG_QUALITY), WALLPAPER_QUALITY]))
    except Exception as e:
        print(f"  ⚠ Could not store wallpaper for {pet_id}: {e}")
        return False


def delete_wallpaper(pet_id: str) -> bool:
    path = wallpaper_path(pet_id)
    if not path:
        return False
    try:
        os.unlink(path)
        return True
    except OSError:
        return False


def save_for_analysis(analysis_id: str, media_type: str,
                      annotated_path: str = None,
                      original_path: str = None) -> dict:
    """Keep the annotated media and a poster for one logged analysis.

    `annotated_path` is preferred for both; `original_path` is the fallback the
    poster falls back to when annotation was skipped or failed, so a timeline
    card still gets a picture even with annotate=false.

    Returns {"media": bool, "poster": bool} — never raises.
    """
    saved = {"media": False, "poster": False}
    if not _safe(analysis_id):
        return saved

    is_video = media_type == "video"
    try:
        root = media_root()

        if annotated_path and os.path.exists(annotated_path):
            ext = _VIDEO_EXT if is_video else _IMAGE_EXT
            dest = os.path.join(root, f"{analysis_id}{ext}")
            shutil.copyfile(annotated_path, dest)
            saved["media"] = True

        poster_source = annotated_path if saved["media"] else original_path
        if poster_source and os.path.exists(poster_source):
            saved["poster"] = _write_poster(
                poster_source,
                os.path.join(root, f"{analysis_id}_poster.jpg"),
                is_video,
            )
    except Exception as e:
        print(f"  ⚠ Could not store media for {analysis_id}: {e}")

    enforce_budget()
    return saved


def library_bytes() -> int:
    """Total size of stored full media (posters excluded — they are never
    evicted, so they don't count against the eviction budget)."""
    total = 0
    try:
        for name in os.listdir(media_root()):
            if _is_permanent(name):
                continue
            try:
                total += os.path.getsize(os.path.join(media_root(), name))
            except OSError:
                pass
    except Exception:
        pass
    return total


def enforce_budget(budget_mb: int = None) -> int:
    """Delete the oldest full media until the library fits the budget.

    Posters survive: the timeline keeps its pictures even after the playable
    clip is gone, and the detail view says the clip has aged out rather than
    showing a broken player. Returns the number of files removed.
    """
    limit = (budget_mb if budget_mb is not None else BUDGET_MB) * 1024 * 1024
    if limit <= 0:
        return 0
    try:
        root = media_root()
        files = []
        for name in os.listdir(root):
            if _is_permanent(name):
                continue
            path = os.path.join(root, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            files.append((st.st_mtime, st.st_size, path))
    except Exception:
        return 0

    total = sum(f[1] for f in files)
    if total <= limit:
        return 0

    removed = 0
    for _, size, path in sorted(files):        # oldest mtime first
        if total <= limit:
            break
        try:
            os.unlink(path)
            total -= size
            removed += 1
        except OSError:
            pass
    if removed:
        print(f"  → Media library over {limit // (1024*1024)}MB: evicted "
              f"{removed} old clip(s), posters kept")
    return removed


def delete_for_analysis(analysis_id: str) -> None:
    """Remove both artefacts for one analysis (used when a record is deleted)."""
    for path in (media_path(analysis_id), poster_path(analysis_id)):
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


def storage_status() -> dict:
    """Plain-English summary for /health."""
    used = library_bytes()
    posters = 0
    avatars = 0
    wallpapers = 0
    clips = 0
    try:
        for name in os.listdir(media_root()):
            if name.endswith("_poster.jpg"):
                posters += 1
            elif name.endswith("_avatar.jpg"):
                avatars += 1
            elif name.endswith("_wallpaper.jpg"):
                wallpapers += 1
            else:
                clips += 1
    except Exception:
        pass
    # How much of the record actually has a picture. This is the number that
    # tells a deploy apart: posters == 0 with analyses > 0 means the backend
    # never wrote any (bad DATA_DIR, or every record predates the feature),
    # whereas posters > 0 means storage works and anything missing on screen
    # is a frontend or auth problem.
    audit = pet_store.analysis_media_audit()
    logged = len(audit)
    assigned = [a for a in audit if a.get("pet_id")]
    unassigned = logged - len(assigned)
    with_poster = sum(1 for a in audit if has_poster(a["id"]))

    # The newest record is the one that settles it. If it was logged after this
    # code went live and still has no picture, something is failing; if it
    # predates the deploy, there is nothing to find — its media was deleted at
    # the time, before anything kept it.
    newest = audit[-1] if audit else None
    newest_at = newest["created_at"] if newest else None
    newest_poster = bool(newest and has_poster(newest["id"]))
    first_with_poster = next((a["created_at"] for a in audit if has_poster(a["id"])), None)

    if not logged:
        coverage = "no observations logged yet"
    elif with_poster:
        coverage = (f"{with_poster}/{logged} observations have a stored picture "
                    f"(media kept from {first_with_poster[:10]} onward)")
    else:
        coverage = (f"0/{logged} observations have a stored picture. Newest was "
                    f"logged {newest_at[:19] if newest_at else 'never'} — if that "
                    f"is BEFORE this build was deployed, its media was never "
                    f"kept and cannot be recovered; upload one new clip to test.")

    return {
        "dir": media_root(),
        "analyses_logged": logged,
        "analyses_with_poster": with_poster,
        # Unassigned analyses NEVER store media — there is no timeline for it to
        # appear in, so nothing would ever read it. Counted separately so this
        # cannot be mistaken for a failure.
        "analyses_with_pet": len(assigned),
        "analyses_unassigned": unassigned,
        "newest_analysis_at": newest_at,
        "newest_has_poster": newest_poster,
        "coverage": coverage,
        "clips_stored": clips,
        "posters_stored": posters,
        "avatars_stored": avatars,
        "wallpapers_stored": wallpapers,
        "used_mb": round(used / (1024 * 1024), 1),
        "budget_mb": BUDGET_MB,
        "note": ("Annotated clips are evicted oldest-first past the budget; "
                 "timeline posters, pet avatars and wallpapers are always kept."),
    }
