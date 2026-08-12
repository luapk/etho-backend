import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Menu, X, Home, Info, Activity, Lock, PawPrint, Upload } from 'lucide-react';
import { listPets } from './api';
import Hero from './pages/Hero';
import Landing from './pages/Landing';
import Dashboard from './pages/Dashboard';
import About from './pages/About';
import Biometrics from './pages/Biometrics';
import Pets from './pages/Pets';
import VetReport from './pages/VetReport';
import PetPage from './pages/PetPage';

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

  // The pet new captures are filed against. Remembered between visits so a
  // guardian isn't re-picking their pet on every upload.
  const [activePetId, setActivePetId] = useState(
    () => localStorage.getItem(ACTIVE_PET_KEY) || null
  );
  const [reportPetId, setReportPetId] = useState(null);
  // Which tab the pet page should open on, and which observation (if any).
  const [petTab, setPetTab] = useState('timeline');
  const [openAnalysisId, setOpenAnalysisId] = useState(null);
  const [booting, setBooting] = useState(false);

  useEffect(() => {
    if (activePetId) localStorage.setItem(ACTIVE_PET_KEY, activePetId);
    else localStorage.removeItem(ACTIVE_PET_KEY);
  }, [activePetId]);

  const handlePasswordSubmit = (e) => {
    e.preventDefault();
    if (passwordInput !== PASSWORD) {
      setPasswordError(true);
      setPasswordInput('');
      return;
    }
    setIsAuthenticated(true);
    setPasswordError(false);
    // Straight to the pet, not to a splash screen. Someone who has already
    // added a pet is opening the app to check on them; a returning user should
    // land on their record. Only a first-timer needs the welcome question.
    setBooting(true);
    listPets()
      .then((pets) => {
        if (!pets.length) { setCurrentPage('landing'); return; }
        const remembered = pets.find((p) => p.id === activePetId);
        const target = remembered || pets[0];
        setActivePetId(target.id);
        setPetTab('timeline');
        setCurrentPage('pet');
      })
      .catch(() => setCurrentPage('landing'))
      .finally(() => setBooting(false));
  };

  const handleAnalysisComplete = (data, url, kind) => {
    setAnalysisData(data);
    setVideoUrl(url);
    setMediaType(kind || null);
    // A fresh result belongs in the pet's record, opened as the observation
    // tab so the timeline it just joined is one tap away. An unassigned
    // one-off has no record to sit in, so it gets the standalone screen.
    if (data?.analysis_id && data?.pet_id) {
      setActivePetId(data.pet_id);
      setOpenAnalysisId(data.analysis_id);
      navigateTo('pet');
    } else {
      navigateTo('dashboard');
    }
  };

  const navigateTo = (page) => {
    setCurrentPage(page);
    setMenuOpen(false);
  };

  const openPet = (petId, tab = 'timeline') => {
    if (petId) setActivePetId(petId);
    setOpenAnalysisId(null);
    setPetTab(tab);
    navigateTo('pet');
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

  // Between the password and knowing which pet to open, the page would
  // otherwise render the hero for a beat and then jump. A quiet hold is
  // better than a flash of a screen nobody asked for.
  if (booting) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <img src="/etho-logo.png" alt="Etho" className="h-10 opacity-70 animate-pulse"
             onError={(e) => { e.target.style.display = 'none'; }} />
      </div>
    );
  }

  const showMenu = currentPage !== 'hero';

  // Timeline and the latest analysis are no longer destinations — they are
  // tabs inside the pet, so the nav lists the pet itself instead.
  const navItems = [
    ...(activePetId ? [{ id: 'pet', label: 'Your pet', icon: PawPrint }] : []),
    { id: 'landing', label: 'Add an observation', icon: Upload },
    { id: 'pets', label: 'My pets', icon: PawPrint },
    { id: 'about', label: 'Research', icon: Info },
    { id: 'biometrics', label: 'Biometrics', icon: Activity, badge: 'New' },
    { id: 'hero', label: 'About Etho', icon: Home },
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
          <Hero onGetStarted={() => (activePetId ? openPet(activePetId) : navigateTo('landing'))} />
        )}

        {currentPage === 'landing' && page('landing',
          <Landing
            onAnalysisComplete={handleAnalysisComplete}
            petId={activePetId}
            onChangePet={setActivePetId}
            onViewTimeline={(id) => openPet(id, 'timeline')}
            onManagePets={() => navigateTo('pets')}
          />
        )}

        {currentPage === 'pets' && page('pets',
          <Pets
            activePetId={activePetId}
            onSelectPet={setActivePetId}
            onViewTimeline={(id) => openPet(id, 'timeline')}
            onOpenProfile={(id) => openPet(id, 'profile')}
          />
        )}

        {currentPage === 'pet' && page('pet',
          <PetPage
            petId={activePetId}
            initialTab={petTab}
            openAnalysisId={openAnalysisId}
            onChangePet={(id) => openPet(id, 'timeline')}
            onAddObservation={() => navigateTo('landing')}
            onOpenVetReport={openVetReport}
            onManagePets={() => navigateTo('pets')}
          />
        )}

        {currentPage === 'vetreport' && page('vetreport',
          <VetReport petId={reportPetId} onBack={() => openPet(reportPetId, 'timeline')} />
        )}

        {currentPage === 'dashboard' && page('dashboard',
          <Dashboard
            analysisData={analysisData}
            videoUrl={videoUrl}
            mediaType={mediaType}
            onViewTimeline={activePetId ? () => openPet(activePetId, 'timeline') : null}
          />
        )}

        {currentPage === 'about' && page('about', <About />)}
        {currentPage === 'biometrics' && page('biometrics', <Biometrics />)}
      </AnimatePresence>
    </div>
  );
}

export default App;
