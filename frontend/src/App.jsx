import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Menu, X, Home, Info, BarChart3, Activity, Lock, PawPrint,
         CalendarRange, Upload } from 'lucide-react';
import Hero from './pages/Hero';
import Landing from './pages/Landing';
import Dashboard from './pages/Dashboard';
import About from './pages/About';
import Biometrics from './pages/Biometrics';
import Pets from './pages/Pets';
import Timeline from './pages/Timeline';
import VetReport from './pages/VetReport';
import AnalysisDetail from './pages/AnalysisDetail';

const PASSWORD = 'etho2024';
const ACTIVE_PET_KEY = 'etho.activePetId';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [passwordInput, setPasswordInput] = useState('');
  const [passwordError, setPasswordError] = useState(false);
  const [currentPage, setCurrentPage] = useState('hero');
  const [menuOpen, setMenuOpen] = useState(false);
  const [analysisData, setAnalysisData] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [mediaType, setMediaType] = useState(null);
  // A past observation reopened from the timeline.
  const [detailAnalysisId, setDetailAnalysisId] = useState(null);

  // The pet new captures are filed against. Remembered between visits so a
  // guardian isn't re-picking their pet on every upload.
  const [activePetId, setActivePetId] = useState(
    () => localStorage.getItem(ACTIVE_PET_KEY) || null
  );
  const [reportPetId, setReportPetId] = useState(null);

  useEffect(() => {
    if (activePetId) localStorage.setItem(ACTIVE_PET_KEY, activePetId);
    else localStorage.removeItem(ACTIVE_PET_KEY);
  }, [activePetId]);

  const handlePasswordSubmit = (e) => {
    e.preventDefault();
    if (passwordInput === PASSWORD) {
      setIsAuthenticated(true);
      setPasswordError(false);
    } else {
      setPasswordError(true);
      setPasswordInput('');
    }
  };

  const handleAnalysisComplete = (data, url, kind) => {
    setAnalysisData(data);
    setVideoUrl(url);
    setMediaType(kind || null);
    setCurrentPage('dashboard');
  };

  const openAnalysis = (analysisId) => {
    if (!analysisId) return;
    setDetailAnalysisId(analysisId);
    navigateTo('analysis');
  };

  const navigateTo = (page) => {
    setCurrentPage(page);
    setMenuOpen(false);
  };

  const openTimeline = (petId) => {
    if (petId) setActivePetId(petId);
    navigateTo('timeline');
  };

  const openVetReport = (petId) => {
    setReportPetId(petId || activePetId);
    navigateTo('vetreport');
  };

  // Password Gate
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-sky-400 via-blue-500 to-cyan-600 flex items-center justify-center p-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-sm"
        >
          <div
            className="p-8 rounded-3xl text-center"
            style={{
              background: 'rgba(255, 255, 255, 0.15)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.2)'
            }}
          >
            <img
              src="/etho-logo.png"
              alt="Etho"
              className="h-12 mx-auto mb-6"
              onError={(e) => { e.target.style.display = 'none'; }}
            />
            <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-white/20 flex items-center justify-center">
              <Lock className="w-6 h-6 text-white" />
            </div>
            <h2 className="font-roboto font-bold text-xl text-white mb-2">Beta Access</h2>
            <p className="font-roboto text-white/70 text-sm mb-6">Enter password to continue</p>

            <form onSubmit={handlePasswordSubmit}>
              <input
                type="password"
                value={passwordInput}
                onChange={(e) => setPasswordInput(e.target.value)}
                placeholder="Password"
                className="w-full px-4 py-3 rounded-xl bg-white/20 border border-white/30 text-white placeholder-white/50 font-roboto text-center focus:outline-none focus:border-white/50 mb-4"
                autoFocus
              />
              {passwordError && (
                <p className="text-red-300 text-sm mb-4 font-roboto">Incorrect password</p>
              )}
              <button
                type="submit"
                className="w-full py-3 rounded-xl bg-white/30 hover:bg-white/40 text-white font-roboto font-medium transition-colors"
              >
                Enter
              </button>
            </form>
          </div>
        </motion.div>
      </div>
    );
  }

  const showMenu = currentPage !== 'hero';

  // Timeline and the vet report only appear once there's a pet to show —
  // empty menu items teach nothing and make the app feel unfinished.
  const navItems = [
    { id: 'hero', label: 'Home', icon: Home },
    { id: 'landing', label: 'Analyse a clip', icon: Upload },
    { id: 'pets', label: 'My pets', icon: PawPrint },
    ...(activePetId ? [{ id: 'timeline', label: 'Timeline', icon: CalendarRange }] : []),
    { id: 'dashboard', label: 'Latest analysis', icon: BarChart3, disabled: !analysisData },
    { id: 'about', label: 'Research', icon: Info },
    { id: 'biometrics', label: 'Biometrics', icon: Activity, badge: 'New' },
  ];

  const page = (key, node) => (
    <motion.div key={key} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      {node}
    </motion.div>
  );

  return (
    <div className="relative min-h-screen font-roboto">
      {showMenu && (
        <button
          onClick={() => setMenuOpen(!menuOpen)}
          className="fixed top-4 right-4 z-50 p-3 glass-card rounded-full hover:bg-white/30 transition-colors no-print"
        >
          {menuOpen ? <X className="w-5 h-5 text-white" /> : <Menu className="w-5 h-5 text-white" />}
        </button>
      )}

      <AnimatePresence>
        {menuOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setMenuOpen(false)}
              className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40"
            />
            <motion.div
              initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
              transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              className="fixed right-0 top-0 h-full w-72 z-50 p-6 nav-menu"
              style={{
                background: 'rgba(255, 255, 255, 0.15)',
                backdropFilter: 'blur(20px)',
                borderLeft: '1px solid rgba(255, 255, 255, 0.2)'
              }}
            >
              <div className="mt-16 space-y-1">
                {navItems.map(({ id, label, icon: Icon, disabled, badge }) => (
                  <button
                    key={id}
                    onClick={() => !disabled && navigateTo(id)}
                    disabled={disabled}
                    className={`w-full flex items-center gap-3 p-4 rounded-xl transition-colors ${
                      currentPage === id
                        ? 'bg-white/20 text-white'
                        : disabled
                          ? 'text-white/30 cursor-not-allowed'
                          : 'hover:bg-white/10 text-white/70'
                    }`}
                  >
                    <Icon className="w-5 h-5" />
                    <span className="font-roboto font-medium">{label}</span>
                    {badge && (
                      <span className="ml-auto px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 text-xs font-medium">
                        {badge}
                      </span>
                    )}
                    {disabled && (
                      <span className="font-roboto text-xs text-white/30 ml-auto">No data</span>
                    )}
                  </button>
                ))}
              </div>

              <div className="absolute bottom-6 left-6 right-6 text-center">
                <p className="font-roboto text-white/40 text-xs">Etho v17</p>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      <AnimatePresence mode="wait">
        {currentPage === 'hero' && page('hero',
          <Hero onGetStarted={() => setCurrentPage('landing')} />
        )}

        {currentPage === 'landing' && page('landing',
          <Landing
            onAnalysisComplete={handleAnalysisComplete}
            petId={activePetId}
            onChangePet={setActivePetId}
            onViewTimeline={openTimeline}
          />
        )}

        {currentPage === 'pets' && page('pets',
          <Pets
            activePetId={activePetId}
            onSelectPet={setActivePetId}
            onViewTimeline={openTimeline}
          />
        )}

        {currentPage === 'timeline' && page('timeline',
          <Timeline
            petId={activePetId}
            onOpenVetReport={openVetReport}
            onUpload={() => navigateTo('landing')}
            onOpenAnalysis={openAnalysis}
          />
        )}

        {currentPage === 'analysis' && page('analysis',
          <AnalysisDetail
            analysisId={detailAnalysisId}
            onBack={() => navigateTo('timeline')}
          />
        )}

        {currentPage === 'vetreport' && page('vetreport',
          <VetReport petId={reportPetId} onBack={() => navigateTo('timeline')} />
        )}

        {currentPage === 'dashboard' && page('dashboard',
          <Dashboard
            analysisData={analysisData}
            videoUrl={videoUrl}
            mediaType={mediaType}
            onViewTimeline={activePetId ? () => openTimeline(activePetId) : null}
          />
        )}

        {currentPage === 'about' && page('about', <About />)}
        {currentPage === 'biometrics' && page('biometrics', <Biometrics />)}
      </AnimatePresence>
    </div>
  );
}

export default App;
