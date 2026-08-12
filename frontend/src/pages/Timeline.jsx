import React, { useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip,
         ReferenceArea, ReferenceLine } from 'recharts';
import { AlertTriangle, FileText, Scale, Video, Image as ImageIcon,
         Wind, TrendingUp, TrendingDown, Minus, Plus } from 'lucide-react';
import { getTimeline, getTrends, getPet, addWeight, fetchPoster, friendlyError } from '../api';

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

/** Inline sparkline of one clip's own distress curve. */
function Sparkline({ curve }) {
  if (!curve?.length) return <div className="h-8" />;
  const W = 180, H = 32;
  const tmax = Math.max(...curve.map((p) => p.t_sec), 1);
  const pts = curve.map((p) => [
    4 + (p.t_sec / tmax) * (W - 8),
    4 + (1 - p.distress_score / 100) * (H - 8),
  ]);
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
  const last = pts[pts.length - 1];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-8" aria-hidden="true">
      <path d={`${d} L${last[0]},${H} L${pts[0][0]},${H} Z`} fill="rgba(255,255,255,0.18)" />
      <path d={d} fill="none" stroke="white" strokeWidth="1.6" strokeDasharray="3 3" opacity="0.85" />
      {pts.map((p, i) => (
        <circle key={i} cx={p[0]} cy={p[1]} r="2.4" fill="white" />
      ))}
    </svg>
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

export default function Timeline({ petId, onOpenVetReport, onUpload, onOpenAnalysis }) {
  const [pet, setPet] = useState(null);
  const [items, setItems] = useState([]);
  const [trends, setTrends] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [weighing, setWeighing] = useState(false);
  const [newWeight, setNewWeight] = useState('');

  const load = () => {
    if (!petId) return;
    setLoading(true);
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

  useEffect(load, [petId]);

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

  return (
    <div className="min-h-screen px-4 py-8 md:px-6">
      <div className="max-w-4xl mx-auto space-y-4">

        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="font-roboto font-black text-3xl text-white">{pet?.name}</h1>
          <p className="font-roboto text-white/70 capitalize">
            {[pet?.species, pet?.breed].filter(Boolean).join(' · ')}
            {analyses.length > 0 && ` · ${analyses.length} observation${analyses.length === 1 ? '' : 's'}`}
          </p>
        </motion.div>

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
            {/* The one-sentence answer to "is my pet okay?", before any number */}
            {reading?.detail && (
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

            {/* Capture filmstrip */}
            <div>
              <div className="flex items-baseline justify-between mb-2 px-1">
                <h2 className="font-roboto font-bold text-white">Every capture</h2>
                <span className="font-roboto text-white/50 text-xs">Scroll · tap for detail</span>
              </div>
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
                  return (
                    <button
                      key={item.analysis_id || idx}
                      onClick={() => onOpenAnalysis?.(item.analysis_id)}
                      className="flex-none w-52 glass-card rounded-2xl overflow-hidden text-left transition-all hover:bg-white/25 focus:outline-none focus:ring-2 focus:ring-white"
                    >
                      <Poster
                        analysisId={item.analysis_id}
                        available={item.has_poster}
                        mediaType={item.media_type}
                        zoneColor={z.color}
                      />
                      <div className="p-3 space-y-2">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-roboto text-white/70 text-xs font-bold">
                            {fmtDate(item.date)}
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
                        <div className="flex flex-wrap gap-1">
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
                  );
                })}
              </div>
            </div>

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
