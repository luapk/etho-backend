import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import Footer from '../components/Footer';

function Hero({ onGetStarted }) {
  // Randomly select a dog image once on initial render (not in useEffect to avoid flash)
  const dogImage = useMemo(() => {
    const randomNum = Math.floor(Math.random() * 5) + 1;
    return `/dog-${randomNum}.png`;
  }, []);

  return (
    <div className="min-h-screen relative overflow-hidden flex flex-col items-center justify-center px-6">
      {/* Background Dog Image - Full vivid display, minimal overlay */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <img 
          src={dogImage}
          alt=""
          loading="eager"
          fetchpriority="high"
          className="absolute inset-0 w-full h-full object-cover"
          style={{ 
            objectPosition: 'center top'
          }}
          onError={(e) => e.target.style.display = 'none'}
        />
        {/* Minimal overlay only at edges for text readability - keeps image vivid */}
        <div className="absolute inset-0 bg-gradient-to-b from-black/20 via-transparent to-black/30"></div>
      </div>

      {/* Content */}
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8 }}
        className="relative z-10 text-center max-w-4xl"
      >
        {/* Combined Glass Panel - Logo + Tagline + Subline */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="mb-10 p-8 md:p-10 rounded-3xl mx-auto max-w-2xl"
          style={{
            background: 'rgba(255, 255, 255, 0.1)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            border: '1px solid rgba(255, 255, 255, 0.18)',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.12)'
          }}
        >
          {/* Logo inside panel */}
          <div className="mb-6 relative">
            <img 
              src="/etho-logo.png" 
              alt="Etho" 
              className="h-14 mx-auto drop-shadow-lg" 
              onError={(e) => {
                e.target.style.display = 'none';
                e.target.nextSibling.style.display = 'block';
              }} 
            />
            <span className="font-roboto font-bold text-4xl text-white hidden drop-shadow-2xl">ETHO</span>
            {/* BETA Tag */}
            <span className="absolute -top-2 -right-4 md:right-[calc(50%-80px)] px-2 py-0.5 bg-cyan-500 text-white text-xs font-bold rounded-full uppercase tracking-wider">
              Beta
            </span>
          </div>

          {/* Headline */}
          <h1
            className="font-roboto font-bold text-4xl md:text-5xl lg:text-6xl text-white drop-shadow-lg"
            style={{ lineHeight: 1.15 }}
          >
            Closing the<br />translation gap.
          </h1>
          
          {/* Subline */}
          <p className="font-roboto text-lg text-white/80 mt-6 max-w-xl mx-auto">
            AI-powered pet behavior analysis backed by ethological research
          </p>
        </motion.div>

        {/* CTA Button - Glassmorphism with distinct hover */}
        <motion.button
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          whileHover={{ scale: 1.05, y: -3 }}
          whileTap={{ scale: 0.98 }}
          onClick={onGetStarted}
          className="group inline-flex items-center gap-3 px-10 py-4 rounded-full font-roboto font-bold text-lg transition-all duration-300 text-white"
          style={{
            background: 'rgba(255, 255, 255, 0.18)',
            backdropFilter: 'blur(12px)',
            WebkitBackdropFilter: 'blur(12px)',
            border: '1px solid rgba(255, 255, 255, 0.25)',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.15)'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(255, 255, 255, 0.95)';
            e.currentTarget.style.color = '#3b82f6';
            e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.9)';
            e.currentTarget.style.boxShadow = '0 16px 48px rgba(0, 0, 0, 0.25)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'rgba(255, 255, 255, 0.18)';
            e.currentTarget.style.color = 'white';
            e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.25)';
            e.currentTarget.style.boxShadow = '0 8px 32px rgba(0, 0, 0, 0.15)';
          }}
        >
          Try it out
          <ArrowRight className="w-5 h-5 transition-transform duration-300 group-hover:translate-x-1" />
        </motion.button>
      </motion.div>

      {/* Footer */}
      <div className="absolute bottom-0 left-0 right-0 z-10">
        <Footer />
      </div>
    </div>
  );
}

export default Hero;
