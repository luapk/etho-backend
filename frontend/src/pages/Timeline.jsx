import React, { useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip,
         ReferenceArea, ReferenceLine } from 'recharts';
import { AlertTriangle, FileText, Scale, Video, Image as ImageIcon,
         Wind, TrendingUp, TrendingDown, Minus, Plus, Camera, Check, Trash2,
         Pencil, X } from 'lucide-react';
import { getTimeline, getTrends, getPet, addWeight, fetchPoster, getCapturePlan,
         updatePet, deleteAnalysis, setAnalysisDate, friendlyError } from '../api';
import { soundColor } from '../components/AudioWaveform';

/*
 * The longitudinal view — the reason the record layer exists.
 *
 * Reading order is deliberate: how they are RIGHT NOW, then how that compares
 * to their own normal, then the individual captures. A guardian should be able
 * to answer "is my pet okay?" from the top of the screen without understanding
 * a single number.
 */

const ZONE = {
  green:  { label: 'Low',      color: '#22c55e', text: 'text-green-300' },
  yellow: { label: 'Moderate', color: '#f59e0b', text: 'text-amber-300' },
  red:    { label: 'Elevated', color: '#ef4444', text: 'text-red-300' },
};

/* Reading tone → colour. Deliberately restrained: "watch" is amber, not red,
   and "calm" is never coloured at all. Colour is how a screen raises its
   voice, so it's reserved for readings that have earned it. */
const TONE = {
  calm:      { text: 'text-white',      icon: 'text-white/70' },
  watch:     { text: 'text-amber-200',  icon: 'text-amber-300' },
  attention: { text: 'text-red-200',    icon: 'text-red-300' },
};

/* Where a capture's date came from. Anything in GUESSED_DATE means the file
   didn't carry one, so the record was dated to the upload day — which is
   almost never when the behaviour happened. */
const GUESSED_DATE = new Set(['unknown', 'filename', null, undefined, '']);

const DATE_SOURCE_NOTE = {
  exif: 'Currently taken from the photo\u2019s own metadata. Changing it marks the date as one you set.',
  video_metadata: 'Currently taken from the video file. Changing it marks the date as one you set.',
  filename: 'Guessed from the filename. Your date will be recorded as one you set.',
  manual: 'You set this date before. It stays marked as set by hand.',
  unknown: 'The file had no date, so this landed on the day you uploaded it. Your date will be recorded as one you set.',
};

const zoneOf = (s) => (s == null ? 'yellow' : s <= 33 ? 'green' : s <= 66 ? 'yellow' : 'red');
const fmtDate = (iso) =>
  new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });

/** Score is within 3 points of a zone boundary — say so rather than flip category. */
const isBorderline = (s) =>
  s != null && (Math.abs(s - 33) <= 3 || Math.abs(s - 66) <= 3);

function ZoneBadge({ score, zone }) {
  const z = ZONE[zone] || ZONE.yellow;
  return (
    <span
      className="px-2.5 py-1 rounded-full text-white text-[11px] font-bold uppercase tracking-wide whitespace-nowrap"
      style={{ background: `${z.color}e6` }}
    >
      {z.label}{isBorderline(score) ? ' · borderline' : ''}
    </span>
  );
}

function Tile({ label, children, sub }) {
  return (
    <div className="glass-card rounded-2xl p-4">
      <p className="font-roboto text-white/60 text-[11px] font-bold uppercase tracking-wider mb-1">
        {label}
      </p>
      <div className="font-roboto font-black text-white text-2xl leading-tight flex items-baseline gap-2 flex-wrap">
        {children}
      </div>
      {sub && <p className="font-roboto text-white/70 text-xs mt-1">{sub}</p>}
    </div>
  );
}

/** One clip's distress curve, with each scored moment dotted in its own zone
 *  colour — so a tile shows at a glance whether a calm clip had one bad
 *  moment in it, which a single overall score cannot say. */
function Sparkline({ curve }) {
  if (!curve?.length) return <div className="h-8" />;
  const W = 180, H = 32;
  const tmax = Math.max(...curve.map((p) => p.t_sec), 1);
  const pts = curve.map((p) => [
    4 + (p.t_sec / tmax) * (W - 8),
    4 + (1 - p.distress_score / 100) * (H - 8),
    ZONE[p.zone || zoneOf(p.distress_score)]?.color || '#e2e8f0',
  ]);
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
  const last = pts[pts.length - 1];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-8" aria-hidden="true">
      <path d={`${d} L${last[0]},${H} L${pts[0][0]},${H} Z`} fill="rgba(255,255,255,0.16)" />
      <path d={d} fill="none" stroke="rgba(255,255,255,0.75)" strokeWidth="1.6" />
      {pts.map((p, i) => (
        <circle key={i} cx={p[0]} cy={p[1]} r="3" fill={p[2]}
                stroke="rgba(255,255,255,0.9)" strokeWidth="1" />
      ))}
    </svg>
  );
}

/** The measured audio underneath, on the same time axis as the dots above:
 *  the amplitude envelope, with a tick where each vocalization was measured.
 *  Two strips sharing an axis answer "was it noisy when they were tense?" —
 *  which neither strip answers alone. */
function AudioStrip({ envelope, events, durationSec, present, eventCount, zone }) {
  const W = 180, H = 18;

  /* Four distinct states, and they must not be confused with each other.
   *
   * The strip used to treat anything falsy as silence, so a clip whose audio
   * WAS analysed — but was analysed before the envelope existed, or by a
   * backend that doesn't report the field yet — was labelled "No audio" while
   * the observation view showed its measured frequencies. Saying a clip has no
   * sound when it demonstrably does is worse than saying nothing.
   *
   * present === false  → genuinely silent, say so
   * envelope           → draw the measured shape
   * events only        → draw where the sounds were, no invented shape
   * neither            → report the count in words, claim no shape at all
   * present == null    → we were not told; stay quiet rather than guess
   */
  if (present === false) {
    return (
      <div className="h-5 flex items-center">
        <span className="font-roboto text-white/25 text-[10px]">No audio</span>
      </div>
    );
  }
  if (present === null || present === undefined) return <div className="h-5" />;

  const dur = durationSec || Math.max(1, ...(events || []).map((e) => e.t_sec || 0)) || 1;
  /* Same colour rule as the full audio timeline, from the same function:
     only THIS animal's sounds are in the distress colours, a person is white,
     and anything unidentified is slate. A tile that coloured a human voice as
     the pet's distress would be telling a different story from the screen it
     opens into. */
  const ticks = (events || []).map((e, i) => (
    <circle key={i} cx={Math.min(W - 2, Math.max(2, (e.t_sec / dur) * W))} cy={H - 2} r="2"
            fill={soundColor(e.source, zone)}
            stroke="rgba(0,0,0,0.35)" strokeWidth="0.5" />
  ));

  if (envelope?.length) {
    const bw = W / envelope.length;
    return (
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-5" aria-hidden="true">
        {envelope.map((v, i) => {
          const h = Math.max(1, v * (H - 5));
          return <rect key={i} x={i * bw} y={H - 4 - h} width={Math.max(0.6, bw - 0.5)}
                       height={h} fill="rgba(255,255,255,0.45)" rx="0.4" />;
        })}
        <line x1="0" y1={H - 3.5} x2={W} y2={H - 3.5} stroke="rgba(255,255,255,0.25)" strokeWidth="0.6" />
        {ticks}
      </svg>
    );
  }

  if (events?.length) {
    return (
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-5" aria-hidden="true">
        <line x1="0" y1={H - 3.5} x2={W} y2={H - 3.5} stroke="rgba(255,255,255,0.25)" strokeWidth="0.6" />
        {ticks}
      </svg>
    );
  }

  return (
    <div className="h-5 flex items-center">
      <span className="font-roboto text-white/35 text-[10px] truncate">
        {eventCount
          ? `${eventCount} sound${eventCount === 1 ? '' : 's'} · no waveform`
          : 'Audio analysed · no waveform'}
      </span>
    </div>
  );
}

/**
 * The stored thumbnail for one capture.
 *
 * Fetched as a blob rather than set as an <img src> because posters are
 * owner-scoped and need the API-key header. Falls back to a media-type icon
 * when nothing was stored — records logged before media was kept, and clips
 * whose poster couldn't be cut, still get a tile that reads correctly.
 */
function Poster({ analysisId, available, mediaType, zoneColor }) {
  const [url, setUrl] = useState(null);

  useEffect(() => {
    if (!available) return undefined;
    let objectUrl = null;
    let cancelled = false;
    fetchPoster(analysisId).then((u) => {
      if (cancelled) {
        if (u) URL.revokeObjectURL(u);
        return;
      }
      objectUrl = u;
      setUrl(u);
    });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [analysisId, available]);

  return (
    <div className="relative w-full aspect-[4/3] bg-black/25 overflow-hidden">
      {url ? (
        <img src={url} alt="" className="w-full h-full object-cover" loading="lazy" />
      ) : (
        <div className="w-full h-full flex items-center justify-center">
          {mediaType === 'image'
            ? <ImageIcon className="w-7 h-7 text-white/30" />
            : <Video className="w-7 h-7 text-white/30" />}
        </div>
      )}
      <div className="absolute inset-x-0 bottom-0 h-1.5" style={{ background: zoneColor }} />
    </div>
  );
}

export default function Timeline({ petId, onOpenVetReport, onUpload, onOpenAnalysis,
                                   embedded = false, refreshKey = 0, onChanged }) {
  const [pet, setPet] = useState(null);
  const [items, setItems] = useState([]);
  const [trends, setTrends] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [weighing, setWeighing] = useState(false);
  const [newWeight, setNewWeight] = useState('');
  const [plan, setPlan] = useState(null);
  const [deleting, setDeleting] = useState(null);      // analysis_id awaiting confirm
  const [busyDelete, setBusyDelete] = useState(false);
  const [editingDate, setEditingDate] = useState(null); // analysis_id being re-dated
  const [dateDraft, setDateDraft] = useState('');
  const [busyDate, setBusyDate] = useState(false);

  const load = () => {
    if (!petId) return;
    setLoading(true);
    getCapturePlan(petId).then(setPlan).catch(() => setPlan(null));
    Promise.all([getPet(petId), getTimeline(petId), getTrends(petId)])
      .then(([p, tl, tr]) => {
        setPet(p.pet);
        setItems(tl);
        setTrends(tr);
        setError(null);
      })
      .catch((e) => setError(friendlyError(e)))
      .finally(() => setLoading(false));
  };

  useEffect(load, [petId, refreshKey]);

  const analyses = useMemo(() => items.filter((i) => i.type === 'analysis'), [items]);
  const weights = useMemo(() => items.filter((i) => i.type === 'weight'), [items]);

  const chartData = useMemo(
    () => analyses.map((a) => ({
      date: fmtDate(a.date),
      score: a.distress_score,
      quality: a.quality_grade,
    })),
    [analyses]
  );

  const removeObservation = async (analysisId) => {
    setBusyDelete(true);
    try {
      await deleteAnalysis(analysisId);
      setDeleting(null);
      load();          // trend, baseline and counts are all recomputed
      onChanged?.();
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setBusyDelete(false);
    }
  };

  /* Re-dating a capture from the tile.
   *
   * About a fifth of a camera roll has no usable capture date — screenshots
   * and anything that came through a messaging app lose it — and those land on
   * the upload day, which bends every trend that runs through them. The
   * guardian usually knows when it actually happened, and the timeline is
   * where they SEE it in the wrong place, so that is where the fix belongs.
   *
   * The reload afterwards is not just a refresh: the feed is ordered by
   * observation date, so the tile physically moves, and the baseline, slope
   * and chart are all recomputed against the new ordering.
   */
  const openDateEditor = (item) => {
    setEditingDate(item.analysis_id);
    setDateDraft((item.date || '').slice(0, 10));
  };

  const saveDate = async (analysisId) => {
    if (!dateDraft) return;
    setBusyDate(true);
    try {
      await setAnalysisDate(analysisId, dateDraft);
      setEditingDate(null);
      load();
      onChanged?.();
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setBusyDate(false);
    }
  };

  const confirmBreed = async (breed) => {
    try {
      await updatePet(petId, { breed });
      load();
    } catch (err) {
      setError(friendlyError(err));
    }
  };

  const submitWeight = async (e) => {
    e.preventDefault();
    const kg = parseFloat(newWeight);
    if (!kg) return;
    try {
      await addWeight(petId, kg, 'logged in app');
      setNewWeight('');
      setWeighing(false);
      load();
    } catch (err) {
      setError(friendlyError(err));
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="font-roboto text-white/60">Loading timeline…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="glass-card rounded-2xl p-8 max-w-md text-center">
          <AlertTriangle className="w-12 h-12 text-amber-400 mx-auto mb-3" />
          <p className="font-roboto text-white">{error}</p>
        </div>
      </div>
    );
  }

  const latest = trends?.latest;
  const baseline = trends?.baseline;
  const slope = trends?.slope;
  const reading = trends?.reading;
  const flags = trends?.red_flags || [];
  const metrics = trends?.metrics || [];

  return (
    <div className={`px-4 md:px-6 ${embedded ? "pt-5 pb-10" : "min-h-screen py-8"}`}>
      <div className="max-w-4xl mx-auto space-y-4">

        {/* No pet header here when embedded — the PetPage shell owns it, and
            two names stacked on one screen reads as a bug. */}
        {!embedded && (
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
            <h1 className="font-roboto font-black text-3xl text-white">{pet?.name}</h1>
            <p className="font-roboto text-white/70 capitalize">
              {[pet?.species, pet?.breed].filter(Boolean).join(' · ')}
              {analyses.length > 0 && ` · ${analyses.length} observation${analyses.length === 1 ? '' : 's'}`}
            </p>
          </motion.div>
        )}

        {analyses.length === 0 ? (
          <div className="glass-card rounded-2xl p-8 text-center">
            <Video className="w-12 h-12 text-white/50 mx-auto mb-3" />
            <h2 className="font-roboto font-bold text-white text-xl mb-2">
              No observations yet
            </h2>
            <p className="font-roboto text-white/70 mb-5">
              Upload a clip or photo of {pet?.name} and it'll appear here. After
              three, Etho can start spotting changes from their normal.
            </p>
            <button
              onClick={onUpload}
              className="px-6 py-3 rounded-xl bg-white/30 hover:bg-white/40 text-white font-roboto font-bold transition-colors"
            >
              Add first observation
            </button>
          </div>
        ) : (
          <>
            {/* Life captures — first on the page.
                This is the record. The statistics underneath describe it, but
                the pictures ARE it, and a guardian opening their pet's page
                wants to see their animal before they see a standard
                deviation. */}
            <div>
              <div className="flex items-baseline justify-between mb-2 px-1">
                <h2 className="font-roboto font-bold text-white">Life captures</h2>
                <span className="font-roboto text-white/50 text-xs">Scroll · tap for detail</span>
              </div>
              {/* Why a filmstrip with no pictures. Media storage arrived after
                  the first releases, so early records are text-only and always
                  will be — the media was never kept. Saying so beats leaving a
                  row of grey placeholders to be interpreted as a bug. */}
              {analyses.length > 0 && !analyses.some((a) => a.has_poster) && (
                <p className="font-roboto text-white/45 text-xs mb-2 px-1">
                  These observations were recorded before Etho started keeping
                  the pictures, so there's nothing to show for them. New uploads
                  will appear here with their thumbnails.
                </p>
              )}

              <div className="flex gap-3 overflow-x-auto pb-3 scroll-container">
                {items.map((item, idx) => {
                  if (item.type === 'weight') {
                    return (
                      <div
                        key={`w${idx}`}
                        className="flex-none w-24 rounded-2xl border border-dashed border-white/40 bg-white/5 flex flex-col items-center justify-center p-3 gap-1"
                      >
                        <Scale className="w-4 h-4 text-white/60" />
                        <span className="font-roboto font-black text-white">{item.weight_kg}<span className="text-xs font-bold"> kg</span></span>
                        <span className="font-roboto text-white/50 text-[11px]">{fmtDate(item.date)}</span>
                      </div>
                    );
                  }
                  const z = ZONE[item.zone] || ZONE.yellow;
                  const pendingDelete = deleting === item.analysis_id;
                  return (
                    <div key={item.analysis_id || idx} className="relative flex-none w-52">
                    {/* Delete lives on the tile, but never inside the
                        tap-to-open target: a separate button in the corner,
                        and the confirmation covers the tile so the answer
                        cannot be mis-tapped either. */}
                    <button
                      onClick={(e) => { e.stopPropagation(); openDateEditor(item); }}
                      aria-label="Change the date of this observation"
                      className="tap-compact absolute bottom-1 right-8 z-10 flex items-center justify-center text-white/45 hover:text-white drop-shadow-[0_1px_3px_rgba(0,0,0,0.55)] transition-colors"
                    >
                      <Pencil className="w-3.5 h-3.5" />
                    </button>

                    <button
                      onClick={(e) => { e.stopPropagation(); setDeleting(item.analysis_id); }}
                      aria-label="Delete this observation"
                      className="tap-compact absolute bottom-1 right-1 z-10 flex items-center justify-center text-white/45 hover:text-red-300 drop-shadow-[0_1px_3px_rgba(0,0,0,0.55)] transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>

                    {editingDate === item.analysis_id && (
                      <div className="absolute inset-0 z-20 rounded-2xl bg-slate-900/90 backdrop-blur-sm flex flex-col justify-center gap-2 p-3">
                        <div className="flex items-center justify-between">
                          <p className="font-roboto text-white text-xs font-bold">
                            When was this taken?
                          </p>
                          <button
                            onClick={() => setEditingDate(null)}
                            aria-label="Cancel"
                            className="tap-compact text-white/50 hover:text-white"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                        <input
                          type="date"
                          value={dateDraft}
                          max={new Date().toISOString().slice(0, 10)}
                          onChange={(e) => setDateDraft(e.target.value)}
                          className="w-full px-2 py-2 rounded-lg bg-white/15 border border-white/30 text-white font-roboto text-sm focus:outline-none focus:border-white/70"
                        />
                        <p className="font-roboto text-white/50 text-[10px] leading-snug">
                          {DATE_SOURCE_NOTE[item.capture_time_source] || DATE_SOURCE_NOTE.unknown}
                        </p>
                        <button
                          onClick={() => saveDate(item.analysis_id)}
                          disabled={busyDate || !dateDraft}
                          className="px-3 py-2 rounded-lg bg-white/35 hover:bg-white/45 disabled:opacity-40 text-white font-roboto text-xs font-bold"
                        >
                          {busyDate ? 'Moving…' : 'Save date'}
                        </button>
                      </div>
                    )}

                    {pendingDelete && (
                      <div className="absolute inset-0 z-20 rounded-2xl bg-slate-900/85 backdrop-blur-sm flex flex-col items-center justify-center gap-2 p-3 text-center">
                        <p className="font-roboto text-white text-xs">
                          Delete this {item.media_type === 'image' ? 'photo' : 'clip'} and
                          everything measured from it?
                        </p>
                        <p className="font-roboto text-white/55 text-[10px]">
                          {pet?.name}'s trend is worked out again without it.
                        </p>
                        <div className="flex gap-2 mt-1">
                          <button
                            onClick={() => removeObservation(item.analysis_id)}
                            disabled={busyDelete}
                            className="px-3 py-1.5 rounded-lg bg-red-500/85 hover:bg-red-500 disabled:opacity-50 text-white font-roboto text-xs font-bold"
                          >
                            {busyDelete ? 'Deleting…' : 'Delete'}
                          </button>
                          <button
                            onClick={() => setDeleting(null)}
                            className="px-3 py-1.5 rounded-lg bg-white/20 hover:bg-white/30 text-white font-roboto text-xs"
                          >
                            Keep
                          </button>
                        </div>
                      </div>
                    )}

                    {/* h-full so the card fills its wrapper. The wrapper is a
                        stretched flex item as tall as the tallest tile in the
                        row; without it a short tile's card stops early and the
                        corner delete button lands on the background below the
                        card instead of inside the tile. */}
                    <button
                      onClick={() => onOpenAnalysis?.(item.analysis_id, item.date)}
                      className="w-full h-full glass-card rounded-2xl overflow-hidden text-left transition-all hover:bg-white/25 focus:outline-none focus:ring-2 focus:ring-white"
                    >
                      <Poster
                        analysisId={item.analysis_id}
                        available={item.has_poster}
                        mediaType={item.media_type}
                        zoneColor={z.color}
                      />
                      <div className="p-3 space-y-2">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-roboto text-white/70 text-xs font-bold flex items-center gap-1">
                            {fmtDate(item.date)}
                            {/* A date the tool GUESSED gets a marker. Those
                                landed on the upload day and drag every trend
                                that runs through them, and the guardian is the
                                only one who knows the real one. */}
                            {GUESSED_DATE.has(item.capture_time_source) && (
                              <span className="text-amber-300/80" title="Date not in the file — tap the pencil to set it">
                                ?
                              </span>
                            )}
                          </span>
                          <ZoneBadge score={item.distress_score} zone={item.zone} />
                        </div>
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-roboto font-black text-white text-xl">
                            {item.distress_score}
                            <span className="text-xs font-bold text-white/50">/100</span>
                          </span>
                          <span className="flex items-center gap-1 text-white/60">
                            {item.media_type === 'image'
                              ? <ImageIcon className="w-3.5 h-3.5" />
                              : <Video className="w-3.5 h-3.5" />}
                            {item.srr_bpm && (
                              <span className="flex items-center gap-0.5 text-[11px]">
                                <Wind className="w-3 h-3" />{item.srr_bpm}
                              </span>
                            )}
                          </span>
                        </div>
                        <Sparkline curve={item.distress_curve} />
                        <AudioStrip
                          zone={item.zone}
                          envelope={item.audio_envelope}
                          events={item.vocal_events}
                          durationSec={item.audio_duration_sec}
                          present={item.audio_present}
                          eventCount={item.audio_event_count}
                        />
                        <div className="flex flex-wrap gap-1 pr-7">
                          {item.context && (
                            <span className="px-1.5 py-0.5 rounded bg-white/15 border border-white/20 text-white/80 text-[10px] font-bold capitalize">
                              {item.context.replace(/_/g, ' ')}
                            </span>
                          )}
                          {item.quality_grade && item.quality_grade !== 'good' && (
                            <span className="px-1.5 py-0.5 rounded bg-white/15 border border-white/20 text-white/70 text-[10px] font-bold">
                              {item.quality_grade} quality
                            </span>
                          )}
                        </div>
                      </div>
                    </button>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* The one-sentence answer to "is my pet okay?" — but only when the
                answer is something other than "fine".
                For a settled pet this card said "Settled / all observations sit
                in their calm range" directly above a Direction tile reading
                "Settled" and a normal tile reading "within their usual range":
                three ways of saying nothing has happened, which trains a
                guardian to skim past the row. When the reading has actually
                earned concern it says something the tiles cannot, so it stays
                for those. */}
            {reading?.detail && reading.tone !== 'calm' && (
              <motion.div
                initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                className="glass-card rounded-2xl p-5"
              >
                <p className={`font-roboto font-black text-xl ${TONE[reading.tone]?.text || 'text-white'}`}>
                  {reading.headline}
                </p>
                <p className="font-roboto text-white/75 text-sm mt-1">{reading.detail}</p>
              </motion.div>
            )}

            {/* How they are now */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <Tile
                label="Right now"
                sub={`Last seen ${latest ? fmtDate(latest.created_at) : '—'}`}
              >
                {latest?.distress_score ?? '—'}
                {latest && <ZoneBadge score={latest.distress_score} zone={latest.zone} />}
              </Tile>

              <Tile
                label="Their normal"
                sub={
                  /* A 2 SD jump inside the green band is statistically real and
                     clinically unremarkable. Saying "well above normal" without
                     that context is the same scare the trend wording had. */
                  baseline
                    ? !baseline.flag
                      ? 'Latest is within their usual range'
                      : baseline.latest_deviation_sigma < 0
                        ? 'Calmer than their usual'
                        : latest?.zone === 'green'
                          ? 'Above their usual — still in the calm range'
                          : 'Well above their usual'
                    : `Needs ${Math.max(0, 3 - analyses.length)} more observation(s)`
                }
              >
                {baseline ? (
                  <>
                    {baseline.mean}
                    <span className="text-base text-white/60 font-bold">± {baseline.std}</span>
                  </>
                ) : '—'}
              </Tile>

              {/* The headline comes from the backend reading, which weighs
                  WHERE the scores sit before it weighs which way they lean —
                  a rising line inside the calm band is not bad news. The raw
                  gradient stays underneath for anyone who wants it. */}
              <Tile
                label="Direction"
                sub={
                  slope
                    ? `${slope.points_per_week > 0 ? '+' : ''}${slope.points_per_week} pts/week`
                    : 'Needs 4+ observations'
                }
              >
                <span className={`flex items-center gap-2 text-xl ${TONE[reading?.tone]?.text || ''}`}>
                  {slope && (slope.direction === 'rising'
                    ? <TrendingUp className={`w-6 h-6 ${TONE[reading?.tone]?.icon || 'text-white/70'}`} />
                    : slope.direction === 'easing'
                      ? <TrendingDown className="w-6 h-6 text-green-300" />
                      : <Minus className="w-6 h-6 text-white/70" />)}
                  {reading?.headline || '—'}
                </span>
              </Tile>

              <Tile
                label="Weight"
                sub={weights.length ? `${weights.length} entries logged` : 'Not logged yet'}
              >
                {pet?.weight_kg ? <>{pet.weight_kg}<span className="text-base text-white/60"> kg</span></> : '—'}
              </Tile>
            </div>

            {/* Things worth mentioning to a vet */}
            {flags.length > 0 && (
              <motion.div
                initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                className="glass-card rounded-2xl p-5 border-2 border-amber-500/50"
              >
                <div className="flex items-center gap-2 mb-3">
                  <AlertTriangle className="w-5 h-5 text-amber-300" />
                  <h2 className="font-roboto font-bold text-white">
                    Worth mentioning to your vet
                  </h2>
                </div>
                <ul className="space-y-2">
                  {flags.slice(-5).reverse().map((f, i) => (
                    <li key={i} className="font-roboto text-white/85 text-sm flex gap-3">
                      <span className="text-white/50 flex-none">{fmtDate(f.created_at)}</span>
                      <span>{f.detail}</span>
                    </li>
                  ))}
                </ul>
              </motion.div>
            )}

            {/* What's changed against their own normal.
                Separate from the vet-flag panel above on purpose: that one is
                a list of moments that crossed a published threshold, this is
                the slow drift that never does. For an animal that masks pain,
                this is the panel that actually catches something — so it shows
                every metric with enough history, not just the ones flagged,
                because "steady" is a real and reassuring answer. */}
            {metrics.length > 0 && (
              <div className="glass-card rounded-2xl p-5">
                <h2 className="font-roboto font-bold text-white mb-1">
                  Against {pet?.name}'s own normal
                </h2>
                <p className="font-roboto text-white/50 text-sm mb-4">
                  Cats and stoic dogs hide discomfort well, so what matters is
                  change over time rather than any single number.
                </p>
                <div className="space-y-2.5">
                  {metrics.map((m) => (
                    <div key={m.key}
                         className={`rounded-xl p-3.5 border ${m.flag
                           ? 'bg-amber-400/10 border-amber-300/50'
                           : 'bg-white/5 border-white/10'}`}>
                      <div className="flex items-baseline justify-between gap-3 flex-wrap">
                        <span className="font-roboto text-white font-bold text-sm">
                          {m.label}
                        </span>
                        <span className="font-roboto text-white/50 text-[10px] font-bold uppercase tracking-wider">
                          {m.kind === 'measured' ? 'Measured' : 'AI-estimated'}
                        </span>
                      </div>
                      <div className="flex items-baseline gap-2 mt-1 flex-wrap">
                        <span className="font-roboto font-black text-white text-2xl">
                          {m.latest}<span className="text-xs font-bold text-white/50">{m.unit}</span>
                        </span>
                        <span className="font-roboto text-white/60 text-xs">
                          usual {m.mean} ± {m.std} · {m.n} before this
                        </span>
                      </div>
                      {m.flag ? (
                        <p className="font-roboto text-amber-100 text-xs mt-2 leading-relaxed">
                          {m.reading}
                        </p>
                      ) : (
                        <p className="font-roboto text-white/45 text-xs mt-1.5">
                          {m.change > 0 ? 'Up' : m.change < 0 ? 'Down' : 'No change'}
                          {m.change !== 0 && ` ${Math.abs(m.change)}${m.unit} on their usual`}
                          {' — '}steady for their own range.
                        </p>
                      )}
                    </div>
                  ))}
                </div>
                <p className="font-roboto text-white/35 text-xs mt-4">
                  Only the concerning direction is flagged, and only when the
                  change is big enough to mean something — not merely unusual.
                  None of this is a diagnosis.
                </p>
              </div>
            )}


            {/* Trend over time */}
            <div className="glass-card rounded-2xl p-5">
              <div className="flex items-baseline justify-between mb-1 flex-wrap gap-2">
                <h2 className="font-roboto font-bold text-white">How {pet?.name} has been</h2>
                <span className="font-roboto text-white/50 text-xs">AI-estimated</span>
              </div>
              <p className="font-roboto text-white/60 text-xs mb-3">
                Lower is calmer. The shaded band is {pet?.name}'s own usual range.
              </p>
              <div style={{ height: 220 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 8, right: 8, left: -24, bottom: 4 }}>
                    <ReferenceArea y1={0} y2={33} fill="#22c55e" fillOpacity={0.10} />
                    <ReferenceArea y1={33} y2={66} fill="#f59e0b" fillOpacity={0.10} />
                    <ReferenceArea y1={66} y2={100} fill="#ef4444" fillOpacity={0.10} />
                    {baseline && (
                      <ReferenceArea
                        y1={Math.max(0, baseline.mean - baseline.std)}
                        y2={Math.min(100, baseline.mean + baseline.std)}
                        fill="#ffffff" fillOpacity={0.16}
                      />
                    )}
                    <XAxis dataKey="date" stroke="rgba(255,255,255,0.5)" fontSize={11} tickLine={false} />
                    <YAxis domain={[0, 100]} stroke="rgba(255,255,255,0.5)" fontSize={11} tickLine={false} />
                    <Tooltip
                      contentStyle={{
                        background: 'rgba(15,23,42,0.92)', border: '1px solid rgba(255,255,255,0.2)',
                        borderRadius: 10, color: 'white', fontSize: 12,
                      }}
                      formatter={(v) => [`${v} — ${ZONE[zoneOf(v)].label}`, 'Distress']}
                    />
                    <Line
                      type="monotone" dataKey="score" stroke="white" strokeWidth={2.5}
                      dot={{ r: 4, fill: 'white' }} activeDot={{ r: 6 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* What to film next.
                Breed predispositions arrive here as an ASK, never a warning:
                the only ones that surface are those Etho has a real
                measurement for, so a base rate turns into evidence instead of
                anxiety. Population context, never a claim about this pet. */}
            {plan?.plan?.length > 0 && (
              <div className="glass-card rounded-2xl p-5">
                <div className="flex items-center gap-2 mb-1">
                  <Camera className="w-5 h-5 text-white/70" />
                  <h2 className="font-roboto font-bold text-white">
                    Worth capturing next
                  </h2>
                </div>
                {plan.driven_by_breed && (
                  <p className="font-roboto text-white/50 text-xs mb-3">
                    Tailored to what's commonly reported in {plan.breed}s — not
                    a claim about {pet?.name}.
                  </p>
                )}
                <div className="space-y-3">
                  {plan.plan.slice(0, 2).map((step) => (
                    <button
                      key={step.id}
                      onClick={onUpload}
                      className="w-full text-left p-4 rounded-xl bg-white/10 hover:bg-white/20 transition-colors"
                    >
                      <p className="font-roboto font-bold text-white text-sm">
                        {step.action}
                      </p>
                      <p className="font-roboto text-white/70 text-xs mt-1">{step.why}</p>
                      <p className="font-roboto text-white/45 text-[11px] mt-2">
                        Measures: {step.measures}
                        {step.done_count > 0 && ` · ${step.done_count} so far`}
                        {step.last_measured && ` · last ${fmtDate(step.last_measured)}`}
                      </p>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Breed confirmation. breed_detected is a guess from a frame, so
                it is offered for a human to ratify and never used until they
                do — epidemiology on top of a guess isn't evidence. */}
            {plan?.breed_suggestion && (
              <div className="glass-card rounded-2xl p-4 flex items-center gap-3 flex-wrap">
                <div className="flex-1 min-w-[180px]">
                  <p className="font-roboto text-white text-sm">
                    Is {pet?.name} a <strong>{plan.breed_suggestion.breed}</strong>?
                  </p>
                  <p className="font-roboto text-white/55 text-xs mt-0.5">
                    Seen in {plan.breed_suggestion.seen_in} of their captures.
                    Confirming tailors what's worth filming — we won't guess it
                    for you.
                  </p>
                </div>
                <button
                  onClick={() => confirmBreed(plan.breed_suggestion.breed)}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/30 hover:bg-white/40 text-white font-roboto font-bold text-sm"
                >
                  <Check className="w-4 h-4" /> Yes
                </button>
              </div>
            )}

            {/* Actions */}
            <div className="grid sm:grid-cols-2 gap-3">
              <button
                onClick={() => onOpenVetReport?.(petId)}
                className="glass-card rounded-2xl p-5 flex items-center gap-3 hover:bg-white/25 transition-colors text-left"
              >
                <FileText className="w-6 h-6 text-white flex-none" />
                <div>
                  <p className="font-roboto font-bold text-white">Prepare for the vet</p>
                  <p className="font-roboto text-white/60 text-xs">
                    A summary you can print or email
                  </p>
                </div>
              </button>

              {weighing ? (
                <form onSubmit={submitWeight} className="glass-card rounded-2xl p-4 flex gap-2 items-center">
                  <input
                    autoFocus type="number" step="0.1" min="0"
                    value={newWeight}
                    onChange={(e) => setNewWeight(e.target.value)}
                    placeholder="Weight in kg"
                    className="flex-1 min-w-0 px-3 py-2.5 rounded-xl bg-white/20 border border-white/30 text-white placeholder-white/50 font-roboto focus:outline-none focus:border-white/60"
                  />
                  <button type="submit" className="px-4 py-2.5 rounded-xl bg-white/35 hover:bg-white/45 text-white font-roboto font-bold">
                    Save
                  </button>
                </form>
              ) : (
                <button
                  onClick={() => setWeighing(true)}
                  className="glass-card rounded-2xl p-5 flex items-center gap-3 hover:bg-white/25 transition-colors text-left"
                >
                  <Plus className="w-6 h-6 text-white flex-none" />
                  <div>
                    <p className="font-roboto font-bold text-white">Log a weight</p>
                    <p className="font-roboto text-white/60 text-xs">
                      Weight trend is one of the clearest health signals
                    </p>
                  </div>
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
