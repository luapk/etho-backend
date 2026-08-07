import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Volume2, Eye, ChevronDown, ChevronUp, Download, AlertTriangle, MessageCircle, BookOpen, Subtitles, Lightbulb, Info, X, Sparkles, Volume1, VolumeX } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts';
import AudioWaveform from '../components/AudioWaveform';
import Footer from '../components/Footer';
import RatingWidget from '../components/RatingWidget';

const ZONE_CONFIG = {
  green: { label: 'LOW', color: '#22c55e', textClass: 'text-green-300' },
  yellow: { label: 'MODERATE', color: '#f59e0b', textClass: 'text-amber-300' },
  red: { label: 'ELEVATED', color: '#ef4444', textClass: 'text-red-300' }
};

/*
 * RESEARCH-BACKED BEHAVIORAL MARKER DATABASE
 * Each marker includes scientific explanation and what it means
 */
const MARKER_RESEARCH = {
  // Dog FACS Codes
  'EAD101': {
    name: 'Ears Forward',
    scientific: 'Ear Adductor 101 - forward ear positioning',
    meaning: 'Indicates alert attention and engagement with a stimulus. The dog is actively focusing on something of interest.',
    research: 'DogFACS (Waller et al., 2013)'
  },
  'EAD102': {
    name: 'Ears Adductor',
    scientific: 'Ear Adductor 102 - ears pulled together at top',
    meaning: 'Associated with positive anticipation and friendly engagement. Often seen during pleasant interactions.',
    research: 'DogFACS (Waller et al., 2013)'
  },
  'EAD103': {
    name: 'Ears Flattened',
    scientific: 'Ear Flattener - ears rotated back against head',
    meaning: 'Signals negative emotional state: fear, anxiety, frustration, or pain. Context determines which emotion dominates.',
    research: 'DogFACS (Waller et al., 2013)'
  },
  'AU145': {
    name: 'Rapid Blinking',
    scientific: 'Action Unit 145 - increased blink rate',
    meaning: 'Displacement behavior indicating stress or internal conflict. The dog is uncomfortable with the current situation.',
    research: 'DogFACS (Waller et al., 2013)'
  },
  'AD137': {
    name: 'Nose Licking',
    scientific: 'Action Descriptor 137 - tongue contacts nose/lips',
    meaning: 'Classic displacement behavior signaling anxiety or stress. Often appears before escalation of discomfort.',
    research: 'DogFACS (Waller et al., 2013)'
  },
  'AD19': {
    name: 'Tongue Show',
    scientific: 'Action Descriptor 19 - brief tongue protrusion',
    meaning: 'Subtle stress indicator, often missed by owners. Indicates mild discomfort or uncertainty.',
    research: 'DogFACS (Waller et al., 2013)'
  },
  // Common behavioral markers
  'Whale Eye': {
    name: 'Whale Eye',
    scientific: 'Visible sclera (white of eye) in crescent shape',
    meaning: 'Strong indicator of fear or anxiety. The dog is avoiding direct gaze while monitoring a perceived threat.',
    research: 'Canine Body Language Studies'
  },
  'Play Bow': {
    name: 'Play Bow',
    scientific: 'Front legs extended, rear elevated',
    meaning: 'Universal play invitation signal. Indicates the dog wants to engage in friendly play behavior.',
    research: 'Bekoff (1974) - Social Play in Canids'
  },
  'Tail Tucked': {
    name: 'Tail Tucked',
    scientific: 'Tail positioned under body between legs',
    meaning: 'Clear fear or submission signal. The dog feels threatened and is trying to appear non-threatening.',
    research: 'Canine Ethology'
  },
  'Piloerection': {
    name: 'Raised Hackles',
    scientific: 'Piloerection - involuntary hair raising',
    meaning: 'Indicates high arousal - can be excitement, fear, or aggression. Not always negative; context is key.',
    research: 'Autonomic Nervous System Response'
  },
  'Stress Yawning': {
    name: 'Stress Yawning',
    scientific: 'Yawn unrelated to fatigue',
    meaning: 'Displacement behavior indicating tension or anxiety. Often seen in uncomfortable social situations.',
    research: 'Beerda et al. (1998)'
  },
  'Soft Eyes': {
    name: 'Soft Eyes',
    scientific: 'Relaxed periocular muscles, partial lid closure',
    meaning: 'Indicates relaxation and contentment. The dog feels safe and comfortable in their environment.',
    research: 'DogFACS (Waller et al., 2013)'
  },
  // Cat FGS markers
  'FGS Ear Position': {
    name: 'Ear Position (FGS)',
    scientific: 'Feline Grimace Scale ear assessment',
    meaning: 'Flattened or rotated ears indicate pain or fear. Forward, upright ears suggest comfort.',
    research: 'Feline Grimace Scale (Evangelista et al., 2019)'
  },
  'FGS Orbital Tightening': {
    name: 'Orbital Tightening',
    scientific: 'Squinting or partially closed eyes',
    meaning: 'Key pain indicator in cats. Persistent orbital tightening suggests discomfort requiring attention.',
    research: 'Feline Grimace Scale (Evangelista et al., 2019)'
  },
  'FGS Muzzle Tension': {
    name: 'Muzzle Tension',
    scientific: 'Elliptical or flattened muzzle shape',
    meaning: 'Indicates facial muscle tension from pain or stress. Round, relaxed muzzle suggests comfort.',
    research: 'Feline Grimace Scale (Evangelista et al., 2019)'
  },
  'Slow Blink': {
    name: 'Slow Blink',
    scientific: 'Deliberate, slow eye closure and opening',
    meaning: 'Affiliative signal indicating trust and comfort. Often called a "cat kiss" - a positive communication.',
    research: 'Humphrey et al. (2020) - Cat-Human Communication'
  },
  // Vocalizations
  'Growl': {
    name: 'Growling',
    scientific: 'Low-frequency, sustained vocalization',
    meaning: 'Warning signal indicating the animal feels threatened. Respect this boundary to prevent escalation.',
    research: "Morton's Motivation-Structural Rules (1977)"
  },
  'Hiss': {
    name: 'Hissing',
    scientific: 'Explosive, high-pressure vocalization',
    meaning: 'Defensive warning mimicking snake sounds. The cat feels threatened and is demanding space.',
    research: "Morton's Rules & Feline Defensive Behavior"
  },
  'Whine': {
    name: 'Whining',
    scientific: 'High-pitched, tonal vocalization',
    meaning: 'Indicates frustration, anxiety, or solicitation. Rising pitch suggests request; sustained suggests distress.',
    research: 'Canine Bio-Acoustics (Pongrácz et al.)'
  }
};

// Helper to get marker research info
const getMarkerResearch = (marker, code) => {
  // Try code first, then marker name
  if (code && MARKER_RESEARCH[code]) return MARKER_RESEARCH[code];
  if (marker && MARKER_RESEARCH[marker]) return MARKER_RESEARCH[marker];
  
  // Fuzzy match
  const searchTerm = (marker || '').toLowerCase();
  for (const [key, value] of Object.entries(MARKER_RESEARCH)) {
    if (key.toLowerCase().includes(searchTerm) || value.name.toLowerCase().includes(searchTerm)) {
      return value;
    }
  }
  
  return null;
};

/*
 * PET POV DISPLAY
 * The AI generates unique, context-specific interpretations.
 * We display them DIRECTLY - no client-side override or stock phrases.
 * The quality of these depends entirely on the backend prompt.
 */

// Helper to get the pet's interpretation text from various API response formats
const getPetPovText = (line) => {
  // New format: pet_pov field
  if (line.pet_pov) return line.pet_pov;
  // Legacy format: first_person_interpretation
  if (line.first_person_interpretation) return line.first_person_interpretation;
  // Fallback
  return line.interpretation || line.text || '';
};

// Behavioral markers library
const MARKERS_LIBRARY = {
  dog: {
    stress: [
      { text: 'Whale Eye', zone: 'red', desc: 'Visible sclera - fear indicator' },
      { text: 'Lip Licking', zone: 'yellow', desc: 'Displacement behavior AD137' },
      { text: 'Stress Yawning', zone: 'yellow', desc: 'Non-fatigue tension yawn' },
      { text: 'Ears Flattened', zone: 'red', desc: 'EAD103 negative valence' },
      { text: 'Body Tense', zone: 'yellow', desc: 'Rigid arousal posture' },
      { text: 'Tail Tucked', zone: 'red', desc: 'Fear/submission signal' },
      { text: 'Panting', zone: 'yellow', desc: 'Stress-related breathing' },
      { text: 'Low Posture', zone: 'red', desc: 'Defensive position' },
      { text: 'Averted Gaze', zone: 'yellow', desc: 'Conflict avoidance' }
    ],
    alert: [
      { text: 'Ears Forward', zone: 'yellow', desc: 'EAD101 alert attention' },
      { text: 'Hard Stare', zone: 'yellow', desc: 'Fixed gaze on stimulus' },
      { text: 'Tail High', zone: 'yellow', desc: 'Aroused posture' },
      { text: 'Raised Hackles', zone: 'yellow', desc: 'Piloerection arousal' },
      { text: 'Weight Forward', zone: 'yellow', desc: 'Engaged posture' },
      { text: 'Closed Mouth', zone: 'yellow', desc: 'Focused state' }
    ],
    relaxed: [
      { text: 'Soft Eyes', zone: 'green', desc: 'Relaxed facial muscles' },
      { text: 'Loose Body', zone: 'green', desc: 'No tension' },
      { text: 'Tail Relaxed', zone: 'green', desc: 'Natural position' },
      { text: 'Open Mouth', zone: 'green', desc: 'Relaxed breathing' },
      { text: 'Play Bow', zone: 'green', desc: 'Play invitation' }
    ]
  },
  cat: {
    stress: [
      { text: 'Ears Flat', zone: 'red', desc: 'Defensive posture (FGS)' },
      { text: 'Dilated Pupils', zone: 'red', desc: 'Fear response' },
      { text: 'Tail Puffed', zone: 'red', desc: 'Piloerection fear' },
      { text: 'Back Arched', zone: 'red', desc: 'Defensive posture' },
      { text: 'Whiskers Back', zone: 'red', desc: 'Fear indicator' },
      { text: 'Crouching', zone: 'red', desc: 'Fear position' },
      { text: 'Frozen Stance', zone: 'red', desc: 'Fear immobility' }
    ],
    alert: [
      { text: 'Ears Forward', zone: 'yellow', desc: 'Alert attention' },
      { text: 'Tail Twitching', zone: 'yellow', desc: 'Agitation' },
      { text: 'Whiskers Forward', zone: 'yellow', desc: 'Hunting mode' },
      { text: 'Focused Stare', zone: 'yellow', desc: 'Predatory focus' }
    ],
    relaxed: [
      { text: 'Slow Blink', zone: 'green', desc: 'Trust signal' },
      { text: 'Kneading', zone: 'green', desc: 'Contentment' },
      { text: 'Purring', zone: 'green', desc: 'Self-soothing' },
      { text: 'Tail Up', zone: 'green', desc: 'Friendly greeting' },
      { text: 'Soft Eyes', zone: 'green', desc: 'Relaxed state' }
    ]
  }
};

const BREED_NOTES = {
  'pug': ['Brachycephalic Baseline', 'Breathing Normal'],
  'french bulldog': ['Brachycephalic Baseline', 'Breathing Normal'],
  'bulldog': ['Brachycephalic Baseline', 'Breathing Normal'],
  'shiba inu': ['Curled Tail Normal', 'Spitz Baseline'],
  'akita': ['Curled Tail Normal', 'Breed Reserve'],
  'husky': ['Curled Tail Normal', 'High Energy'],
  'german shepherd': ['Working Drive', 'High Alert Normal'],
  'belgian malinois': ['Working Drive', 'High Alert Normal'],
  'border collie': ['Herding Intensity', 'High Focus'],
  'greyhound': ['Athletic Heart', 'Sighthound Build'],
  'persian': ['Brachycephalic Cat', 'Low Activity'],
  'siamese': ['Vocal Breed', 'High Activity'],
  'scottish fold': ['Folded Ears Baseline']
};

// Breed facts
const BREED_FACTS = {
  'german shepherd': ["German Shepherds were the first guide dogs for the blind, with Buddy leading Morris Frank in 1928. (Source: AKC)", "During WWI, German Shepherds served as Red Cross dogs and messengers. (Source: Military Working Dog Foundation)", "A German Shepherd can learn a new command in under 5 repetitions. (Source: Stanley Coren)"],
  'labrador retriever': ["Labs were originally 'St. John's Dogs' working with Newfoundland fishermen. (Source: LRC)", "Labs have been America's most popular breed for 31 consecutive years. (Source: AKC)", "A Lab's nose has 300 million scent receptors. (Source: Medical Detection Dogs)"],
  'golden retriever': ["Goldens can carry a raw egg without breaking it. (Source: GRCA)", "The first three AKC Obedience Champions were Golden Retrievers. (Source: AKC)", "Lord Tweedmouth developed the breed in 1860s Scotland. (Source: The Kennel Club)"],
  'french bulldog': ["Frenchies can't swim due to their front-heavy build. (Source: FBDCA)", "French Bulldogs communicate through yawns, yips, and gargles. (Source: AKC)", "In 2022, Frenchies surpassed Labs as America's most popular breed. (Source: AKC)"],
  'beagle': ["Beagles have 220 million scent receptors. The USDA employs 'Beagle Brigades'. (Source: USDA)", "Queen Elizabeth I kept 'Pocket Beagles' only 8-9 inches tall. (Source: National Beagle Club)", "Snoopy has appeared in over 17,897 comic strips. (Source: Schulz Museum)"],
  'belgian malinois': ["Malinois are the preferred breed for military K-9 units. Cairo was part of SEAL Team 6. (Source: US Navy)", "They can jump fences over 8 feet high. (Source: ABMC)", "Their bite force of 195 PSI makes them top apprehension dogs. (Source: Police K-9 Magazine)"],
  'siamese': ["Siamese color points are temperature-sensitive albinism. (Source: CFA)", "Two Siamese cats detected a concealed microphone in the Dutch Embassy. (Source: CIA Archives)", "They were sacred temple cats in Siam. (Source: Siamese Cat Association)"],
  'maine coon': ["Maine Coons can weigh 25+ pounds. (Source: MCBFA)", "Stewie holds the record for longest cat at 48.5 inches. (Source: Guinness)", "They're one of few cats that enjoy water. (Source: CFA)"]
};

const getBreedFact = (breed, species) => {
  if (!breed) {
    const generic = species === 'cat' 
      ? ["Cats spend 70% of their lives sleeping. (Source: Sleep Medicine Reviews)", "A cat's purr vibrates at 25-150 Hz—frequencies that promote healing. (Source: J Acoustical Society)", "Cats can jump 6x their length. (Source: Journal of Anatomy)"]
      : ["Dogs have been companions for 15,000+ years. (Source: Science)", "Dogs understand up to 250 words. (Source: APA)", "A dog's smell is 10,000-100,000x more sensitive than humans. (Source: PBS Nova)"];
    return generic[Math.floor(Math.random() * generic.length)];
  }
  const lower = breed.toLowerCase();
  for (const [key, facts] of Object.entries(BREED_FACTS)) {
    if (lower.includes(key) || key.includes(lower)) return facts[Math.floor(Math.random() * facts.length)];
  }
  return getBreedFact(null, species);
};

const getBehaviorZone = (text) => {
  const l = (text || '').toLowerCase();
  if (l.includes('stress') || l.includes('fear') || l.includes('distress') || l.includes('aggressive') || l.includes('growl') || l.includes('hiss') || l.includes('flat') || l.includes('tuck') || l.includes('whale')) return 'red';
  if (l.includes('alert') || l.includes('bark') || l.includes('whine') || l.includes('tense') || l.includes('forward') || l.includes('demand') || l.includes('meow')) return 'yellow';
  if (l.includes('relax') || l.includes('calm') || l.includes('play') || l.includes('soft') || l.includes('purr') || l.includes('loose')) return 'green';
  return 'neutral';
};

const parseTimestamp = (ts) => {
  if (!ts) return 0;
  const parts = ts.split(':').map(Number);
  return parts.length === 2 ? parts[0] * 60 + parts[1] : parseFloat(ts) || 0;
};

const CustomTooltip = ({ active, payload }) => {
  if (active && payload?.[0]?.payload?.marker) {
    const d = payload[0].payload;
    const eventTypeLabel = d.eventType === 'environmental' ? '🔊' : d.eventType === 'audio' ? '🎵' : '👁️';
    return (
      <div className="glass-card p-3 rounded-lg max-w-[200px]">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm">{eventTypeLabel}</span>
          <span className="w-3 h-3 rounded-full" style={{ backgroundColor: ZONE_CONFIG[d.markerZone]?.color || '#94a3b8' }}></span>
        </div>
        <p className="text-white/90 text-sm font-roboto font-medium">{d.marker}</p>
        {d.evidence?.length > 0 && (
          <p className="text-white/50 text-xs mt-1">{d.evidence.slice(0,2).join(', ')}</p>
        )}
      </div>
    );
  }
  return null;
};

const MarkerDot = ({ cx, cy, payload, onClick }) => {
  if (!payload?.marker) return null;
  return (
    <circle cx={cx} cy={cy} r={10} fill={ZONE_CONFIG[payload.markerZone]?.color || '#94a3b8'}
      stroke="rgba(255,255,255,0.9)" strokeWidth={2}
      style={{ cursor: 'pointer', filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.4))' }}
      onClick={() => onClick?.(payload.timeSeconds)} />
  );
};

const DistressInfoModal = ({ isOpen, onClose }) => {
  if (!isOpen) return null;
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-6" onClick={onClose}>
      <motion.div initial={{ scale: 0.9 }} animate={{ scale: 1 }} className="glass-card rounded-2xl p-6 max-w-md w-full" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between mb-4">
          <h3 className="font-roboto font-bold text-xl text-white">Understanding the Distress Score</h3>
          <button onClick={onClose} className="text-white/50 hover:text-white"><X className="w-5 h-5" /></button>
        </div>
        <div className="space-y-3 text-white/80 text-sm">
          <p>The score (0-100) analyzes multiple behavioral signals against research frameworks.</p>
          <div className="space-y-2">
            <div className="flex items-center gap-3"><span className="w-4 h-4 rounded-full bg-green-500"></span><span><b className="text-white">0-33:</b> Relaxed, comfortable</span></div>
            <div className="flex items-center gap-3"><span className="w-4 h-4 rounded-full bg-amber-500"></span><span><b className="text-white">34-66:</b> Alert, mildly aroused</span></div>
            <div className="flex items-center gap-3"><span className="w-4 h-4 rounded-full bg-red-500"></span><span><b className="text-white">67-100:</b> Stress or discomfort</span></div>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
};

// Behavioral Marker Modal Component
const MarkerInfoModal = ({ marker, onClose }) => {
  if (!marker) return null;
  const research = getMarkerResearch(marker.text, marker.code);
  
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-6" onClick={onClose}>
      <motion.div initial={{ scale: 0.9 }} animate={{ scale: 1 }} className="glass-card rounded-2xl p-6 max-w-md w-full" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-start mb-4">
          <div>
            <h3 className="font-roboto font-bold text-xl text-white">{marker.code || marker.text}</h3>
            {research && <p className="text-white/50 text-sm">{research.scientific}</p>}
          </div>
          <button onClick={onClose} className="text-white/50 hover:text-white"><X className="w-5 h-5" /></button>
        </div>
        <div className="space-y-3">
          {research ? (
            <>
              <p className="text-white/90 text-sm leading-relaxed">{research.meaning}</p>
              <div className="pt-3 border-t border-white/10">
                <p className="text-white/40 text-xs">Research: {research.research}</p>
              </div>
            </>
          ) : (
            <p className="text-white/70 text-sm">
              {marker.text} was observed at {marker.timestamp}. This behavioral signal contributes to our overall assessment of your pet's emotional state.
            </p>
          )}
          {marker.timestamp && (
            <p className="text-cyan-400 text-xs">Observed at {marker.timestamp}</p>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
};

function Dashboard({ analysisData, videoUrl }) {
  const [expandedSections, setExpandedSections] = useState({ audio: true, interpret: true, didyouknow: true, research: false });
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [subtitlesEnabled, setSubtitlesEnabled] = useState(true);
  const [audioEnabled, setAudioEnabled] = useState(false);
  const [currentSubtitle, setCurrentSubtitle] = useState(null);
  const [isGeneratingPDF, setIsGeneratingPDF] = useState(false);
  const [showDistressInfo, setShowDistressInfo] = useState(false);
  const [selectedMarker, setSelectedMarker] = useState(null);
  const videoRef = useRef(null);
  const speechSynthRef = useRef(null);

  // Text-to-speech
  const speak = useCallback((text) => {
    if (!audioEnabled || !window.speechSynthesis) return;
    
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.9;
    utterance.pitch = 1.1;
    utterance.volume = 0.8;
    window.speechSynthesis.speak(utterance);
  }, [audioEnabled]);

  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    const onTime = () => setCurrentTime(v.currentTime);
    const onDur = () => setDuration(v.duration);
    const onPlay = () => setIsPlaying(true);
    const onPause = () => { setIsPlaying(false); window.speechSynthesis?.cancel(); };
    v.addEventListener('timeupdate', onTime);
    v.addEventListener('durationchange', onDur);
    v.addEventListener('play', onPlay);
    v.addEventListener('pause', onPause);
    return () => { v.removeEventListener('timeupdate', onTime); v.removeEventListener('durationchange', onDur); v.removeEventListener('play', onPlay); v.removeEventListener('pause', onPause); };
  }, []);

  // Subtitle sync with Umwelt-based translations
  useEffect(() => {
    if (!subtitlesEnabled || !analysisData?.interpret_lines) { 
      setCurrentSubtitle(null); 
      return; 
    }
    
    const { species, video_context } = analysisData;
    
    for (let i = analysisData.interpret_lines.length - 1; i >= 0; i--) {
      const line = analysisData.interpret_lines[i];
      const parts = (line.timestamp || '0:00').split(':').map(Number);
      const lineTime = parts.length === 2 ? parts[0] * 60 + parts[1] : parseFloat(line.timestamp) || 0;
      
      if (currentTime >= lineTime && currentTime < lineTime + 4) {
        const zone = line.zone || getBehaviorZone(getPetPovText(line));
        
        // Use AI-generated interpretation directly - no client-side override
        const petPovText = getPetPovText(line);
        
        const newSubtitle = { 
          text: petPovText,
          zone,
          key: `${lineTime}-${i}`
        };
        
        // Only update if different (prevents re-speaking)
        if (!currentSubtitle || currentSubtitle.key !== newSubtitle.key) {
          setCurrentSubtitle(newSubtitle);
          speak(petPovText);
        }
        return;
      }
    }
    setCurrentSubtitle(null);
  }, [currentTime, subtitlesEnabled, analysisData, speak]);

  const handleMarkerClick = useCallback((t) => { if (videoRef.current) { videoRef.current.currentTime = t; videoRef.current.play(); } }, []);

  if (analysisData?.error && analysisData?.error_type === "no_pet_detected") {
    return (<div className="min-h-screen flex items-center justify-center p-6"><div className="glass-card p-8 max-w-md text-center rounded-2xl">
      <AlertTriangle className="w-16 h-16 text-amber-400 mx-auto mb-4" /><h2 className="text-white text-2xl font-bold mb-2">No Pet Detected</h2>
      <p className="text-white/80">{analysisData.message}</p></div></div>);
  }
  if (!analysisData) return <div className="min-h-screen flex items-center justify-center"><p className="text-white/60">No analysis data</p></div>;

  const { overall_assessment, visual_analysis, audio_analysis, timeline, interpret_lines, advisory, species, breed_detected, breed_confidence, video_context, video_type } = analysisData;
  const distressScore = overall_assessment?.distress_score || 50;
  const zone = distressScore <= 33 ? 'green' : distressScore <= 66 ? 'yellow' : 'red';
  const zoneConfig = ZONE_CONFIG[zone];
  const zoneLabel = overall_assessment?.zone_label || zoneConfig.label;
  const toggleSection = (s) => setExpandedSections(p => ({ ...p, [s]: !p[s] }));

  const chartData = useMemo(() => {
    const total = duration || 17, points = [], markers = [];
    
    // Source 1: Timeline from API
    timeline?.forEach(t => {
      const parts = (t.timestamp || '0:00').split(':').map(Number);
      const timeSeconds = parts.length === 2 ? parts[0]*60+parts[1] : parseFloat(t.timestamp)||0;
      const label = t.event_description || t.event || t.context_tag || t.observation;
      const eventType = t.event_type || 'behavioral';
      if (label) {
        markers.push({ 
          time: timeSeconds, 
          label: label, 
          eventType: eventType,
          score: t.distress_score || distressScore, 
          zone: t.zone || getBehaviorZone(label),
          evidence: t.evidence || []
        });
      }
    });
    
    // Source 2: Interpret lines (Pet POV moments)
    interpret_lines?.forEach(line => {
      const parts = (line.timestamp || '0:00').split(':').map(Number);
      const timeSeconds = parts.length === 2 ? parts[0]*60+parts[1] : parseFloat(line.timestamp)||0;
      const label = line.trigger || getPetPovText(line);
      const existingMarker = markers.find(m => Math.abs(m.time - timeSeconds) < 1);
      if (!existingMarker && label) {
        markers.push({
          time: timeSeconds,
          label: label,
          eventType: 'behavioral',
          score: line.zone === 'red' ? 75 : line.zone === 'yellow' ? 50 : 25,
          zone: line.zone || 'yellow',
          evidence: []
        });
      }
    });
    
    // Source 3: Audio vocalizations
    audio_analysis?.vocalizations_detected?.forEach(v => {
      const parts = (v.timestamp_start || '0:00').split(':').map(Number);
      const timeSeconds = parts.length === 2 ? parts[0]*60+parts[1] : parseFloat(v.timestamp_start)||0;
      const label = `${v.type}${v.subtype ? ': ' + v.subtype : ''}`;
      const existingMarker = markers.find(m => Math.abs(m.time - timeSeconds) < 1);
      if (!existingMarker) {
        markers.push({
          time: timeSeconds,
          label: label,
          eventType: 'audio',
          score: v.type?.toLowerCase().includes('growl') || v.type?.toLowerCase().includes('hiss') ? 70 : 45,
          zone: getBehaviorZone(label),
          evidence: [v.interpretation || '']
        });
      }
    });
    
    // Source 4: Key behavioral moments from visual analysis
    visual_analysis?.key_behavioral_moments?.forEach(m => {
      const parts = (m.timestamp || '0:00').split(':').map(Number);
      const timeSeconds = parts.length === 2 ? parts[0]*60+parts[1] : parseFloat(m.timestamp)||0;
      const existingMarker = markers.find(mk => Math.abs(mk.time - timeSeconds) < 1);
      if (!existingMarker && m.behavior) {
        markers.push({
          time: timeSeconds,
          label: m.behavior,
          eventType: 'behavioral',
          score: distressScore,
          zone: getBehaviorZone(m.behavior),
          evidence: [m.significance || '']
        });
      }
    });
    
    // If still no markers, create synthetic ones from FACS codes
    if (markers.length === 0 && visual_analysis?.facs_codes_detected?.length > 0) {
      visual_analysis.facs_codes_detected.forEach(f => {
        const parts = (f.timestamp || '0:00').split(':').map(Number);
        const timeSeconds = parts.length === 2 ? parts[0]*60+parts[1] : parseFloat(f.timestamp)||0;
        markers.push({
          time: timeSeconds,
          label: `${f.code}: ${f.description}`,
          eventType: 'behavioral',
          score: f.valence === 'negative' ? 60 : f.valence === 'positive' ? 25 : 45,
          zone: f.valence === 'negative' ? 'red' : f.valence === 'positive' ? 'green' : 'yellow',
          evidence: [f.code]
        });
      });
    }
    
    markers.sort((a,b) => a.time - b.time);
    
    // Build chart points
    for (let i = 0; i <= total * 2; i++) {
      const t = i / 2, timeLabel = `${Math.floor(t/60)}:${String(Math.floor(t%60)).padStart(2,'0')}`;
      const nearby = markers.filter(m => Math.abs(m.time - t) < 2);
      let score = nearby.length > 0 ? nearby.reduce((s,m) => s + m.score, 0) / nearby.length + Math.sin(i*0.3)*5 : distressScore + Math.sin(i*0.2)*3;
      const exact = markers.find(m => Math.abs(m.time - t) < 0.5);
      points.push({ 
        time: timeLabel, 
        timeSeconds: t, 
        score: Math.round(Math.max(5, Math.min(95, score))), 
        marker: exact?.label || null, 
        markerZone: exact?.zone || null,
        eventType: exact?.eventType || null,
        evidence: exact?.evidence || []
      });
    }
    return points;
  }, [duration, distressScore, timeline, interpret_lines, audio_analysis, visual_analysis]);

  // Only show behavioral markers that are verified from the API response
  const behaviorMarkers = useMemo(() => {
    // First, check if API returned verified behavioral_markers
    const apiMarkers = analysisData?.behavioral_markers?.filter(m => m.verified !== false) || [];
    if (apiMarkers.length > 0) {
      return apiMarkers.map(m => ({
        text: m.marker,
        code: m.code,
        zone: m.zone || 'yellow',
        desc: m.code ? `${m.code} at ${m.timestamp}` : m.timestamp,
        timestamp: m.timestamp
      }));
    }
    
    // Fallback: derive from facs_codes_detected (these should be verified)
    const markers = [];
    const matched = new Set();
    
    // Use FACS codes that were actually detected with timestamps
    visual_analysis?.facs_codes_detected?.forEach(f => {
      if (!matched.has(f.code)) {
        matched.add(f.code);
        markers.push({
          text: f.description || f.code,
          code: f.code,
          zone: f.valence === 'positive' ? 'green' : f.valence === 'negative' ? 'red' : 'yellow',
          desc: `${f.code}${f.timestamp ? ` at ${f.timestamp}` : ''}${f.confidence ? ` (${f.confidence} confidence)` : ''}`,
          timestamp: f.timestamp
        });
      }
    });
    
    return markers.slice(0, 8);
  }, [analysisData, visual_analysis]);

  const summary = useMemo(() => {
    let base = overall_assessment?.summary || `${video_context ? `While in a ${video_context.toLowerCase()}, your` : 'Your'} ${species || 'pet'} shows ${zone === 'green' ? 'calm, relaxed behavior' : zone === 'yellow' ? 'alert, attentive behavior' : 'signs of distress'}.`;
    if (video_type === 'compilation' && !base.includes('compilation')) base += ' This compilation shows multiple moments.';
    return base;
  }, [overall_assessment, video_context, species, zone, video_type]);

  const recommendation = useMemo(() => {
    const pet = species || 'pet', ctx = (video_context || '').toLowerCase();
    if (advisory?.detailed_recommendations?.length) return advisory.detailed_recommendations[0];
    if (zone === 'red') {
      if (ctx.includes('interact') || ctx.includes('close') || ctx.includes('camera')) return `Immediately cease the interaction and provide the ${pet} with space. These signals clearly communicate feeling threatened.`;
      if (ctx.includes('door') || ctx.includes('barrier')) return `The intensity suggests gradual desensitization training with a certified behaviorist would help.`;
      return `I'm seeing genuine discomfort signals. A veterinary behaviorist consultation would help rule out underlying causes and create a support plan.`;
    }
    if (zone === 'yellow') {
      if (ctx.includes('play')) return `Spirited energy! Watch their signals to ensure play stays fun. Brief calm-down breaks work wonders.`;
      return `Your ${pet} is alert and engaged. This is normal in many contexts, though relaxation protocols could help if this is their baseline.`;
    }
    return `Your ${pet} looks wonderfully content. The relaxed signals show they feel safe. Whatever you're doing, it's working!`;
  }, [zone, species, video_context, advisory]);

  const breedFact = useMemo(() => getBreedFact(breed_detected, species), [breed_detected, species]);
  const breedDisplay = useMemo(() => {
    if (!breed_detected) return null;
    const conf = breed_confidence || visual_analysis?.breed_confidence;
    return conf ? `${breed_detected} (${typeof conf === 'number' ? Math.round(conf*100)+'%' : conf} confident)` : breed_detected;
  }, [breed_detected, breed_confidence, visual_analysis]);

  const handleDownloadPDF = async () => {
    setIsGeneratingPDF(true);
    try {
      const markersHtml = behaviorMarkers.map(m => `<span style="display:inline-block;padding:6px 16px;margin:4px;border-radius:20px;background:${ZONE_CONFIG[m.zone]?.color||'#94a3b8'}22;border:1px solid ${ZONE_CONFIG[m.zone]?.color||'#94a3b8'};color:${ZONE_CONFIG[m.zone]?.color||'#94a3b8'}">${m.text}</span>`).join('');
      const html = `<!DOCTYPE html><html><head><title>Etho Report</title><style>body{font-family:sans-serif;max-width:800px;margin:0 auto;padding:40px}.header{text-align:center;border-bottom:2px solid #3b82f6;padding-bottom:20px;margin-bottom:30px}.score{display:inline-block;width:100px;height:100px;border:4px solid ${zoneConfig.color};border-radius:16px;text-align:center;padding-top:20px}.score-num{font-size:48px;font-weight:900;color:${zoneConfig.color}}</style></head><body><div class="header"><h1 style="color:#3b82f6">ETHO</h1><p>Pet Behavior Analysis Report - ${new Date().toLocaleDateString()}</p></div><div style="display:flex;gap:20px;margin-bottom:30px"><div class="score"><div class="score-num">${distressScore}</div><div>${zoneLabel}</div></div><div style="flex:1"><p style="color:${zoneConfig.color};font-weight:bold">${zoneLabel} DISTRESS • ${species||'Pet'} ${breedDisplay ? '• '+breedDisplay : ''}</p><p>${summary}</p><p><b>Recommendation:</b> ${recommendation}</p></div></div><h3>Behavioral Markers</h3><div>${markersHtml}</div>${breedFact ? `<h3>Did You Know?</h3><p>${breedFact}</p>` : ''}<hr style="margin-top:40px"><p style="text-align:center;color:#999;font-size:11px">Etho v3.0 • Not a substitute for veterinary advice</p></body></html>`;
      const blob = new Blob([html], { type: 'text/html' });
      const win = window.open(URL.createObjectURL(blob), '_blank');
      win.onload = () => win.print();
    } finally { setIsGeneratingPDF(false); }
  };

  return (
    <div className="min-h-screen">
      <DistressInfoModal isOpen={showDistressInfo} onClose={() => setShowDistressInfo(false)} />
      <AnimatePresence>
        {selectedMarker && <MarkerInfoModal marker={selectedMarker} onClose={() => setSelectedMarker(null)} />}
      </AnimatePresence>
      <header className="py-6 px-6"><div className="max-w-5xl mx-auto flex flex-col items-center">
        <img src="/etho-logo.png" alt="Etho" className="h-10" onError={(e) => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'block'; }} />
        <span className="font-roboto font-bold text-3xl text-white hidden">Etho</span>
        <p className="font-roboto text-white/60 text-sm mt-2">AI-powered pet behavior analysis</p>
      </div></header>

      <div className="max-w-5xl mx-auto px-6 pb-12 space-y-6">
        {/* Video with enhanced subtitles */}
        {videoUrl && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="glass-card rounded-2xl overflow-hidden">
            <div className="relative">
              <video ref={videoRef} src={videoUrl} controls className="w-full" style={{ maxHeight: '450px', objectFit: 'contain', backgroundColor: 'rgba(0,0,0,0.3)' }} />
              
              {/* Enhanced subtitle - black bg, colored border, 30% bigger */}
              <AnimatePresence mode="wait">
                {subtitlesEnabled && currentSubtitle && (
                  <motion.div 
                    key={currentSubtitle.key}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    transition={{ duration: 0.3, ease: 'easeOut' }}
                    className="absolute bottom-16 left-1/2 -translate-x-1/2 px-4 py-2 rounded-lg max-w-[80%] text-center"
                    style={{ 
                      backgroundColor: 'rgba(0,0,0,0.85)',
                      border: `2px solid ${ZONE_CONFIG[currentSubtitle.zone]?.color || '#fff'}`,
                      boxShadow: `0 0 20px ${ZONE_CONFIG[currentSubtitle.zone]?.color}40`
                    }}
                  >
                    <p className="font-roboto text-white text-sm font-medium italic">
                      "{currentSubtitle.text}"
                    </p>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
            
            {/* Subtitle toggle - slider on left */}
            <div className="p-4 flex items-center justify-between border-t border-white/10">
              <div className="flex items-center gap-3">
                {/* Slider Toggle - fixed overflow */}
                <button
                  onClick={() => setSubtitlesEnabled(!subtitlesEnabled)}
                  className={`relative w-11 h-6 rounded-full transition-colors duration-200 flex-shrink-0 ${
                    subtitlesEnabled ? 'bg-cyan-500' : 'bg-white/20'
                  }`}
                >
                  <span 
                    className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200 ${
                      subtitlesEnabled ? 'translate-x-5' : 'translate-x-0'
                    }`}
                  />
                </button>
                <Subtitles className="w-5 h-5 text-white/70" />
                <span className="font-roboto text-white text-sm">Pet Subtitles</span>
              </div>
              <button
                onClick={() => setAudioEnabled(!audioEnabled)}
                className={`p-2 rounded-full transition-colors ${
                  audioEnabled ? 'bg-cyan-500/30 text-cyan-300' : 'bg-white/10 text-white/50'
                }`}
                title={audioEnabled ? 'Mute voice' : 'Enable voice'}
              >
                {audioEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
              </button>
            </div>
          </motion.div>
        )}

        {/* Inter-species Warning Banner */}
        {analysisData?._interaction_type === 'inter_species' && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} 
            className="glass-card rounded-2xl p-4 border-2 border-amber-500/50" 
            style={{ backgroundColor: 'rgba(245, 158, 11, 0.1)' }}>
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-6 h-6 text-amber-400 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="font-roboto font-bold text-amber-300 mb-1">Inter-Species Interaction Detected</h3>
                <p className="text-white/80 text-sm">
                  This video shows your pet interacting with other animals. 
                  {analysisData?.advisory?.predator_prey_warning && (
                    <span className="text-amber-300"> Predator-prey dynamics may be present - monitor closely for the safety of all animals.</span>
                  )}
                </p>
                {analysisData?._verified_scene?.other_animals_present?.length > 0 && (
                  <p className="text-white/50 text-xs mt-2">
                    Other animals detected: {analysisData._verified_scene.other_animals_present.map(a => a.type || a.description).join(', ')}
                  </p>
                )}
              </div>
            </div>
          </motion.div>
        )}

        {/* Assessment Panel */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="glass-card rounded-2xl overflow-hidden">
          <div className="px-6 py-3 flex items-center gap-3 border-b border-white/10" style={{ backgroundColor: `${zoneConfig.color}12` }}>
            <span className="w-2.5 h-2.5 rounded-full animate-pulse" style={{ backgroundColor: zoneConfig.color }}></span>
            <span className="font-roboto font-bold text-sm uppercase tracking-wider" style={{ color: zoneConfig.color }}>{zoneLabel} Distress</span>
            <span className="text-white/30">•</span>
            <span className="text-white/70 text-sm">{species && species.charAt(0).toUpperCase() + species.slice(1)}{breedDisplay && ` • ${breedDisplay}`}</span>
          </div>
          <div className="p-6">
            <div className="flex flex-col lg:flex-row gap-6">
              <div className="flex flex-col items-center lg:items-start">
                <div className="w-24 h-24 rounded-xl border-2 flex flex-col items-center justify-center" style={{ borderColor: zoneConfig.color, backgroundColor: `${zoneConfig.color}10` }}>
                  <span className="font-roboto font-black text-4xl" style={{ color: zoneConfig.color }}>{distressScore}</span>
                  <span className="font-roboto text-[10px] uppercase tracking-wider text-white/60">{zoneLabel}</span>
                </div>
                <button onClick={() => setShowDistressInfo(true)} className="mt-2 flex items-center gap-1 text-white/40 hover:text-white/70 text-xs">
                  <Info className="w-3.5 h-3.5" />What's this?
                </button>
              </div>
              <div className="flex-1 space-y-4">
                <p className="font-roboto text-white leading-relaxed">{summary}</p>
                <div className="p-4 rounded-xl flex gap-3" style={{ backgroundColor: `${zoneConfig.color}08`, borderLeft: `3px solid ${zoneConfig.color}` }}>
                  <Lightbulb className="w-5 h-5 flex-shrink-0 mt-0.5" style={{ color: zoneConfig.color }} />
                  <div><span className="font-roboto font-semibold text-white text-sm">Recommendation</span>
                    <p className="font-roboto text-white/75 text-sm leading-relaxed mt-1">{recommendation}</p></div>
                </div>
                <button onClick={handleDownloadPDF} disabled={isGeneratingPDF}
                  className="inline-flex items-center gap-2 px-5 py-2 bg-white/10 hover:bg-white/20 text-white rounded-full text-sm border border-white/20 disabled:opacity-50">
                  <Download className="w-4 h-4" />{isGeneratingPDF ? 'Generating...' : 'Download Report'}
                </button>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Visual Timeline */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="glass-card rounded-2xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-roboto font-bold text-xl text-white flex items-center gap-2"><Eye className="w-5 h-5 text-white/70" />Visual Analysis</h2>
            <span className="text-xs text-white/50">Click markers to jump</span>
          </div>
          <div className="relative h-48 rounded-xl overflow-hidden" style={{ backgroundColor: 'rgba(255,255,255,0.05)' }}>
            <div className="absolute inset-0 flex flex-col">
              <div className="flex-1" style={{ backgroundColor: 'rgba(239,68,68,0.15)' }}></div>
              <div className="flex-1" style={{ backgroundColor: 'rgba(245,158,11,0.15)' }}></div>
              <div className="flex-1" style={{ backgroundColor: 'rgba(34,197,94,0.15)' }}></div>
            </div>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 15, right: 15, left: -20, bottom: 5 }}>
                <XAxis dataKey="time" stroke="rgba(255,255,255,0.4)" fontSize={11} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                <YAxis domain={[0, 100]} stroke="rgba(255,255,255,0.4)" fontSize={11} tickLine={false} axisLine={false} ticks={[0, 33, 66, 100]} width={30} />
                <Tooltip content={<CustomTooltip />} />
                <Line type="monotone" dataKey="score" stroke="#1e293b" strokeWidth={2.5} dot={(p) => <MarkerDot {...p} onClick={handleMarkerClick} />} activeDot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="flex justify-center gap-6 mt-4 pt-3 border-t border-white/10">
            {[['green','Low (0-33)'],['amber','Moderate (34-66)'],['red','Elevated (67+)']].map(([c,l]) => (
              <span key={c} className="flex items-center gap-2 text-sm text-white/60"><span className={`w-3 h-3 rounded-full bg-${c === 'amber' ? 'amber' : c}-500`}></span>{l}</span>
            ))}
          </div>
        </motion.div>

        {/* Behavioral Markers - Only verified observations */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="glass-card rounded-2xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-roboto font-bold text-xl text-white">Behavioral Markers</h2>
            <span className="text-white/40 text-xs">Click for details</span>
          </div>
          {behaviorMarkers.length > 0 ? (
            <div className="flex flex-wrap gap-2.5">
              {behaviorMarkers.map((m, i) => (
                <button key={i} 
                  className="px-3.5 py-1.5 rounded-full font-roboto font-medium text-sm text-white border cursor-pointer hover:scale-105 hover:brightness-110 transition-all"
                  style={{ backgroundColor: `${ZONE_CONFIG[m.zone]?.color || '#94a3b8'}20`, borderColor: ZONE_CONFIG[m.zone]?.color || '#94a3b8' }} 
                  onClick={() => setSelectedMarker(m)}
                >
                  {m.code && <span className="text-white/50 mr-1.5">{m.code}</span>}
                  {m.text}
                  {m.timestamp && <span className="text-white/40 ml-1.5 text-xs">@ {m.timestamp}</span>}
                </button>
              ))}
            </div>
          ) : (
            <p className="text-white/50 text-sm italic">No clear behavioral markers detected in this video. This may be due to video quality, angle, or the pet's position.</p>
          )}
        </motion.div>

        {/* Audio */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }} className="glass-card rounded-2xl overflow-hidden">
          <button onClick={() => toggleSection('audio')} className="w-full p-6 flex items-center justify-between hover:bg-white/5">
            <h2 className="font-roboto font-bold text-xl text-white flex items-center gap-2"><Volume2 className="w-5 h-5 text-white/70" />Audio Analysis</h2>
            {expandedSections.audio ? <ChevronUp className="w-5 h-5 text-white/50" /> : <ChevronDown className="w-5 h-5 text-white/50" />}
          </button>
          {expandedSections.audio && <div className="px-6 pb-6"><AudioWaveform events={audio_analysis?.vocalizations_detected || []} environmentalSounds={audio_analysis?.environmental_sounds || []} duration={duration || 17} currentTime={currentTime} isPlaying={isPlaying} onSeek={handleMarkerClick} videoContext={video_context} /></div>}
        </motion.div>

        {/* Pet's Perspective - Umwelt-based ethological translation */}
        {interpret_lines?.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }} className="glass-card rounded-2xl overflow-hidden">
            <button onClick={() => toggleSection('interpret')} className="w-full p-6 flex items-center justify-between hover:bg-white/5">
              <h2 className="font-roboto font-bold text-xl text-white flex items-center gap-2"><MessageCircle className="w-5 h-5 text-white/70" />Pet's Perspective</h2>
              {expandedSections.interpret ? <ChevronUp className="w-5 h-5 text-white/50" /> : <ChevronDown className="w-5 h-5 text-white/50" />}
            </button>
            {expandedSections.interpret && (
              <div className="px-6 pb-6">
                <p className="text-white/50 text-xs mb-4 italic">What your pet likely perceives — based on the specific context of this video</p>
                <div className="space-y-3">
                  {interpret_lines.map((line, i) => {
                    const petPovText = getPetPovText(line);
                    const z = line.zone || getBehaviorZone(petPovText);
                    const c = ZONE_CONFIG[z]?.color || '#94a3b8';
                    
                    return (
                      <div key={i} className="p-4 rounded-xl cursor-pointer hover:bg-white/10 transition-colors"
                        style={{ backgroundColor: 'rgba(0,0,0,0.3)', borderLeft: `4px solid ${c}` }}
                        onClick={() => { const p = (line.timestamp||'0:00').split(':').map(Number); handleMarkerClick(p.length===2 ? p[0]*60+p[1] : parseFloat(line.timestamp)||0); }}>
                        <div className="flex items-start gap-3">
                          <span className="text-white/50 text-xs font-mono min-w-[40px]">{line.timestamp}</span>
                          <div className="flex-1">
                            <p className="text-white font-medium italic">"{petPovText}"</p>
                            {line.trigger && <p className="text-white/40 text-xs mt-1">Trigger: {line.trigger}</p>}
                          </div>
                          <span className="px-2 py-0.5 rounded text-xs font-medium" style={{ backgroundColor: `${c}33`, color: c }}>
                            {z === 'red' ? 'High' : z === 'yellow' ? 'Med' : 'Low'}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </motion.div>
        )}

        {/* Scientific Insight - Expectation Analysis */}
        {analysisData?.expectation_analysis && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.52 }} className="glass-card rounded-2xl p-6">
            <h2 className="font-roboto font-bold text-xl text-white flex items-center gap-2 mb-4">
              <BookOpen className="w-5 h-5 text-cyan-400" />
              Scientific Insight
            </h2>
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 rounded-xl" style={{ backgroundColor: 'rgba(255,255,255,0.05)' }}>
                  <p className="text-white/50 text-xs uppercase tracking-wider mb-1">Pet's Expectation</p>
                  <p className="text-white text-sm">{analysisData.expectation_analysis.pet_expectation}</p>
                </div>
                <div className="p-4 rounded-xl" style={{ backgroundColor: 'rgba(255,255,255,0.05)' }}>
                  <p className="text-white/50 text-xs uppercase tracking-wider mb-1">Actual Outcome</p>
                  <p className="text-white text-sm">{analysisData.expectation_analysis.actual_outcome}</p>
                </div>
              </div>
              {analysisData.expectation_analysis.emotional_response && (
                <div className="p-4 rounded-xl border-l-4" style={{ 
                  backgroundColor: 'rgba(255,255,255,0.03)', 
                  borderColor: analysisData.expectation_analysis.match_type === 'exceeded' ? '#22c55e' : 
                               analysisData.expectation_analysis.match_type === 'met' ? '#22c55e' :
                               analysisData.expectation_analysis.match_type === 'fell_short' ? '#f59e0b' : '#ef4444'
                }}>
                  <p className="text-white/50 text-xs uppercase tracking-wider mb-1">Emotional Response</p>
                  <p className="text-white text-sm">{analysisData.expectation_analysis.emotional_response}</p>
                </div>
              )}
              {analysisData.scene_understanding?.narrative && (
                <p className="text-white/60 text-sm italic mt-2">{analysisData.scene_understanding.narrative}</p>
              )}
            </div>
          </motion.div>
        )}

        {/* Did You Know */}
        {breedFact && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.55 }} className="glass-card rounded-2xl overflow-hidden">
            <button onClick={() => toggleSection('didyouknow')} className="w-full p-6 flex items-center justify-between hover:bg-white/5">
              <h2 className="font-roboto font-bold text-xl text-white flex items-center gap-2"><Sparkles className="w-5 h-5 text-amber-400" />Did You Know?</h2>
              {expandedSections.didyouknow ? <ChevronUp className="w-5 h-5 text-white/50" /> : <ChevronDown className="w-5 h-5 text-white/50" />}
            </button>
            {expandedSections.didyouknow && <div className="px-6 pb-6"><p className="text-white/80 text-sm leading-relaxed">{breedFact}</p></div>}
          </motion.div>
        )}

        {/* Research */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6 }} className="glass-card rounded-2xl overflow-hidden">
          <button onClick={() => toggleSection('research')} className="w-full p-6 flex items-center justify-between hover:bg-white/5">
            <h2 className="font-roboto font-bold text-xl text-white flex items-center gap-2"><BookOpen className="w-5 h-5 text-white/70" />Research Frameworks</h2>
            {expandedSections.research ? <ChevronUp className="w-5 h-5 text-white/50" /> : <ChevronDown className="w-5 h-5 text-white/50" />}
          </button>
          {expandedSections.research && (
            <div className="px-6 pb-6">
              <ul className="space-y-2 text-white/70 text-sm">
                <li><b className="text-white">DogFACS</b> — Dog Facial Action Coding System (Waller et al., 2013)</li>
                <li><b className="text-white">Feline Grimace Scale</b> — Pain assessment (Evangelista et al., 2019)</li>
                <li><b className="text-white">Morton's Rules</b> — Motivation-Structural Rules (1977)</li>
                <li><b className="text-white">C-BARQ</b> — Canine Behavioral Assessment (Serpell, UPenn)</li>
                <li><b className="text-white">Canine Bio-Acoustics</b> — Pongrácz, Faragó et al.</li>
              </ul>
            </div>
          )}
        </motion.div>

        {/* Rating Widget */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }} 
          animate={{ opacity: 1, y: 0 }} 
          transition={{ delay: 0.65 }}
          className="flex justify-center"
        >
          <RatingWidget 
            analysisId={Date.now().toString()}
            species={species}
            breed={breed_detected}
            distressScore={distressScore}
          />
        </motion.div>

        {/* Footer */}
        <Footer />
      </div>
    </div>
  );
}

export default Dashboard;
