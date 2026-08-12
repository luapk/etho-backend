"""
Audio acoustic-analysis service for Etho.

Extracts the video's audio track and computes objective signal-processing
metrics — pitch (F0), tonality (spectral flatness), the 220-520 Hz
solicitation-purr band ratio, and per-vocalization event timing — that are
injected into Gemini's Pass 2 context as ground truth. This is the acoustic
counterpart to yolo_pose_service.py: Gemini identifies *what* a sound is
(bark / meow / growl / purr), while this service supplies the measured
numbers Gemini cannot hear precisely, so vocalization claims can cite
"growl measured at 180 Hz, noisy spectrum (Morton: low + rough = threat)"
instead of vague language.

Measured values (pitch, flatness, purr-band ratio, durations) are objective.
The Morton's-rule labels attached to each event are heuristic first-pass
inferences meant to prime Gemini, not final verdicts.

Graceful degradation: if ffmpeg is unavailable or the video has no audio
track, AudioService.available stays False (per-video) and the pipeline
skips audio entirely — Gemini-only analysis still works. Requires a system
ffmpeg binary; scipy/numpy are already present via the vision stack.
"""

import os
import shutil
import subprocess
import tempfile

import numpy as np

try:
    from scipy.io import wavfile
    from scipy.signal import stft
    _SCIPY_OK = True
except Exception as e:  # pragma: no cover - only if scipy missing
    _SCIPY_OK = False
    print(f"  ⚠ Audio: scipy unavailable: {e}")

# Solicitation-purr cry component sits in this band (McComb et al., 2009).
PURR_BAND_HZ = (220.0, 520.0)

# Pitch search range for animal vocalizations (autocorrelation F0).
F0_MIN_HZ = 60.0
F0_MAX_HZ = 2000.0

# Coarse pitch / tonality buckets for the heuristic Morton label.
_PITCH_LOW_HZ = 250.0
_PITCH_HIGH_HZ = 600.0
_FLAT_TONAL = 0.30    # spectral flatness below this ≈ tonal
_FLAT_NOISY = 0.55    # above this ≈ noisy / rough

# Cough screen thresholds: short, aperiodic, broadband bursts.
_COUGH_MAX_SEC = 0.6
_COUGH_FLATNESS_MIN = 0.5


# Buckets in the amplitude envelope handed to the UI.
_ENVELOPE_POINTS = 200


def _morton_inference(pitch_hz, flatness) -> str:
    """Heuristic first-pass label from Morton's motivation-structural rules.
    Measured pitch + tonality → likely motivational category. Priming only."""
    tonal = flatness is not None and flatness < _FLAT_TONAL
    noisy = flatness is not None and flatness > _FLAT_NOISY

    if pitch_hz is None:
        if noisy:
            return "noisy/atonal — possible threat or distress (Morton)"
        if tonal:
            return "tonal — possible appeasement/contact (Morton)"
        return "indeterminate"

    if pitch_hz < _PITCH_LOW_HZ and noisy:
        return "low + rough → aggression/threat (Morton)"
    if pitch_hz > _PITCH_HIGH_HZ and tonal:
        return "high + tonal → fear/appeasement or care-solicitation (Morton)"
    if pitch_hz < _PITCH_LOW_HZ:
        return "low-pitched → assertive/threat-leaning (Morton)"
    if pitch_hz > _PITCH_HIGH_HZ:
        return "high-pitched → arousal/appeasement-leaning (Morton)"
    return "mid-pitched → contact/play solicitation (Morton)"


class AudioService:
    def __init__(self):
        self._ffmpeg = shutil.which("ffmpeg")
        self._available = bool(self._ffmpeg) and _SCIPY_OK
        if self._available:
            print("  ✓ Audio acoustic service ready (ffmpeg + scipy)")
        elif not _SCIPY_OK:
            print("  ⚠ Audio unavailable: scipy not installed")
        else:
            print("  ⚠ Audio unavailable: ffmpeg not found on PATH")

    @property
    def available(self) -> bool:
        return self._available

    # ── Extraction ────────────────────────────────────────────────────────────

    def _extract_wav(self, video_path: str, sr: int, max_seconds: float):
        """Extract a mono PCM wav via ffmpeg and load it. Returns (y, sr) as
        float32 in [-1, 1], or (None, None) if there is no usable audio."""
        tmp_wav = None
        try:
            fd, tmp_wav = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            cmd = [
                self._ffmpeg, "-nostdin", "-y",
                "-t", str(max_seconds),
                "-i", video_path,
                "-vn", "-ac", "1", "-ar", str(sr),
                "-acodec", "pcm_s16le", "-f", "wav",
                tmp_wav,
            ]
            proc = subprocess.run(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=120
            )
            if proc.returncode != 0 or not os.path.exists(tmp_wav) or os.path.getsize(tmp_wav) < 128:
                # No audio stream, or extraction failed.
                return None, None

            read_sr, data = wavfile.read(tmp_wav)
            if data.size == 0:
                return None, None
            if data.ndim > 1:
                data = data.mean(axis=1)
            # Normalise integer PCM to float [-1, 1].
            if np.issubdtype(data.dtype, np.integer):
                max_val = float(np.iinfo(data.dtype).max)
                y = data.astype(np.float32) / max_val
            else:
                y = data.astype(np.float32)
            return y, read_sr
        except Exception as e:
            print(f"  ⚠ Audio extraction failed: {e}")
            return None, None
        finally:
            if tmp_wav and os.path.exists(tmp_wav):
                try:
                    os.unlink(tmp_wav)
                except OSError:
                    pass

    # ── Feature helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _f0_autocorr(seg: np.ndarray, sr: int):
        """Estimate fundamental frequency via autocorrelation.
        Returns (f0_hz, voicing_strength) or (None, 0.0) if unvoiced/noisy.

        Picks the earliest (highest-frequency) strong periodicity peak rather
        than the global maximum, which avoids the classic octave error where a
        pure tone locks onto a subharmonic. Parabolic interpolation refines the
        lag to sub-sample precision.
        """
        if seg.size < sr // int(F0_MAX_HZ):
            return None, 0.0
        seg = seg - seg.mean()
        if not np.any(seg):
            return None, 0.0
        corr = np.correlate(seg, seg, mode="full")[seg.size - 1:]
        if corr[0] <= 0:
            return None, 0.0

        min_lag = max(1, int(sr / F0_MAX_HZ))
        max_lag = min(len(corr) - 1, int(sr / F0_MIN_HZ))
        if max_lag <= min_lag + 1:
            return None, 0.0

        region = corr[min_lag:max_lag]
        region_max = float(region.max())
        if region_max <= 0:
            return None, 0.0

        # Local maxima within the search region.
        interior = np.where(
            (region[1:-1] > region[:-2]) & (region[1:-1] >= region[2:])
        )[0] + 1
        # Prefer the earliest peak reaching 85% of the strongest — the true
        # fundamental, not an equal-height subharmonic at a longer lag.
        strong = interior[region[interior] >= 0.85 * region_max] if interior.size else interior
        if strong.size:
            peak_idx = int(strong[0])
        elif interior.size:
            peak_idx = int(interior[np.argmax(region[interior])])
        else:
            peak_idx = int(np.argmax(region))

        peak = peak_idx + min_lag
        strength = float(corr[peak] / corr[0])  # 0..1, periodicity confidence
        if strength < 0.3:  # too aperiodic to call it voiced
            return None, strength

        # Parabolic interpolation around the peak for sub-sample accuracy.
        lag = float(peak)
        if 0 < peak < len(corr) - 1:
            a, b, c = corr[peak - 1], corr[peak], corr[peak + 1]
            denom = (a - 2 * b + c)
            if denom != 0:
                lag = peak + 0.5 * (a - c) / denom
        if lag <= 0:
            return None, strength
        return float(sr / lag), strength

    # ── Main entry point ─────────────────────────────────────────────────────────

    def analyze(self, video_path: str, sr: int = 22050, max_seconds: float = 120.0) -> dict:
        """Return a measured-acoustics summary dict, or {} if no audio.

        Bounds cost by analysing at most max_seconds of audio at sr Hz.
        """
        if not self._available:
            return {}

        y, sr = self._extract_wav(video_path, sr, max_seconds)
        if y is None or y.size == 0:
            return {}

        # Reject effectively silent tracks.
        peak_amp = float(np.max(np.abs(y)))
        if peak_amp < 1e-3:
            return {"audio_present": False}

        duration = y.size / sr

        # STFT magnitude/power spectrogram.
        nperseg = 2048
        hop = 512
        freqs, times, Z = stft(
            y, fs=sr, nperseg=nperseg, noverlap=nperseg - hop, boundary=None
        )
        mag = np.abs(Z)
        power = mag ** 2  # shape (freq_bins, frames)
        eps = 1e-10

        frame_energy = power.sum(axis=0)  # per-frame energy
        if frame_energy.size == 0 or frame_energy.max() <= 0:
            return {"audio_present": False}

        # Spectral flatness per frame: geo-mean / arith-mean over freq (0=tonal, 1=noisy).
        log_power = np.log(power + eps)
        geo_mean = np.exp(log_power.mean(axis=0))
        arith_mean = power.mean(axis=0) + eps
        flatness = geo_mean / arith_mean

        # Purr-band energy ratio per frame (220-520 Hz).
        band = (freqs >= PURR_BAND_HZ[0]) & (freqs <= PURR_BAND_HZ[1])
        band_energy = power[band, :].sum(axis=0)
        total_energy = frame_energy + eps
        purr_ratio_frame = band_energy / total_energy

        # ── Voice-activity segmentation ──────────────────────────────────────
        noise_floor = float(np.percentile(frame_energy, 25))
        peak_energy = float(frame_energy.max())
        threshold = max(noise_floor * 4.0, peak_energy * 0.05)
        active = frame_energy > threshold

        frame_dt = hop / sr
        min_event_frames = max(1, int(0.12 / frame_dt))   # ignore < 120 ms blips
        gap_merge_frames = max(1, int(0.12 / frame_dt))    # bridge < 120 ms gaps

        events_idx = []  # (start_frame, end_frame) inclusive
        i = 0
        n = active.size
        while i < n:
            if active[i]:
                j = i
                gap = 0
                while j + 1 < n and (active[j + 1] or gap < gap_merge_frames):
                    if active[j + 1]:
                        gap = 0
                    else:
                        gap += 1
                    j += 1
                # trim trailing bridged silence
                end = j
                while end > i and not active[end]:
                    end -= 1
                if (end - i + 1) >= min_event_frames:
                    events_idx.append((i, end))
                i = j + 1
            else:
                i += 1

        events = []
        hop_samples = hop
        for (s, e) in events_idx:
            fl = float(np.mean(flatness[s:e + 1]))
            purr_r = float(np.mean(purr_ratio_frame[s:e + 1]))
            start_sec = float(times[s]) if s < len(times) else s * frame_dt

            # F0 from the raw samples spanning this event.
            s_samp = s * hop_samples
            e_samp = min(y.size, (e + 1) * hop_samples)
            f0, strength = self._f0_autocorr(y[s_samp:e_samp], sr)

            # Pitch contour trend across the event (rising / falling / flat).
            contour = "n/a"
            seg_f0s = []
            win = int(0.05 * sr)  # 50 ms windows
            if e_samp - s_samp >= win * 2:
                for w in range(s_samp, e_samp - win, win):
                    wf0, wst = self._f0_autocorr(y[w:w + win], sr)
                    if wf0 is not None:
                        seg_f0s.append(wf0)
            if len(seg_f0s) >= 3:
                trend = np.polyfit(range(len(seg_f0s)), seg_f0s, 1)[0]
                span = max(seg_f0s) - min(seg_f0s)
                if span < 30:
                    contour = "flat"
                else:
                    contour = "rising" if trend > 0 else "falling"

            duration_sec = round((e - s + 1) * frame_dt, 2)
            # Cough screen: short, aperiodic, broadband-noisy bursts. Coughing
            # frequency is clinically meaningful (cardiac disease, tracheal
            # collapse, kennel cough), so it is worth counting — but this is
            # a HEURISTIC that also catches sneezes, thumps and door bangs.
            # Gemini identifies what the sound actually is; the DSP supplies
            # the count and timing.
            cough_like = bool(duration_sec <= _COUGH_MAX_SEC
                              and fl >= _COUGH_FLATNESS_MIN
                              and f0 is None)
            events.append({
                "timestamp_sec": round(start_sec, 2),
                "duration_sec": duration_sec,
                "pitch_hz": round(f0, 1) if f0 is not None else None,
                "pitch_contour": contour,
                "spectral_flatness": round(fl, 3),
                "tonality": "tonal" if fl < _FLAT_TONAL else ("noisy" if fl > _FLAT_NOISY else "mixed"),
                "purr_band_ratio": round(purr_r, 3),
                "cough_like": cough_like,
                "morton_inference": _morton_inference(f0, fl),
            })

        # ── Aggregate summary ────────────────────────────────────────────────
        voiced_pitches = [ev["pitch_hz"] for ev in events if ev["pitch_hz"] is not None]
        active_time = float(active.sum()) * frame_dt

        # Downsampled amplitude envelope, so the UI can draw the ACTUAL sound
        # instead of inventing a waveform. RMS per bucket, normalised to its own
        # peak — it is a shape, not a calibrated level, and nothing is measured
        # from it. ~200 buckets is plenty for a strip a few hundred pixels wide.
        rms = np.sqrt(frame_energy)
        buckets = min(_ENVELOPE_POINTS, rms.size) or 1
        edges = np.linspace(0, rms.size, buckets + 1).astype(int)
        env = np.array([rms[a:b].max() if b > a else 0.0
                        for a, b in zip(edges[:-1], edges[1:])])
        peak = float(env.max()) or 1.0

        summary = {
            "audio_present": True,
            "duration_analyzed_sec": round(duration, 1),
            "envelope": [round(float(v / peak), 3) for v in env],
            "vocal_activity_coverage": round(active_time / max(duration, eps), 2),
            "vocalization_event_count": len(events),
            "vocalization_events": events[:20],  # cap injected list
            "cough_like_events": {
                "count": sum(1 for ev in events if ev["cough_like"]),
                "timestamps_sec": [ev["timestamp_sec"] for ev in events
                                   if ev["cough_like"]][:20],
                "note": ("Heuristic screen for short aperiodic bursts — also "
                         "triggered by sneezes, thumps and door bangs. Gemini "
                         "confirms what each sound is; a rising cough count "
                         "across visits is the signal worth watching."),
            },
            "tonality": {
                "mean_flatness": round(float(np.mean(flatness)), 3),
                "interpretation": (
                    "predominantly tonal" if float(np.mean(flatness)) < _FLAT_TONAL
                    else "predominantly noisy" if float(np.mean(flatness)) > _FLAT_NOISY
                    else "mixed"
                ),
            },
        }

        if voiced_pitches:
            summary["pitch"] = {
                "mean_hz": round(float(np.mean(voiced_pitches)), 1),
                "min_hz": round(float(np.min(voiced_pitches)), 1),
                "max_hz": round(float(np.max(voiced_pitches)), 1),
            }

        # Solicitation-purr heuristic: sustained energy in the 220-520 Hz cry
        # band during low/rumbly, non-tonal-peak vocalization. Conservative and
        # flagged as "possible" — Gemini makes the final call.
        max_purr_event = max(events, key=lambda ev: ev["purr_band_ratio"], default=None)
        mean_purr = float(np.mean(purr_ratio_frame))
        purr_possible = bool(
            max_purr_event is not None
            and max_purr_event["purr_band_ratio"] > 0.35
            and max_purr_event["duration_sec"] >= 0.4
        )
        summary["solicitation_purr"] = {
            "possible": purr_possible,
            "mean_purr_band_ratio": round(mean_purr, 3),
            "peak_purr_band_ratio": round(
                max_purr_event["purr_band_ratio"], 3) if max_purr_event else 0.0,
            "note": "220-520 Hz cry-band energy; heuristic — confirm audibly",
        }

        return summary
