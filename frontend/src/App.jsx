import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Menu, X, Home, Info, BarChart3, Activity, Upload, Lock } from 'lucide-react';
import Hero from './pages/Hero';
import Landing from './pages/Landing';
import Dashboard from './pages/Dashboard';
import About from './pages/About';
import Biometrics from './pages/Biometrics';

const PASSWORD = 'etho2024';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [passwordInput, setPasswordInput] = useState('');
  const [passwordError, setPasswordError] = useState(false);
  const [currentPage, setCurrentPage] = useState('hero');
  const [menuOpen, setMenuOpen] = useState(false);
  const [analysisData, setAnalysisData] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);

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

  const handleGetStarted = () => {
    setCurrentPage('landing');
  };

  const handleAnalysisComplete = (data, url) => {
    setAnalysisData(data);
    setVideoUrl(url);
    setCurrentPage('dashboard');
  };

  const navigateTo = (page) => {
    setCurrentPage(page);
    setMenuOpen(false);
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
              onError={(e) => {
                e.target.style.display = 'none';
              }}
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

  // Don't show menu on hero page
  const showMenu = currentPage !== 'hero';

  return (
    <div className="relative min-h-screen font-roboto">
      {/* Navigation Menu Button */}
      {showMenu && (
        <button
          onClick={() => setMenuOpen(!menuOpen)}
          className="fixed top-4 right-4 z-50 p-3 glass-card rounded-full hover:bg-white/30 transition-colors"
        >
          {menuOpen ? (
            <X className="w-5 h-5 text-white" />
          ) : (
            <Menu className="w-5 h-5 text-white" />
          )}
        </button>
      )}

      {/* Slide-out Menu */}
      <AnimatePresence>
        {menuOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMenuOpen(false)}
              className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40"
            />
            
            <motion.div
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              className="fixed right-0 top-0 h-full w-72 z-50 p-6"
              style={{
                background: 'rgba(255, 255, 255, 0.15)',
                backdropFilter: 'blur(20px)',
                borderLeft: '1px solid rgba(255, 255, 255, 0.2)'
              }}
            >
              <div className="mt-16 space-y-1">
                <button
                  onClick={() => navigateTo('hero')}
                  className={`w-full flex items-center gap-3 p-4 rounded-xl transition-colors ${
                    currentPage === 'hero' 
                      ? 'bg-white/20 text-white' 
                      : 'hover:bg-white/10 text-white/70'
                  }`}
                >
                  <Home className="w-5 h-5" />
                  <span className="font-roboto font-medium">Home</span>
                </button>

                <button
                  onClick={() => navigateTo('landing')}
                  className={`w-full flex items-center gap-3 p-4 rounded-xl transition-colors ${
                    currentPage === 'landing' 
                      ? 'bg-white/20 text-white' 
                      : 'hover:bg-white/10 text-white/70'
                  }`}
                >
                  <Home className="w-5 h-5" />
                  <span className="font-roboto font-medium">Upload Video</span>
                </button>
                
                <button
                  onClick={() => navigateTo('dashboard')}
                  disabled={!analysisData}
                  className={`w-full flex items-center gap-3 p-4 rounded-xl transition-colors ${
                    currentPage === 'dashboard' 
                      ? 'bg-white/20 text-white' 
                      : analysisData 
                        ? 'hover:bg-white/10 text-white/70'
                        : 'text-white/30 cursor-not-allowed'
                  }`}
                >
                  <BarChart3 className="w-5 h-5" />
                  <span className="font-roboto font-medium">Analysis</span>
                  {!analysisData && (
                    <span className="font-roboto text-xs text-white/30 ml-auto">No data</span>
                  )}
                </button>
                
                <button
                  onClick={() => navigateTo('about')}
                  className={`w-full flex items-center gap-3 p-4 rounded-xl transition-colors ${
                    currentPage === 'about' 
                      ? 'bg-white/20 text-white' 
                      : 'hover:bg-white/10 text-white/70'
                  }`}
                >
                  <Info className="w-5 h-5" />
                  <span className="font-roboto font-medium">Research</span>
                </button>

                <button
                  onClick={() => navigateTo('biometrics')}
                  className={`w-full flex items-center gap-3 p-4 rounded-xl transition-colors ${
                    currentPage === 'biometrics' 
                      ? 'bg-white/20 text-white' 
                      : 'hover:bg-white/10 text-white/70'
                  }`}
                >
                  <Activity className="w-5 h-5" />
                  <span className="font-roboto font-medium">Biometrics</span>
                  <span className="ml-auto px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 text-xs font-medium">New</span>
                </button>
              </div>

              <div className="absolute bottom-6 left-6 right-6 text-center">
                <p className="font-roboto text-white/40 text-xs">Etho v3.0</p>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Page Content */}
      <AnimatePresence mode="wait">
        {currentPage === 'hero' && (
          <motion.div
            key="hero"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <Hero onGetStarted={handleGetStarted} />
          </motion.div>
        )}

        {currentPage === 'landing' && (
          <motion.div
            key="landing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <Landing onAnalysisComplete={handleAnalysisComplete} />
          </motion.div>
        )}
        
        {currentPage === 'dashboard' && (
          <motion.div
            key="dashboard"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <Dashboard analysisData={analysisData} videoUrl={videoUrl} />
          </motion.div>
        )}
        
        {currentPage === 'about' && (
          <motion.div
            key="about"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <About />
          </motion.div>
        )}

        {currentPage === 'biometrics' && (
          <motion.div
            key="biometrics"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <Biometrics />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default App;
