import React, { useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import { 
  Heart,
  Activity,
  Thermometer,
  Wind,
  Moon,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  CheckCircle,
  Info,
  ChevronDown,
  ChevronUp,
  Zap,
  Clock,
  Calendar
} from 'lucide-react';
import Footer from '../components/Footer';

// Pet names and breeds for randomization
const PET_OPTIONS = [
  { name: 'Luna', breed: 'Belgian Malinois', weight: 28, age: 3 },
  { name: 'Max', breed: 'German Shepherd', weight: 34, age: 5 },
  { name: 'Bella', breed: 'Golden Retriever', weight: 29, age: 4 },
  { name: 'Charlie', breed: 'Labrador Retriever', weight: 32, age: 2 },
  { name: 'Daisy', breed: 'Beagle', weight: 11, age: 6 },
  { name: 'Cooper', breed: 'Border Collie', weight: 19, age: 3 },
  { name: 'Milo', breed: 'French Bulldog', weight: 12, age: 4 },
  { name: 'Sadie', breed: 'Siberian Husky', weight: 23, age: 2 }
];

const STRESS_TRIGGERS = ['Doorbell', 'Thunder', 'Vacuum', 'Stranger', 'Fireworks', 'Car ride', 'Vet visit', 'Unknown'];

// Generate random data on each visit
const generateRandomData = () => {
  const pet = PET_OPTIONS[Math.floor(Math.random() * PET_OPTIONS.length)];
  
  // Base heart rate varies by breed size
  const baseHR = pet.weight < 15 ? 90 : pet.weight < 25 ? 75 : 65;
  const hrVariance = () => Math.floor(Math.random() * 10) - 5;
  
  const currentVitals = {
    heartRate: baseHR + hrVariance(),
    heartRateStatus: Math.random() > 0.85 ? 'elevated' : 'normal',
    hrv: 35 + Math.floor(Math.random() * 25),
    hrvStatus: Math.random() > 0.9 ? 'low' : 'normal',
    respiration: 15 + Math.floor(Math.random() * 10),
    respirationStatus: 'normal',
    temperature: (37.5 + Math.random() * 1.5).toFixed(1),
    temperatureStatus: 'normal',
    lastUpdated: `${Math.floor(Math.random() * 10) + 1} min ago`
  };
  
  const todaySummary = {
    avgHeartRate: baseHR + Math.floor(Math.random() * 15),
    avgHrv: 40 + Math.floor(Math.random() * 20),
    restingHr: baseHR - 10 + Math.floor(Math.random() * 10),
    peakHr: baseHR + 50 + Math.floor(Math.random() * 40),
    activeMinutes: 45 + Math.floor(Math.random() * 60),
    sleepHours: (6 + Math.random() * 4).toFixed(1),
    sleepQuality: Math.random() > 0.3 ? 'good' : 'fair',
    stressEvents: Math.floor(Math.random() * 4)
  };
  
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const weeklyHR = days.map(day => ({
    day,
    resting: baseHR - 15 + Math.floor(Math.random() * 15),
    avg: baseHR - 5 + Math.floor(Math.random() * 15),
    peak: baseHR + 40 + Math.floor(Math.random() * 50)
  }));
  
  const numStressEvents = Math.floor(Math.random() * 3) + 1;
  const stressEvents = Array.from({ length: numStressEvents }, (_, i) => ({
    time: `${8 + Math.floor(Math.random() * 10)}:${String(Math.floor(Math.random() * 60)).padStart(2, '0')}`,
    duration: `${2 + Math.floor(Math.random() * 8)} min`,
    trigger: STRESS_TRIGGERS[Math.floor(Math.random() * STRESS_TRIGGERS.length)],
    hr: baseHR + 40 + Math.floor(Math.random() * 40),
    hrv: 15 + Math.floor(Math.random() * 20),
    recovered: Math.random() > 0.2,
    recoveryTime: `${2 + Math.floor(Math.random() * 6)} min`
  }));
  
  return {
    pet: { ...pet, connected: true, deviceBattery: 60 + Math.floor(Math.random() * 35) },
    currentVitals,
    todaySummary,
    weeklyHR,
    stressEvents
  };
};

// Breed-specific baselines (research-backed)
const BREED_BASELINES = {
  'belgian malinois': { rhrLow: 60, rhrHigh: 90, hrvNormal: 45 },
  'german shepherd': { rhrLow: 60, rhrHigh: 90, hrvNormal: 45 },
  'golden retriever': { rhrLow: 60, rhrHigh: 100, hrvNormal: 42 },
  'labrador retriever': { rhrLow: 60, rhrHigh: 100, hrvNormal: 42 },
  'beagle': { rhrLow: 70, rhrHigh: 120, hrvNormal: 38 },
  'border collie': { rhrLow: 60, rhrHigh: 100, hrvNormal: 45 },
  'french bulldog': { rhrLow: 80, rhrHigh: 120, hrvNormal: 35 },
  'siberian husky': { rhrLow: 55, rhrHigh: 90, hrvNormal: 48 },
  'default': { rhrLow: 60, rhrHigh: 100, hrvNormal: 40 }
};

const getStatusColor = (status) => {
  switch (status) {
    case 'good':
    case 'normal':
      return '#22c55e';
    case 'elevated':
    case 'warning':
      return '#f59e0b';
    case 'high':
    case 'low':
    case 'poor':
      return '#ef4444';
    default:
      return '#94a3b8';
  }
};

const VitalCard = ({ icon: Icon, label, value, unit, status, trend, info }) => {
  const statusColor = getStatusColor(status);
  
  return (
    <div className="glass-card rounded-xl p-4 flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-white/60" />
          <span className="font-roboto text-white/60 text-xs uppercase tracking-wider">{label}</span>
        </div>
        {trend && (
          <div className="flex items-center gap-1">
            {trend === 'up' && <TrendingUp className="w-3 h-3 text-amber-400" />}
            {trend === 'down' && <TrendingDown className="w-3 h-3 text-green-400" />}
            {trend === 'stable' && <Minus className="w-3 h-3 text-white/40" />}
          </div>
        )}
      </div>
      <div className="flex items-baseline gap-1">
        <span className="font-roboto font-bold text-3xl" style={{ color: statusColor }}>{value}</span>
        <span className="font-roboto text-white/50 text-sm">{unit}</span>
      </div>
      {info && <p className="font-roboto text-white/50 text-xs mt-1">{info}</p>}
    </div>
  );
};

const WeeklyHRChart = ({ data }) => {
  const maxHr = Math.max(...data.map(d => d.peak));
  
  return (
    <div className="flex items-end justify-between gap-2 h-32 px-2">
      {data.map((day, idx) => (
        <div key={idx} className="flex-1 flex flex-col items-center gap-1">
          <div className="w-full flex flex-col items-center gap-0.5 flex-1 justify-end">
            <div 
              className="w-full rounded-t-sm bg-red-400/60"
              style={{ height: `${((day.peak - day.avg) / maxHr) * 100}%`, minHeight: '4px' }}
            />
            <div 
              className="w-full bg-amber-400/60"
              style={{ height: `${((day.avg - day.resting) / maxHr) * 100}%`, minHeight: '4px' }}
            />
            <div 
              className="w-full rounded-b-sm bg-green-400/60"
              style={{ height: `${(day.resting / maxHr) * 100}%`, minHeight: '8px' }}
            />
          </div>
          <span className="font-roboto text-white/50 text-xs">{day.day}</span>
        </div>
      ))}
    </div>
  );
};

function Biometrics() {
  const [expandedSections, setExpandedSections] = useState({
    vitals: true,
    insights: true,
    events: true,
    research: false
  });

  // Generate random data on mount
  const data = useMemo(() => generateRandomData(), []);
  const { pet, currentVitals, todaySummary, weeklyHR, stressEvents } = data;

  const toggleSection = (section) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const baselines = BREED_BASELINES[pet.breed.toLowerCase()] || BREED_BASELINES['default'];

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="py-6 px-6">
        <div className="max-w-5xl mx-auto flex flex-col items-center">
          <img src="/etho-logo.png" alt="Etho" className="h-10" 
            onError={(e) => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'block'; }} 
          />
          <span className="font-roboto font-bold text-3xl text-white hidden drop-shadow-lg">Etho</span>
          <p className="font-roboto text-white/60 text-sm mt-2">AI-powered pet behavior analysis</p>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-6 pb-12 space-y-6">
        
        {/* Page Title */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-2"
        >
          <h1 className="text-2xl font-bold text-white font-roboto flex items-center justify-center gap-2">
            <Activity className="w-6 h-6 text-red-400" />
            Biometrics
          </h1>
          <p className="text-white/50 text-xs mt-1 font-roboto">Demo data — refreshes each visit</p>
        </motion.div>

        {/* Connection Status Bar */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card rounded-xl p-4"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-cyan-400 to-blue-500 flex items-center justify-center text-white font-bold font-roboto">
                {pet.name.charAt(0)}
              </div>
              <div>
                <h2 className="font-roboto font-bold text-white">{pet.name}</h2>
                <p className="font-roboto text-white/60 text-sm">{pet.breed} • {pet.weight}kg • {pet.age} years</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></span>
                  <span className="font-roboto text-green-400 text-sm font-medium">Connected</span>
                </div>
                <p className="font-roboto text-white/40 text-xs">PetPace • Battery {pet.deviceBattery}%</p>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Current Vitals Grid */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="glass-card rounded-2xl p-6"
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-roboto font-bold text-lg text-white flex items-center gap-2">
              <Heart className="w-5 h-5 text-red-400" />
              Current Vitals
            </h2>
            <span className="font-roboto text-white/40 text-xs">Updated {currentVitals.lastUpdated}</span>
          </div>
          
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 vitals-grid">
            <VitalCard 
              icon={Heart}
              label="Heart Rate"
              value={currentVitals.heartRate}
              unit="bpm"
              status={currentVitals.heartRateStatus}
              trend="stable"
              info={`Normal: ${baselines.rhrLow}-${baselines.rhrHigh} bpm`}
            />
            <VitalCard 
              icon={Activity}
              label="HRV"
              value={currentVitals.hrv}
              unit="ms"
              status={currentVitals.hrvStatus}
              trend="stable"
              info="Higher = more relaxed"
            />
            <VitalCard 
              icon={Wind}
              label="Respiration"
              value={currentVitals.respiration}
              unit="/min"
              status={currentVitals.respirationStatus}
              trend="stable"
              info="Normal: 15-30/min"
            />
            <VitalCard 
              icon={Thermometer}
              label="Temperature"
              value={currentVitals.temperature}
              unit="°C"
              status={currentVitals.temperatureStatus}
              trend="stable"
              info="Normal: 37.5-39.2°C"
            />
          </div>

          {/* Contextual Assessment */}
          <div className="mt-4 p-4 rounded-xl flex items-start gap-3" style={{ backgroundColor: 'rgba(34, 197, 94, 0.15)' }}>
            <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-roboto text-white text-sm font-medium">All vitals within normal range</p>
              <p className="font-roboto text-white/70 text-xs mt-1">
                {pet.name}'s current readings indicate a calm, resting state. Heart rate and HRV are consistent with relaxed baseline for a {pet.breed}.
              </p>
            </div>
          </div>
        </motion.div>

        {/* Today's Summary */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="glass-card rounded-2xl p-6"
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-roboto font-bold text-lg text-white flex items-center gap-2">
              <Calendar className="w-5 h-5 text-white/70" />
              Today's Summary
            </h2>
            <span className="font-roboto text-white/40 text-xs">{new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })}</span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="text-center p-3 rounded-lg" style={{ backgroundColor: 'rgba(255,255,255,0.05)' }}>
              <p className="font-roboto text-white/50 text-xs uppercase mb-1">Resting HR</p>
              <p className="font-roboto font-bold text-2xl text-green-400">{todaySummary.restingHr}</p>
              <p className="font-roboto text-white/40 text-xs">bpm</p>
            </div>
            <div className="text-center p-3 rounded-lg" style={{ backgroundColor: 'rgba(255,255,255,0.05)' }}>
              <p className="font-roboto text-white/50 text-xs uppercase mb-1">Peak HR</p>
              <p className="font-roboto font-bold text-2xl text-red-400">{todaySummary.peakHr}</p>
              <p className="font-roboto text-white/40 text-xs">bpm</p>
            </div>
            <div className="text-center p-3 rounded-lg" style={{ backgroundColor: 'rgba(255,255,255,0.05)' }}>
              <p className="font-roboto text-white/50 text-xs uppercase mb-1">Active</p>
              <p className="font-roboto font-bold text-2xl text-amber-400">{todaySummary.activeMinutes}</p>
              <p className="font-roboto text-white/40 text-xs">minutes</p>
            </div>
            <div className="text-center p-3 rounded-lg" style={{ backgroundColor: 'rgba(255,255,255,0.05)' }}>
              <p className="font-roboto text-white/50 text-xs uppercase mb-1">Sleep</p>
              <p className="font-roboto font-bold text-2xl text-blue-400">{todaySummary.sleepHours}</p>
              <p className="font-roboto text-white/40 text-xs">hours</p>
            </div>
          </div>

          {/* Weekly HR Trend */}
          <div className="mb-4">
            <h3 className="font-roboto text-white/70 text-sm mb-3">7-Day Heart Rate Trend</h3>
            <WeeklyHRChart data={weeklyHR} />
            <div className="flex justify-center gap-6 mt-3">
              <span className="flex items-center gap-2 font-roboto text-xs text-white/50">
                <span className="w-3 h-3 rounded-sm bg-green-400/60"></span>Resting
              </span>
              <span className="flex items-center gap-2 font-roboto text-xs text-white/50">
                <span className="w-3 h-3 rounded-sm bg-amber-400/60"></span>Average
              </span>
              <span className="flex items-center gap-2 font-roboto text-xs text-white/50">
                <span className="w-3 h-3 rounded-sm bg-red-400/60"></span>Peak
              </span>
            </div>
          </div>
        </motion.div>

        {/* Stress Events */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="glass-card rounded-2xl overflow-hidden"
        >
          <button 
            onClick={() => toggleSection('events')}
            className="w-full p-6 flex items-center justify-between hover:bg-white/5 transition-colors"
          >
            <h2 className="font-roboto font-bold text-lg text-white flex items-center gap-2">
              <Zap className="w-5 h-5 text-amber-400" />
              Stress Events Today
              <span className="ml-2 px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 text-xs font-medium">
                {stressEvents.length}
              </span>
            </h2>
            {expandedSections.events ? <ChevronUp className="w-5 h-5 text-white/50" /> : <ChevronDown className="w-5 h-5 text-white/50" />}
          </button>
          
          {expandedSections.events && (
            <div className="px-6 pb-6 space-y-3">
              {stressEvents.map((event, idx) => (
                <div 
                  key={idx}
                  className="p-4 rounded-xl flex items-start gap-4"
                  style={{ backgroundColor: 'rgba(255,255,255,0.05)', borderLeft: '4px solid #f59e0b' }}
                >
                  <div className="flex-shrink-0 text-center">
                    <Clock className="w-4 h-4 text-white/40 mx-auto mb-1" />
                    <p className="font-roboto font-mono text-white text-sm">{event.time}</p>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-roboto font-medium text-white">{event.trigger}</span>
                      <span className="font-roboto text-white/40 text-xs">• {event.duration}</span>
                    </div>
                    <div className="flex items-center gap-4 mb-2">
                      <span className="font-roboto text-red-400 text-sm">HR: {event.hr} bpm</span>
                      <span className="font-roboto text-amber-400 text-sm">HRV: {event.hrv} ms</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {event.recovered ? (
                        <>
                          <CheckCircle className="w-4 h-4 text-green-400" />
                          <span className="font-roboto text-green-400 text-xs">Recovered in {event.recoveryTime}</span>
                        </>
                      ) : (
                        <>
                          <AlertTriangle className="w-4 h-4 text-amber-400" />
                          <span className="font-roboto text-amber-400 text-xs">Slow recovery — monitor</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              ))}

              {/* Insight */}
              <div className="p-4 rounded-xl flex items-start gap-3" style={{ backgroundColor: 'rgba(56, 189, 248, 0.1)' }}>
                <Info className="w-5 h-5 text-sky-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-roboto text-white text-sm font-medium">Recovery analysis</p>
                  <p className="font-roboto text-white/70 text-xs mt-1">
                    {pet.name}'s heart rate typically returns to baseline within 5 minutes, indicating good vagal tone. 
                    Consider desensitization training for recurring triggers.
                  </p>
                  <p className="font-roboto text-white/50 text-xs mt-2 italic">
                    Research: Recovery time &lt;5 min indicates healthy autonomic regulation (Katayama et al., 2016)
                  </p>
                </div>
              </div>
            </div>
          )}
        </motion.div>

        {/* Behavioral Insights */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="glass-card rounded-2xl overflow-hidden"
        >
          <button 
            onClick={() => toggleSection('insights')}
            className="w-full p-6 flex items-center justify-between hover:bg-white/5 transition-colors"
          >
            <h2 className="font-roboto font-bold text-lg text-white flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-white/70" />
              Behavioral Insights
            </h2>
            {expandedSections.insights ? <ChevronUp className="w-5 h-5 text-white/50" /> : <ChevronDown className="w-5 h-5 text-white/50" />}
          </button>
          
          {expandedSections.insights && (
            <div className="px-6 pb-6 space-y-4">
              {/* Sleep Quality */}
              <div className="p-4 rounded-xl" style={{ backgroundColor: 'rgba(255,255,255,0.05)' }}>
                <div className="flex items-center gap-2 mb-2">
                  <Moon className="w-4 h-4 text-blue-400" />
                  <span className="font-roboto font-medium text-white">Sleep Quality: {todaySummary.sleepQuality === 'good' ? 'Good' : 'Fair'}</span>
                </div>
                <p className="font-roboto text-white/70 text-sm">
                  {pet.name} had {todaySummary.sleepHours} hours of sleep. Resting heart rate during sleep indicates 
                  {todaySummary.sleepQuality === 'good' ? ' healthy rest patterns' : ' some restlessness'}.
                </p>
              </div>

              {/* Activity Balance */}
              <div className="p-4 rounded-xl" style={{ backgroundColor: 'rgba(255,255,255,0.05)' }}>
                <div className="flex items-center gap-2 mb-2">
                  <Activity className="w-4 h-4 text-green-400" />
                  <span className="font-roboto font-medium text-white">Activity Balance: {todaySummary.activeMinutes > 60 ? 'Optimal' : 'Moderate'}</span>
                </div>
                <p className="font-roboto text-white/70 text-sm">
                  {todaySummary.activeMinutes} active minutes today with appropriate rest periods. 
                  Peak HR of {todaySummary.peakHr} bpm during exercise is within healthy range.
                </p>
              </div>

              {/* Trend Alert */}
              <div className="p-4 rounded-xl" style={{ backgroundColor: 'rgba(34, 197, 94, 0.1)' }}>
                <div className="flex items-center gap-2 mb-2">
                  <TrendingDown className="w-4 h-4 text-green-400" />
                  <span className="font-roboto font-medium text-white">7-Day Trend: Stable</span>
                </div>
                <p className="font-roboto text-white/70 text-sm">
                  Average resting heart rate has remained consistent over the past week, suggesting 
                  {pet.name} is well-adjusted to their environment and routine.
                </p>
                <p className="font-roboto text-white/50 text-xs mt-2 italic">
                  Research: Stable resting HR correlates with low baseline anxiety (Zupan et al., 2021)
                </p>
              </div>
            </div>
          )}
        </motion.div>

        {/* Research & Methodology */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="glass-card rounded-2xl overflow-hidden"
        >
          <button 
            onClick={() => toggleSection('research')}
            className="w-full p-6 flex items-center justify-between hover:bg-white/5 transition-colors"
          >
            <h2 className="font-roboto font-bold text-lg text-white flex items-center gap-2">
              <Info className="w-5 h-5 text-white/70" />
              How We Analyze Biometrics
            </h2>
            {expandedSections.research ? <ChevronUp className="w-5 h-5 text-white/50" /> : <ChevronDown className="w-5 h-5 text-white/50" />}
          </button>
          
          {expandedSections.research && (
            <div className="px-6 pb-6 space-y-4">
              <p className="font-roboto text-white/80 text-sm">
                Raw heart rate data is meaningless without context. We use the <strong className="text-white">Contextual Stress Index (CSI)</strong> to 
                interpret vitals accurately, combining activity level, breed baselines, and behavioral signals.
              </p>

              <div className="space-y-3">
                <div className="p-3 rounded-lg" style={{ backgroundColor: 'rgba(255,255,255,0.05)' }}>
                  <h4 className="font-roboto font-medium text-white text-sm mb-1">Freeze Detection</h4>
                  <p className="font-roboto text-white/60 text-xs">
                    Low movement + elevated HR = fear response. We flag when speed &lt;0.5 mph AND heart rate &gt;150% of resting baseline.
                  </p>
                </div>

                <div className="p-3 rounded-lg" style={{ backgroundColor: 'rgba(255,255,255,0.05)' }}>
                  <h4 className="font-roboto font-medium text-white text-sm mb-1">Recovery Analysis</h4>
                  <p className="font-roboto text-white/60 text-xs">
                    How quickly HR returns to baseline indicates vagal tone. &lt;5 min = healthy. &gt;10 min = potential chronic anxiety.
                  </p>
                </div>

                <div className="p-3 rounded-lg" style={{ backgroundColor: 'rgba(255,255,255,0.05)' }}>
                  <h4 className="font-roboto font-medium text-white text-sm mb-1">Breed Normalization</h4>
                  <p className="font-roboto text-white/60 text-xs">
                    {pet.breed} baseline: {baselines.rhrLow}-{baselines.rhrHigh} bpm resting. Adjustments made for brachycephalic and sighthound breeds.
                  </p>
                </div>
              </div>

              <div className="pt-3 border-t border-white/10">
                <h4 className="font-roboto font-medium text-white text-sm mb-2">Research Sources</h4>
                <ul className="space-y-1 font-roboto text-white/60 text-xs">
                  <li>• Zupan et al., 2021 — HRV in dogs systematic review</li>
                  <li>• Katayama et al., 2016 — Recovery time and autonomic function</li>
                  <li>• Palestrini et al., 2005 — Physiological stress indicators</li>
                  <li>• Lamb et al., 2010 — Breed-specific heart rate baselines</li>
                </ul>
              </div>
            </div>
          )}
        </motion.div>

        {/* Footer */}
        <Footer />
      </div>
    </div>
  );
}

export default Biometrics;
