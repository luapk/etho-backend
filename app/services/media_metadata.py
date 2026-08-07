"""
Capture-time extraction — when the media was RECORDED, not uploaded.

Why this is foundational: a guardian uploading three months of phone
backlog in one sitting must not have every observation stamped with
today's date. Baselines, trend slopes, and the vet report's observation
log are all ordered by *when the behaviour happened*. Without real capture
times, a bulk import silently destroys the longitudinal record it was
meant to build.

Sources, in order of trust:
  1. EXIF DateTimeOriginal / DateTimeDigitized (photos) — set by the camera
  2. QuickTime/MP4 creation_time (videos) — set by the recording device
  3. Filename date patterns — messaging apps (WhatsApp, Signal) and
     screenshots routinely STRIP metadata but keep dates in the filename
     (IMG_20260315_143022.jpg, PXL_…, VID_…, Screenshot_2026-03-15-…)
  4. None — the caller falls back to upload time and records that fact

Every result carries its source so the record can state how the date is
known; a filename-derived date is not as trustworthy as camera EXIF, and
the vet report should be able to say so.
"""

import os
import re
import subprocess
import shutil
from datetime import datetime, timezone

_EXIF_DATETIME_ORIGINAL = 36867
_EXIF_DATETIME_DIGITIZED = 36868
_EXIF_DATETIME = 306

# Filename date patterns used by common phone cameras and messaging apps.
_FILENAME_PATTERNS = [
    # IMG_20260315_143022, VID_20260315_143022, PXL_20260315_143022123
    # (Pixel appends milliseconds, so allow up to 3 trailing digits.)
    re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})[_\-T]?(\d{2})(\d{2})(\d{2})\d{0,3}(?!\d)"),
    # Screenshot_2026-03-15-14-30-22, 2026-03-15 14.30.22
    re.compile(r"(?<!\d)(20\d{2})[-_.](\d{2})[-_.](\d{2})[-_. T]+(\d{2})[-_.](\d{2})[-_.](\d{2})(?!\d)"),
    # Date only: IMG-20260315-WA0001 (WhatsApp), 2026-03-15
    re.compile(r"(?<!\d)(20\d{2})[-_.]?(\d{2})[-_.]?(\d{2})(?!\d)"),
]


def _valid(dt: datetime):
    """Reject nonsense: pre-digital-camera dates and future dates."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if dt.year < 2000 or dt > now:
        return None
    return dt


def _from_exif(path: str):
    try:
        from PIL import Image
        with Image.open(path) as img:
            exif = getattr(img, "_getexif", lambda: None)()
        if not exif:
            return None
        for tag in (_EXIF_DATETIME_ORIGINAL, _EXIF_DATETIME_DIGITIZED, _EXIF_DATETIME):
            raw = exif.get(tag)
            if not raw:
                continue
            try:
                # EXIF format: "2026:03:15 14:30:22"
                return _valid(datetime.strptime(str(raw).strip(),
                                                "%Y:%m:%d %H:%M:%S"))
            except ValueError:
                continue
    except Exception:
        return None
    return None


def _from_video_container(path: str):
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        proc = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries",
             "format_tags=creation_time", "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, timeout=30,
        )
        raw = (proc.stdout or "").strip().splitlines()
        if not raw or not raw[0]:
            return None
        val = raw[0].strip().replace("Z", "+00:00")
        return _valid(datetime.fromisoformat(val))
    except Exception:
        return None


def _from_filename(filename: str):
    if not filename:
        return None
    name = os.path.basename(filename)
    for pattern in _FILENAME_PATTERNS:
        m = pattern.search(name)
        if not m:
            continue
        g = m.groups()
        try:
            if len(g) >= 6:
                dt = datetime(int(g[0]), int(g[1]), int(g[2]),
                              int(g[3]), int(g[4]), int(g[5]),
                              tzinfo=timezone.utc)
            else:
                dt = datetime(int(g[0]), int(g[1]), int(g[2]),
                              12, 0, 0, tzinfo=timezone.utc)
        except ValueError:
            continue
        ok = _valid(dt)
        if ok:
            return ok
    return None


def extract_capture_time(path: str, original_filename: str = None,
                         media_type: str = "video") -> dict:
    """When was this media recorded?

    Returns {captured_at: ISO-8601 or None, source: str, confident: bool}.
    `source` is one of exif | video_metadata | filename | unknown and is
    stored with the record so the provenance of every date is auditable.
    """
    dt, source = None, "unknown"

    if media_type == "image":
        dt = _from_exif(path)
        if dt:
            source = "exif"
    else:
        dt = _from_video_container(path)
        if dt:
            source = "video_metadata"

    if dt is None:
        # Messaging apps and screenshots strip metadata but keep the date
        # in the filename — a genuinely common case for guardian backlogs.
        dt = _from_filename(original_filename or os.path.basename(path))
        if dt:
            source = "filename"

    return {
        "captured_at": dt.astimezone(timezone.utc).isoformat(timespec="seconds")
                       if dt else None,
        "source": source,
        # Camera-written metadata is trustworthy; a filename date is a
        # reasonable inference; nothing found means we must use upload time.
        "confident": source in ("exif", "video_metadata"),
    }
