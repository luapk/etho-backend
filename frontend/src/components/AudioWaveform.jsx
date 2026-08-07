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

function AudioWaveform({ events = [], environmentalSounds = [], duration = 30, currentTime = 0, isPlaying = false, onSeek, videoContext = '' }) {
  
  // Combine vocalizations and environmental sounds
  const allEvents = useMemo(() => {
    const combined = [...events];
    
    // Add environmental sounds as events too
    environmentalSounds.forEach(es => {
      combined.push({
        timestamp_start: es.timestamp,
        timestamp_end: es.timestamp,
        type: 'environmental',
        subtype: es.sound,
        interpretation: es.pet_reaction,
        isEnvironmental: true
      });
    });
    
    return combined;
  }, [events, environmentalSounds]);
  
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

    return allEvents.map(e => ({
      start: parseTime(e.timestamp_start),
      end: parseTime(e.timestamp_end) || parseTime(e.timestamp_start) + 2,
      label: e.isEnvironmental ? `🔊 ${e.subtype}` : getContextualDescription(e, videoContext),
      interpretation: e.interpretation,
      zone: e.isEnvironmental ? 'yellow' : getVocalizationZone(e.type, e.subtype),
      loudness: e.isEnvironmental ? 0.5 :
                e.subtype?.toLowerCase().includes('aggressive') ? 1.0 :
                e.subtype?.toLowerCase().includes('demand') ? 0.85 :
                e.subtype?.toLowerCase().includes('frustrat') ? 0.8 : 0.65,
      original: e,
      isEnvironmental: e.isEnvironmental
    }));
  }, [allEvents, videoContext]);

  // Generate refined waveform bars - more bars, thinner width
  const waveformBars = useMemo(() => {
    const bars = [];
    const totalBars = 150; // More bars for finer detail
    const barWidth = 100 / totalBars;
    
    for (let i = 0; i < totalBars; i++) {
      const t = (i / totalBars) * duration;
      const activeEvent = eventRanges.find(r => t >= r.start && t <= r.end);
      
      let height, colors, isActive;
      
      if (activeEvent) {
        const eventProgress = (t - activeEvent.start) / (activeEvent.end - activeEvent.start);
        
        // Envelope shaping for natural audio look
        let envelope;
        if (eventProgress < 0.1) envelope = eventProgress / 0.1;
        else if (eventProgress > 0.8) envelope = (1 - eventProgress) / 0.2;
        else envelope = 0.85 + Math.random() * 0.15;
        
        // Add harmonic variation for realistic waveform
        const harmonic1 = Math.sin(i * 1.2) * 0.1;
        const harmonic2 = Math.sin(i * 3.7) * 0.05;
        const noise = (Math.random() - 0.5) * 0.08;
        
        height = 25 + (activeEvent.loudness * envelope * 60) + ((harmonic1 + harmonic2 + noise) * 25);
        colors = ZONE_COLORS[activeEvent.zone];
        isActive = true;
      } else {
        // Ambient noise floor
        const baseNoise = 5 + Math.random() * 8;
        const microVariation = Math.sin(i * 0.5) * 2;
        height = baseNoise + microVariation;
        colors = ZONE_COLORS.inactive;
        isActive = false;
      }
      
      bars.push({
        index: i,
        left: `${i * barWidth}%`,
        width: `${Math.max(0.3, barWidth - 0.15)}%`, // Thinner bars with gaps
        height: Math.max(3, Math.min(92, height)),
        colors,
        isActive,
        time: t,
        event: activeEvent
      });
    }
    
    return bars;
  }, [duration, eventRanges]);

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
          {allEvents.slice(0, 5).map((event, idx) => {
            const zone = event.isEnvironmental ? 'yellow' : getVocalizationZone(event.type, event.subtype);
            const colors = ZONE_COLORS[zone];
            const description = event.isEnvironmental ? `🔊 ${event.subtype}` : getContextualDescription(event, videoContext);
            
            return (
              <div 
                key={idx}
                className="flex items-start gap-3 p-3 rounded-lg cursor-pointer hover:bg-white/10 transition-colors"
                style={{ backgroundColor: 'rgba(255,255,255,0.05)', borderLeft: `3px solid ${colors.primary}` }}
                onClick={() => {
                  const timeStr = event.timestamp_start || '0:00';
                  const parts = timeStr.split(':').map(Number);
                  const seconds = parts.length === 2 ? parts[0] * 60 + parts[1] : parseFloat(timeStr) || 0;
                  onSeek && onSeek(seconds);
                }}
              >
                <span className="font-roboto text-white/50 text-xs font-mono whitespace-nowrap min-w-[40px]">
                  {event.timestamp_start}
                </span>
                <div className="flex-1 min-w-0">
                  <span className="font-roboto text-white text-sm font-medium capitalize">{description}</span>
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
