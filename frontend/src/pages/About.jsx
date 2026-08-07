import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
  BookOpen, 
  Brain, 
  Eye, 
  Volume2, 
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Microscope,
  Activity,
  PawPrint
} from 'lucide-react';
import Footer from '../components/Footer';

function About() {
  const [expandedFramework, setExpandedFramework] = useState(null);
  const [bgImage, setBgImage] = useState('/dog-1.png');
  
  // Random background image on mount
  useEffect(() => {
    const randomNum = Math.floor(Math.random() * 5) + 1;
    setBgImage(`/dog-${randomNum}.png`);
  }, []);

  // Single color for all categories - light blue
  const categoryColor = '#38bdf8';

  const frameworks = [
    {
      name: "DogFACS",
      fullName: "Dog Facial Action Coding System",
      citation: "Waller, B. M., Peirce, K., Caeiro, C. C., et al. (2013)",
      journal: "PLOS ONE",
      description: "An anatomically-based system for objectively coding facial movements in dogs. Adapted from the human FACS system developed by Ekman and Friesen.",
      icon: Eye,
      category: 'Visual Analysis',
      keyFindings: [
        "EAD101 (Inner Brow Raiser) — Associated with 'puppy dog eyes', increases in shelter dogs when humans are watching",
        "EAD103 (Ear Flattener) — Correlates with negative emotional states and fear",
        "AD19 (Tongue Show) — Can indicate stress, appeasement, or relaxation depending on context",
        "AD137 (Lip Licking) — Displacement behavior indicating mild stress or anticipation",
        "AU101+AU102 (Blink) — Rapid blinking correlates with arousal; slow blinking with relaxation"
      ],
      methodology: "Trained coders identify 17 action units based on underlying muscle movements. Each AU is coded for presence/absence and intensity. Inter-rater reliability established via Cohen's kappa."
    },
    {
      name: "Feline Grimace Scale (FGS)",
      fullName: "Validated Acute Pain Assessment Tool for Cats",
      citation: "Evangelista, M. C., Watanabe, R., Leung, V. S. Y., et al. (2019)",
      journal: "Scientific Reports",
      description: "A validated tool for assessing acute pain in cats using five facial action units. Scores ≥0.39/1.0 indicate pain requiring intervention.",
      icon: Eye,
      category: 'Visual Analysis',
      keyFindings: [
        "Ear Position — Ears rotated outward or flattened indicate pain",
        "Orbital Tightening — Squinted or partially closed eyes",
        "Muzzle Tension — Tension in the muzzle area, rounded appearance",
        "Whisker Position — Whiskers held straight out or pushed forward",
        "Head Position — Head held below shoulder line, reluctance to move"
      ],
      methodology: "Each of 5 action units scored 0-2, yielding total 0-10 normalized to 0-1. Sensitivity 91%, specificity 89%. Responds to analgesic treatment (scores decrease post-pain relief)."
    },
    {
      name: "C-BARQ",
      fullName: "Canine Behavioral Assessment & Research Questionnaire",
      citation: "Serpell, J. A. & Hsu, Y. (2005)",
      journal: "University of Pennsylvania School of Veterinary Medicine",
      description: "Standardized questionnaire for measuring breed-typical behavior and temperament in dogs. Used to establish behavioral baselines across 100+ breeds.",
      icon: PawPrint,
      category: 'Behavioral Assessment',
      keyFindings: [
        "14 behavioral factors identified across breeds",
        "Stranger-directed aggression varies significantly by breed",
        "Owner-directed aggression is NOT strongly breed-dependent",
        "Trainability correlates with working dog heritage",
        "Fear/anxiety scores help contextualize individual behavior"
      ],
      methodology: "101-item questionnaire completed by owners. Factor analysis yields 14 subscales. Normative data from 15,000+ dogs enables breed-specific baselines. Used in genetics studies linking behavior to specific loci."
    },
    {
      name: "Morton's Motivation-Structural Rules",
      fullName: "Acoustic Communication Theory",
      citation: "Morton, E. S. (1977)",
      journal: "The American Naturalist",
      description: "Foundational theory explaining how acoustic properties of animal vocalizations convey motivation and emotional state across species.",
      icon: Volume2,
      category: 'Audio Analysis',
      keyFindings: [
        "Low-frequency, harsh sounds → Aggression, dominance, confidence",
        "High-frequency, tonal sounds → Fear, submission, friendliness",
        "Rapid frequency modulation → Excitement, high arousal",
        "Longer calls → Greater intensity of motivation",
        "Rules apply across mammals and birds due to shared evolutionary pressures"
      ],
      methodology: "Comparative acoustic analysis across species. Validated through playback experiments showing consistent receiver responses to synthesized calls matching predicted patterns."
    },
    {
      name: "Canine Bio-Acoustics",
      fullName: "Dog Bark and Growl Emotional Content Research",
      citation: "Pongrácz, P., Molnár, C., Miklósi, Á., Faragó, T., et al. (2005-2017)",
      journal: "Applied Animal Behaviour Science / Animal Cognition",
      description: "Series of studies demonstrating that dogs encode specific emotional and contextual information in their vocalizations, and that humans can decode this information.",
      icon: Volume2,
      category: 'Audio Analysis',
      keyFindings: [
        "Bark contexts (stranger, play, alone) distinguishable by acoustic features",
        "Growl contexts distinguishable — play growls shorter, higher-pitched",
        "Food-guarding growls: longest duration, lowest frequency",
        "Humans correctly categorize bark contexts 60-80% of time",
        "Dog owners outperform non-owners in bark interpretation"
      ],
      methodology: "Acoustic analysis of recorded vocalizations across contexts. Playback experiments with human listeners. Spectrographic analysis of fundamental frequency (f0), formant structure, and duration."
    },
    {
      name: "Meowsic Project",
      fullName: "Cat Vocalization Research",
      citation: "Schötz, S., van de Weijer, J., & Eklund, R. (2016-2022)",
      journal: "Lund University Humanities Lab",
      description: "Interdisciplinary research project studying phonetic variation in cat vocalizations, particularly human-directed meows.",
      icon: Volume2,
      category: 'Audio Analysis',
      keyFindings: [
        "Rising melodic contour (f0↑) → Friendly, solicitation contexts",
        "Falling melodic contour (f0↓) → Complaint, frustration, demands",
        "Flat sustained tone → Urgent demands, distress",
        "Individual cats develop unique vocal patterns with their owners",
        "Cats modify vocalizations based on human response patterns"
      ],
      methodology: "Phonetic analysis using Praat software. Recording of cats in naturalistic home environments. Perceptual experiments with human listeners rating valence and urgency."
    },
    {
      name: "McGreevy Skull Morphology",
      fullName: "Behavioral Correlates of Skull Shape in Dogs",
      citation: "McGreevy, P. D., Georgevsky, D., Carrasco, J., et al. (2013)",
      journal: "PLOS ONE",
      description: "Research demonstrating that skull shape (cephalic index) correlates with behavioral tendencies and how dogs perceive the world.",
      icon: Microscope,
      category: 'Morphology',
      keyFindings: [
        "Brachycephalic (flat-faced) breeds show reduced facial signal clarity",
        "Dolichocephalic (long-nosed) breeds: better peripheral vision, may show more gaze-following",
        "Eye placement affects visual field — impacts social attention",
        "Facial muscle structure varies — affects expression range",
        "Implications for human reading of dog emotions by breed type"
      ],
      methodology: "Correlation of cephalic index measurements with C-BARQ behavioral scores across 8,000+ dogs. Geometric morphometric analysis of skull shapes."
    },
    {
      name: "Stress Physiology Research",
      fullName: "Physiological Indicators of Stress in Companion Animals",
      citation: "Beerda, B., Schilder, M. B. H., et al. (1997-2000)",
      journal: "Physiology & Behavior / Applied Animal Behaviour Science",
      description: "Foundational research linking behavioral signals to physiological stress markers (cortisol, heart rate) in dogs.",
      icon: Activity,
      category: 'Behavioral Assessment',
      keyFindings: [
        "Lip licking, yawning, body shaking correlate with elevated cortisol",
        "Paw lifting and low posture indicate acute stress",
        "Repetitive behaviors (pacing, circling) indicate chronic stress",
        "Recovery time to baseline HR indicates stress coping ability",
        "Individual variation exists — context is critical"
      ],
      methodology: "Cortisol measurement via blood/saliva samples. Heart rate monitoring. Behavioral coding synchronized with physiological measures during controlled stressors."
    },
    {
      name: "Feline Five Personality Model",
      fullName: "Five-Factor Model of Cat Personality",
      citation: "Litchfield, C. A., Quinton, G., Tindle, H., et al. (2017)",
      journal: "PLOS ONE",
      description: "Validated personality assessment for domestic cats identifying five reliable personality factors.",
      icon: PawPrint,
      category: 'Behavioral Assessment',
      keyFindings: [
        "Neuroticism — Anxiety, fear, insecurity vs. stability",
        "Extraversion — Curiosity, activity, playfulness",
        "Dominance — Aggression, bullying of other cats",
        "Impulsiveness — Erratic, reckless behavior",
        "Agreeableness — Affection, friendliness to people"
      ],
      methodology: "52-item questionnaire completed by cat owners. Factor analysis yielded 5 robust factors. Validated across 2,800+ cats. Useful for predicting shelter adoption outcomes."
    },
    {
      name: "HRV in Companion Animals",
      fullName: "Heart Rate Variability as Welfare Indicator",
      citation: "Zupan, M., Buskas, J., Altimiras, J., & Keeling, L. J. (2016)",
      journal: "Animals / Applied Animal Behaviour Science",
      description: "Research establishing heart rate variability (HRV) as a non-invasive measure of autonomic balance and emotional state in dogs and cats.",
      icon: Activity,
      category: 'Biometrics',
      keyFindings: [
        "RMSSD (HRV metric) decreases during acute stress",
        "Higher baseline HRV correlates with better stress coping",
        "Recovery of HRV post-stressor indicates resilience",
        "Breed differences exist in baseline HRV",
        "Combined with behavior, HRV improves welfare assessment accuracy"
      ],
      methodology: "ECG or optical HR monitors. Time-domain and frequency-domain HRV analysis. Correlation with behavioral observations and cortisol measures."
    }
  ];

  const limitations = [
    {
      title: "Breed Variations",
      description: "Brachycephalic breeds have reduced facial signal clarity. Spitz breeds' curled tails don't indicate arousal. We adjust for these."
    },
    {
      title: "Individual Differences", 
      description: "Some pets are naturally more vocal or expressive. Baseline behavior varies by individual temperament and history."
    },
    {
      title: "Context Dependency",
      description: "The same behavior can mean different things in different situations. A yawn during play differs from a yawn when cornered."
    },
    {
      title: "Video Limitations",
      description: "Camera angle, lighting, and video quality affect signal detection. Subtle signals may be missed in poor footage."
    },
    {
      title: "Not Medical Advice",
      description: "Etho provides behavioral insights, not diagnoses. Always consult a veterinarian or certified behaviorist for health concerns."
    }
  ];

  return (
    <div className="min-h-screen relative">
      {/* Background Pet Image */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <img 
          src={bgImage}
          alt=""
          className="absolute top-0 right-0 w-auto h-full object-cover opacity-20"
          style={{ objectPosition: 'right top' }}
          onError={(e) => e.target.style.display = 'none'}
        />
        <div className="absolute inset-0 bg-gradient-to-l from-transparent via-blue-500/80 to-blue-500"></div>
      </div>

      {/* Header */}
      <header className="relative py-6 px-6">
        <div className="max-w-5xl mx-auto flex justify-center">
          <img 
            src="/etho-logo.png" 
            alt="Etho" 
            className="h-10" 
            onError={(e) => {
              e.target.style.display = 'none';
              e.target.nextSibling.style.display = 'block';
            }} 
          />
          <span className="font-roboto font-bold text-3xl text-white hidden drop-shadow-lg">Etho</span>
        </div>
      </header>

      <div className="relative max-w-4xl mx-auto px-6 pb-12 space-y-8">
        
        {/* Title */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center"
        >
          <h1 className="text-4xl font-bold text-white mb-4 drop-shadow-lg font-roboto">Research & Methods</h1>
          <p className="text-white/90 text-lg max-w-2xl mx-auto font-roboto">
            Etho's analysis is grounded in peer-reviewed ethological research. Here's the science behind what we do.
          </p>
        </motion.div>

        {/* How It Works */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="glass-card rounded-2xl p-6"
        >
          <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-2 font-roboto">
            <Brain className="w-5 h-5 text-white/70" />
            How Etho Analyzes Your Pet
          </h2>
          
          <div className="grid md:grid-cols-3 gap-6">
            <div className="text-center">
              <div className="w-12 h-12 glass-card rounded-full flex items-center justify-center mx-auto mb-3">
                <Eye className="w-6 h-6 text-white" />
              </div>
              <h3 className="text-white font-medium mb-2 font-roboto">Visual Analysis</h3>
              <p className="text-white/80 text-sm font-roboto">
                Facial expressions coded using DogFACS and Feline Grimace Scale. Body posture analyzed for tension and orientation.
              </p>
            </div>
            
            <div className="text-center">
              <div className="w-12 h-12 glass-card rounded-full flex items-center justify-center mx-auto mb-3">
                <Volume2 className="w-6 h-6 text-white" />
              </div>
              <h3 className="text-white font-medium mb-2 font-roboto">Audio Analysis</h3>
              <p className="text-white/80 text-sm font-roboto">
                Vocalizations classified using Morton's Rules and bio-acoustic research on pitch, duration, and harmonic structure.
              </p>
            </div>
            
            <div className="text-center">
              <div className="w-12 h-12 glass-card rounded-full flex items-center justify-center mx-auto mb-3">
                <Brain className="w-6 h-6 text-white" />
              </div>
              <h3 className="text-white font-medium mb-2 font-roboto">Triangulation</h3>
              <p className="text-white/80 text-sm font-roboto">
                Visual, audio, context, and breed data combined. Confidence-weighted scoring accounts for signal clarity.
              </p>
            </div>
          </div>
        </motion.div>

        {/* Research Frameworks - Expandable */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="space-y-3"
        >
          <h2 className="text-xl font-bold text-white flex items-center gap-2 font-roboto mb-4">
            <BookOpen className="w-5 h-5 text-white/70" />
            Research Frameworks We Use
          </h2>
          
          {frameworks.map((framework, idx) => {
            const isExpanded = expandedFramework === idx;
            
            return (
              <motion.div
                key={framework.name}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.05 * idx }}
                className="glass-card rounded-xl overflow-hidden"
              >
                <button
                  onClick={() => setExpandedFramework(isExpanded ? null : idx)}
                  className="w-full p-4 flex items-center gap-4 hover:bg-white/5 transition-colors"
                >
                  <div 
                    className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                    style={{ backgroundColor: `${categoryColor}20` }}
                  >
                    <framework.icon className="w-5 h-5" style={{ color: categoryColor }} />
                  </div>
                  <div className="flex-1 text-left">
                    <h3 className="text-white font-semibold font-roboto">{framework.name}</h3>
                    <p className="text-white/60 text-xs font-roboto">{framework.fullName}</p>
                  </div>
                  <span 
                    className="px-2 py-0.5 rounded text-xs font-roboto"
                    style={{ backgroundColor: `${categoryColor}20`, color: categoryColor }}
                  >
                    {framework.category}
                  </span>
                  {isExpanded ? <ChevronUp className="w-5 h-5 text-white/50" /> : <ChevronDown className="w-5 h-5 text-white/50" />}
                </button>
                
                {isExpanded && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="px-4 pb-4 border-t border-white/10"
                  >
                    <div className="pt-4 space-y-4">
                      <p className="text-white/90 text-sm font-roboto">{framework.description}</p>
                      
                      <div>
                        <h4 className="text-white font-medium text-sm mb-2 font-roboto">Key Findings:</h4>
                        <ul className="space-y-1.5">
                          {framework.keyFindings.map((finding, i) => (
                            <li key={i} className="text-white/80 text-sm flex items-start gap-2 font-roboto">
                              <CheckCircle className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: categoryColor }} />
                              {finding}
                            </li>
                          ))}
                        </ul>
                      </div>
                      
                      {framework.methodology && (
                        <div className="p-3 rounded-lg" style={{ backgroundColor: 'rgba(255,255,255,0.08)' }}>
                          <h4 className="text-white/70 text-xs font-medium mb-1 font-roboto uppercase tracking-wider">Methodology</h4>
                          <p className="text-white/80 text-xs font-roboto">{framework.methodology}</p>
                        </div>
                      )}
                      
                      <p className="text-white/50 text-xs font-roboto">
                        {framework.citation} — <span className="italic">{framework.journal}</span>
                      </p>
                    </div>
                  </motion.div>
                )}
              </motion.div>
            );
          })}
        </motion.div>

        {/* Limitations */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="glass-card rounded-2xl p-6"
          style={{ backgroundColor: 'rgba(245, 158, 11, 0.15)' }}
        >
          <h2 className="text-xl font-bold text-amber-200 mb-4 flex items-center gap-2 font-roboto">
            <AlertTriangle className="w-5 h-5" />
            Important Limitations
          </h2>
          
          <div className="grid md:grid-cols-2 gap-4">
            {limitations.map((limitation, idx) => (
              <div key={idx} className="p-4 rounded-lg" style={{ backgroundColor: 'rgba(255,255,255,0.08)' }}>
                <h3 className="text-white font-medium mb-1 font-roboto">{limitation.title}</h3>
                <p className="text-white/80 text-sm font-roboto">{limitation.description}</p>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Distress Scale - Improved legibility */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="glass-card rounded-2xl p-6"
        >
          <h2 className="text-xl font-bold text-white mb-4 font-roboto">Understanding the Distress Score</h2>
          
          <p className="text-white/90 text-sm mb-4 font-roboto">
            The 0-100 distress score is calculated by weighting multiple behavioral signals against their research-established correlations with emotional valence and arousal.
          </p>
          
          <div className="space-y-3">
            <div className="flex items-center gap-4 p-4 rounded-xl" style={{ backgroundColor: 'rgba(34, 197, 94, 0.2)' }}>
              <div className="w-14 h-14 bg-green-500 rounded-full flex items-center justify-center text-white font-bold font-roboto flex-shrink-0">
                0-33
              </div>
              <div>
                <h3 className="text-white font-semibold font-roboto">Low Distress</h3>
                <p className="text-white/90 text-sm font-roboto">
                  Positive valence indicators. Relaxed musculature, soft gaze, parasympathetic dominance.
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-4 p-4 rounded-xl" style={{ backgroundColor: 'rgba(245, 158, 11, 0.2)' }}>
              <div className="w-14 h-14 bg-amber-500 rounded-full flex items-center justify-center text-white font-bold font-roboto flex-shrink-0">
                34-66
              </div>
              <div>
                <h3 className="text-white font-semibold font-roboto">Moderate Distress</h3>
                <p className="text-white/90 text-sm font-roboto">
                  Mixed or ambiguous signals. Could indicate excitement, mild stress, or demand behavior. Context-dependent.
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-4 p-4 rounded-xl" style={{ backgroundColor: 'rgba(239, 68, 68, 0.2)' }}>
              <div className="w-14 h-14 bg-red-500 rounded-full flex items-center justify-center text-white font-bold font-roboto flex-shrink-0">
                67+
              </div>
              <div>
                <h3 className="text-white font-semibold font-roboto">Elevated Distress</h3>
                <p className="text-white/90 text-sm font-roboto">
                  Clear negative valence indicators. Sympathetic nervous system activation. Consider intervention.
                </p>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Further Reading */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
          className="glass-card rounded-2xl p-6"
        >
          <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2 font-roboto">
            <ExternalLink className="w-5 h-5 text-white/70" />
            Further Reading
          </h2>
          
          <div className="space-y-3 text-white/90 text-sm font-roboto">
            <p>
              <strong className="text-white">For Pet Owners:</strong> "The Other End of the Leash" by Patricia McConnell, PhD — Accessible introduction to animal behavior science.
            </p>
            <p>
              <strong className="text-white">For Professionals:</strong> "Canine and Feline Behavior for Veterinary Technicians and Nurses" — Clinical applications of behavioral assessment.
            </p>
            <p>
              <strong className="text-white">Academic Resources:</strong> Applied Animal Behaviour Science journal, Animal Cognition journal, and the ISAE (International Society for Applied Ethology) proceedings.
            </p>
          </div>
        </motion.div>

        {/* Footer */}
        <Footer />
      </div>
    </div>
  );
}

export default About;
