import React, { useMemo } from 'react';

// Zone colors with gradient support
const ZONE_COLORS = {
  green: { primary: '#22c55e', secondary: '#4ade80' },
  yellow: { primary: '#f59e0b', secondary: '#fbbf24' }, 
  red: { primary: '#ef4444', secondary: '#f87171' },
  inactive: { primary: '#334155', secondary: '#475569' }
};

// Get zone from vocalization type
const getVocalizationZone = (type, subtype) => {
  const combined = `${type || ''} ${subtype || ''}`.toLowerCase();
  
  if (combined.includes('distress') || combined.includes('alarm') || combined.includes('pain') ||
      combined.includes('fear') || combined.includes('aggressive') || combined.includes('threat') ||
      combined.includes('growl') || combined.includes('hiss') || combined.includes('scream')) return 'red';
  
  if (combined.includes('demand') || combined.includes('frustrat') || combined.includes('alert') ||
      combined.includes('complaint') || combined.includes('whine') || combined.includes('urgent') ||
      combined.includes('bark') || combined.includes('excitement')) return 'yellow';
  
  if (combined.includes('play') || combined.includes('happy') || combined.includes('relax') ||
      combined.includes('greeting') || combined.includes('friendly') || combined.includes('purr')) return 'green';
  
  return 'yellow';
};

// Generate contextual description
const getContextualDescription = (event, videoContext) => {
  const type = event.type || '';
  const subtype = event.subtype || '';
  const context = videoContext?.toLowerCase() || '';
  
  let contextSuffix = '';
  if (context.includes('door')) contextSuffix = 'at door';
  else if (context.includes('window')) contextSuffix = 'at window';
  else if (context.includes('person') || context.includes('stranger')) contextSuffix = 'at person';
  else if (context.includes('cat') || context.includes('dog') || context.includes('animal')) contextSuffix = 'at animal';
  else if (context.includes('food') || context.includes('treat')) contextSuffix = 'for food';
  else if (context.includes('play') || context.includes('toy')) contextSuffix = 'during play';
  else if (context.includes('barrier') || context.includes('gate')) contextSuffix = 'at barrier';
  else if (context.includes('camera') || context.includes('close')) contextSuffix = 'at camera';
  
  if (subtype && subtype !== type) {
    const formattedSubtype = subtype.replace(/_/g, ' ');
    return contextSuffix ? `${type} — ${formattedSubtype} ${contextSuffix}` : `${type} — ${formattedSubtype}`;
  }
  
  return contextSuffix ? `${type} ${contextSuffix}` : type;
};

/* A cat's purr has a fundamental around 20-40 Hz. The 220-520 Hz band we
   watch is the CRY embedded in a solicitation purr, not the purr itself.
   So a sound measured above this is not a purr, whatever it gets called —
   it is a meow, chirp or trill. Used to flag the identification against the
   measurement rather than letting one quietly overrule the other. */
const PURR_MAX_F0_HZ = 600;

/** Measured events carry seconds; the model's carry "m:ss". Show both as m:ss. */
const fmtClock = (t) => {
  const secs = typeof t === 'number' ? t : parseFloat(String(t).includes(':') ? NaN : t);
  if (Number.isNaN(secs) || secs === undefined || secs === null) return String(t ?? '—');
  return `${Math.floor(secs / 60)}:${String(Math.floor(secs % 60)).padStart(2, '0')}`;
};

function AudioWaveform({ events = [], environmentalSounds = [], duration = 30, currentTime = 0, isPlaying = false, onSeek, videoContext = '', envelope = null, measuredEvents = null }) {
  
  /* WHEN a sound happened is measured; WHAT it was is identified.
   *
   * The signal-processing service segments the audio by energy and returns
   * each event's real start, duration, fundamental frequency, tonality and
   * Morton reading. Those timings are the accurate ones, so the track is
   * built from them. Gemini's identifications are then matched onto the
   * nearest measured event by time — a name attached to a measurement,
   * rather than a name with a time the model chose.
   *
   * With no DSP (no ffmpeg/scipy) there are no measured events, and the
   * model's own list is used with its timings marked as estimated. */
  const parseTs = (ts) => {
    if (typeof ts === 'number') return ts;
    if (ts === null || ts === undefined || ts === '') return null;
    const parts = String(ts).split(':').map(Number);
    if (parts.length === 2 && parts.every((n) => !Number.isNaN(n))) return parts[0] * 60 + parts[1];
    const n = parseFloat(ts);
    return Number.isNaN(n) ? null : n;
  };

  const allEvents = useMemo(() => {
    const named = events.map((e) => ({ ...e, _t: parseTs(e.timestamp_start) }));
    const takeNearest = (tSec) => {
      let best = null, bestGap = Infinity;
      named.forEach((n) => {
        if (n._used || n._t === null) return;
        const gap = Math.abs(n._t - tSec);
        if (gap < bestGap) { best = n; bestGap = gap; }
      });
      // 2s is about the resolution the model works at when reading timestamps.
      if (best && bestGap <= 2) { best._used = true; return best; }
      return null;
    };

    let combined;
    if (Array.isArray(measuredEvents) && measuredEvents.length) {
      combined = measuredEvents.map((m) => {
        const match = takeNearest(m.timestamp_sec);
        return {
          timestamp_start: m.timestamp_sec,
          timestamp_end: m.timestamp_sec + (m.duration_sec || 0),
          type: match?.type || 'vocalization',
          subtype: match?.subtype,
          interpretation: match?.interpretation,
          measured: m,
          isMeasured: true,
        };
      });
      // Anything the model heard that no measured event lines up with is still
      // worth listing, but it is flagged as unlocated rather than given a bar.
      named.filter((n) => !n._used).forEach((n) => combined.push({ ...n, unmatched: true }));
    } else {
      combined = [...named];
    }

    environmentalSounds.forEach((es) => {
      combined.push({
        timestamp_start: es.timestamp,
        timestamp_end: es.timestamp,
        type: 'environmental',
        subtype: es.sound,
        interpretation: es.pet_reaction,
        isEnvironmental: true,
      });
    });

    return combined;
  }, [events, environmentalSounds, measuredEvents]);
  
  // Process events into time ranges
  const eventRanges = useMemo(() => {
    const parseTime = (ts) => {
      if (typeof ts === 'number') return ts;
      if (!ts) return 0;
      const str = String(ts);
      const parts = str.split(':').map(Number);
      if (parts.length === 2) return parts[0] * 60 + parts[1];
      return parseFloat(str) || 0;
    };

    const MIN_SPAN = 1.5;   // a marker you can actually see and click

    return allEvents.map(e => {
      const start = parseTime(e.timestamp_start);
      const rawEnd = parseTime(e.timestamp_end);
      // `end || start + 2` looked like a fallback but only fired when the end
      // parsed to zero. An event whose end EQUALS its start — which is most of
      // them — produced a zero-length range that no bar could ever fall inside,
      // so it painted nothing at all. Hence a list full of purrs above a
      // waveform showing none of them.
      const end = rawEnd > start ? rawEnd : start + MIN_SPAN;
      return {
      start,
      end,
      label: e.isEnvironmental ? `🔊 ${e.subtype}` : getContextualDescription(e, videoContext),
      interpretation: e.interpretation,
      zone: e.isEnvironmental ? 'yellow' : getVocalizationZone(e.type, e.subtype),
      loudness: e.isEnvironmental ? 0.5 :
                e.subtype?.toLowerCase().includes('aggressive') ? 1.0 :
                e.subtype?.toLowerCase().includes('demand') ? 0.85 :
                e.subtype?.toLowerCase().includes('frustrat') ? 0.8 : 0.65,
      original: e,
      isEnvironmental: e.isEnvironmental,
      timed: e.timestamp_start !== undefined && e.timestamp_start !== null
             && String(e.timestamp_start).length > 0,
      };
    })
    // An event with no timestamp used to default to 0 and paint a block over
    // the opening seconds that corresponded to nothing that happened there.
    .filter(r => r.timed);
  }, [allEvents, videoContext]);

  /* The bars are the REAL amplitude envelope, measured from the audio track by
     the signal-processing service and passed down as `envelope` (RMS per
     bucket, normalised to its own peak).

     They used to be Math.random() shaped by a sine wave. On a panel that also
     prints measured frequencies in Hz, drawing an invented waveform is the
     same failure as any other fabricated measurement — it just looks more like
     evidence. With no envelope we now draw a flat line and say so, rather than
     making one up. */
  const waveformBars = useMemo(() => {
    const bars = [];
    const hasReal = Array.isArray(envelope) && envelope.length > 1;
    const totalBars = hasReal ? envelope.length : 150;
    const barWidth = 100 / totalBars;

    for (let i = 0; i < totalBars; i++) {
      const t = (i / totalBars) * duration;
      const activeEvent = eventRanges.find(r => t >= r.start && t <= r.end);

      // Height is amplitude and nothing else. Colour is what the event was.
      const amp = hasReal ? envelope[i] : 0;
      const height = hasReal ? Math.max(2, amp * 92) : 2;
      const colors = activeEvent ? ZONE_COLORS[activeEvent.zone] : ZONE_COLORS.inactive;
      const isActive = Boolean(activeEvent);

      bars.push({
        index: i,
        left: `${i * barWidth}%`,
        width: `${Math.max(0.3, barWidth - 0.15)}%`, // Thinner bars with gaps
        height: Math.max(2, Math.min(92, height)),
        colors,
        isActive,
        time: t,
        event: activeEvent
      });
    }

    return bars;
  }, [duration, eventRanges, envelope]);

  const hasRealWaveform = Array.isArray(envelope) && envelope.length > 1;

  // Get unique event types for legend
  const eventTypes = useMemo(() => {
    const types = new Map();
    allEvents.forEach(e => {
      if (e.isEnvironmental) {
        if (!types.has('environmental')) {
          types.set('environmental', 'yellow');
        }
      } else {
        const key = e.subtype || e.type;
        if (key && !types.has(key)) {
          types.set(key, getVocalizationZone(e.type, e.subtype));
        }
      }
    });
    return Array.from(types.entries());
  }, [allEvents]);

  const handleBarClick = (time, event) => {
    if (event && onSeek) onSeek(event.start);
  };

  return (
    <div className="rounded-xl p-5" style={{ backgroundColor: 'rgba(255,255,255,0.05)' }}>
      <div className="flex items-center justify-between mb-4">
        <span className="font-roboto font-medium text-white">Audio Timeline</span>
        <span className="font-roboto text-white/50 text-sm">{Math.round(duration)}s</span>
      </div>
      
      {/* Refined Waveform */}
      <div 
        className="relative h-36 rounded-lg overflow-hidden"
        style={{ backgroundColor: 'rgba(0,0,0,0.4)' }}
      >
        {/* Center line */}
        <div className="absolute left-0 right-0 top-1/2 h-px bg-white/10"></div>
        
        {/* Waveform bars with gradient effect */}
        <div className="absolute inset-0 flex items-center">
          {waveformBars.map((bar) => (
            <div
              key={bar.index}
              className="absolute transition-all duration-50"
              style={{
                left: bar.left,
                width: bar.width,
                height: `${bar.height}%`,
                top: `${50 - bar.height / 2}%`,
                background: bar.isActive 
                  ? `linear-gradient(180deg, ${bar.colors.secondary} 0%, ${bar.colors.primary} 50%, ${bar.colors.secondary} 100%)`
                  : bar.colors.primary,
                opacity: bar.isActive ? 0.95 : 0.25,
                borderRadius: '1px',
                cursor: bar.isActive ? 'pointer' : 'default',
                boxShadow: bar.isActive ? `0 0 4px ${bar.colors.primary}40` : 'none'
              }}
              onClick={() => handleBarClick(bar.time, bar.event)}
              title={bar.event?.label}
            />
          ))}
        </div>
        
        {/* Playhead */}
        {isPlaying && (
          <div 
            className="absolute top-0 bottom-0 w-0.5 bg-white z-10"
            style={{ 
              left: `${(currentTime / duration) * 100}%`,
              boxShadow: '0 0 8px rgba(255,255,255,0.8)'
            }}
          />
        )}
        
        {/* Time markers */}
        <div className="absolute bottom-1 left-2 text-white/30 text-xs font-mono">0:00</div>
        <div className="absolute bottom-1 right-2 text-white/30 text-xs font-mono">
          {Math.floor(duration / 60)}:{String(Math.floor(duration % 60)).padStart(2, '0')}
        </div>
      </div>

      {!hasRealWaveform && (
        <p className="font-roboto text-white/40 text-xs mt-2">
          No waveform for this clip — the shape of the audio wasn't measured.
          Events below are still from the analysis.
        </p>
      )}

      {/* Legend */}
      {eventTypes.length > 0 && (
        <div className="flex flex-wrap gap-4 mt-4 pt-3 border-t border-white/10">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: ZONE_COLORS.inactive.primary, opacity: 0.4 }} />
            <span className="font-roboto text-white/40 text-xs">Ambient</span>
          </div>
          {eventTypes.map(([type, zone]) => (
            <div key={type} className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: ZONE_COLORS[zone].primary }} />
              <span className="font-roboto text-white/70 text-xs capitalize">{type.replace(/_/g, ' ')}</span>
            </div>
          ))}
        </div>
      )}
      
      {/* Event List */}
      {allEvents && allEvents.length > 0 && (
        <div className="mt-4 space-y-2">
          {allEvents.slice(0, 8).map((event, idx) => {
            const zone = event.isEnvironmental ? 'yellow' : getVocalizationZone(event.type, event.subtype);
            const colors = ZONE_COLORS[zone];
            const description = event.isEnvironmental ? `🔊 ${event.subtype}` : getContextualDescription(event, videoContext);
            
            return (
              <div 
                key={idx}
                className="flex items-start gap-3 p-3 rounded-lg cursor-pointer hover:bg-white/10 transition-colors"
                style={{ backgroundColor: 'rgba(255,255,255,0.05)', borderLeft: `3px solid ${colors.primary}` }}
                onClick={() => onSeek && onSeek(parseTs(event.timestamp_start) || 0)}
              >
                <span className="font-roboto text-white/50 text-xs font-mono whitespace-nowrap min-w-[40px]">
                  {fmtClock(event.timestamp_start)}
                </span>
                <div className="flex-1 min-w-0">
                  <span className="font-roboto text-white text-sm font-medium capitalize">
                    {description}
                  </span>
                  {event.unmatched && (
                    <span className="ml-2 font-roboto text-white/40 text-[10px] uppercase tracking-wide">
                      time estimated
                    </span>
                  )}

                  {/* Measured, and labelled as such — pitch, tonality and the
                      Morton reading come from signal processing, not the model. */}
                  {event.measured && (
                    <p className="font-roboto text-white/55 text-xs mt-1 font-mono">
                      {event.measured.pitch_hz != null
                        ? `${event.measured.pitch_hz} Hz`
                        : 'unvoiced'}
                      {event.measured.pitch_contour ? ` · ${event.measured.pitch_contour}` : ''}
                      {event.measured.tonality ? ` · ${event.measured.tonality}` : ''}
                      {event.measured.duration_sec ? ` · ${event.measured.duration_sec}s` : ''}
                      <span className="text-white/35"> · measured</span>
                    </p>
                  )}
                  {event.measured?.morton_inference && (
                    <p className="font-roboto text-white/45 text-xs mt-0.5">
                      {event.measured.morton_inference}
                    </p>
                  )}

                  {/* Where the name and the number disagree, say so. A purr has
                      a fundamental near 25 Hz; anything up at 1 kHz is a meow
                      or chirp however it is labelled. Reporting the conflict is
                      the rule everywhere else in this codebase. */}
                  {event.measured?.pitch_hz != null
                    && /purr/i.test(`${event.type || ''} ${event.subtype || ''}`)
                    && event.measured.pitch_hz > PURR_MAX_F0_HZ && (
                    <p className="font-roboto text-amber-200/90 text-xs mt-1">
                      Identified as a purr, but measured at {event.measured.pitch_hz} Hz —
                      a purr's fundamental is around 20–40 Hz, so this is more
                      likely a meow, chirp or trill. Both are shown; neither is
                      overruled.
                    </p>
                  )}

                  {event.interpretation && (
                    <p className="font-roboto text-white/50 text-xs mt-1">{event.interpretation}</p>
                  )}
                </div>
                <span className="px-2 py-0.5 rounded text-xs font-roboto font-medium"
                  style={{ backgroundColor: `${colors.primary}25`, color: colors.primary }}>
                  {zone === 'red' ? 'High' : zone === 'yellow' ? 'Med' : 'Low'}
                </span>
              </div>
            );
          })}
        </div>
      )}
      
      {(!allEvents || allEvents.length === 0) && (
        <p className="text-white/40 text-sm text-center mt-4 font-roboto">
          No vocalizations or notable sounds detected in this video
        </p>
      )}
      
      <p className="text-white/30 text-xs mt-4 font-roboto">
        Based on Morton's Motivation-Structural Rules and Canine Bio-Acoustics research
      </p>
    </div>
  );
}

export default AudioWaveform;
