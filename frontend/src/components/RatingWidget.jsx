import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Star, ThumbsUp, ThumbsDown, X, Send, CheckCircle } from 'lucide-react';

// Store ratings in localStorage for persistence
const STORAGE_KEY = 'etho_ratings';

const getRatings = () => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
};

const saveRating = (rating) => {
  try {
    const existing = getRatings();
    existing.push({ ...rating, timestamp: Date.now() });
    localStorage.setItem(STORAGE_KEY, JSON.stringify(existing));
  } catch (e) {
    console.error('Failed to save rating:', e);
  }
};

// Export function to get rating stats (for admin access)
export const getRatingStats = () => {
  const ratings = getRatings();
  if (ratings.length === 0) return null;
  
  const totalRatings = ratings.length;
  const avgAccuracy = ratings.reduce((sum, r) => sum + r.accuracy, 0) / totalRatings;
  const avgHelpfulness = ratings.reduce((sum, r) => sum + r.helpfulness, 0) / totalRatings;
  
  const issueCounts = {};
  ratings.forEach(r => {
    r.issues?.forEach(issue => {
      issueCounts[issue] = (issueCounts[issue] || 0) + 1;
    });
  });
  
  return {
    totalRatings,
    avgAccuracy: avgAccuracy.toFixed(1),
    avgHelpfulness: avgHelpfulness.toFixed(1),
    issueCounts,
    ratings
  };
};

const QUICK_ISSUES = [
  { id: 'wrong_species', label: 'Wrong species detected' },
  { id: 'wrong_breed', label: 'Wrong breed detected' },
  { id: 'score_too_high', label: 'Distress score too high' },
  { id: 'score_too_low', label: 'Distress score too low' },
  { id: 'missing_signals', label: 'Missed behavioral signals' },
  { id: 'wrong_interpretation', label: 'Interpretation was off' },
  { id: 'recommendation_unhelpful', label: 'Recommendation not helpful' },
  { id: 'subtitle_inaccurate', label: 'Pet subtitles inaccurate' }
];

function RatingWidget({ analysisId, species, breed, distressScore }) {
  const [isOpen, setIsOpen] = useState(false);
  const [accuracy, setAccuracy] = useState(0);
  const [helpfulness, setHelpfulness] = useState(0);
  const [selectedIssues, setSelectedIssues] = useState([]);
  const [additionalFeedback, setAdditionalFeedback] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = () => {
    const rating = {
      analysisId,
      species,
      breed,
      distressScore,
      accuracy,
      helpfulness,
      issues: selectedIssues,
      feedback: additionalFeedback
    };
    
    saveRating(rating);
    setSubmitted(true);
    
    setTimeout(() => {
      setIsOpen(false);
      setSubmitted(false);
    }, 2000);
  };

  const toggleIssue = (issueId) => {
    setSelectedIssues(prev => 
      prev.includes(issueId) 
        ? prev.filter(i => i !== issueId)
        : [...prev, issueId]
    );
  };

  const StarRating = ({ value, onChange, label }) => (
    <div className="flex flex-col gap-2">
      <span className="text-white/70 text-sm font-roboto">{label}</span>
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            onClick={() => onChange(star)}
            className="p-1 transition-transform hover:scale-110"
          >
            <Star 
              className={`w-6 h-6 ${star <= value ? 'text-amber-400 fill-amber-400' : 'text-white/30'}`}
            />
          </button>
        ))}
      </div>
    </div>
  );

  return (
    <>
      {/* Trigger Button */}
      <button
        onClick={() => setIsOpen(true)}
        className="flex items-center gap-2 px-4 py-2 bg-white/10 hover:bg-white/20 text-white rounded-full text-sm font-roboto transition-colors border border-white/20"
      >
        <Star className="w-4 h-4" />
        Rate this analysis
      </button>

      {/* Modal */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
            onClick={() => !submitted && setIsOpen(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="glass-card rounded-2xl p-6 max-w-md w-full max-h-[90vh] overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
            >
              {submitted ? (
                <div className="text-center py-8">
                  <CheckCircle className="w-16 h-16 text-green-400 mx-auto mb-4" />
                  <h3 className="text-white font-bold text-xl font-roboto">Thank you!</h3>
                  <p className="text-white/70 text-sm mt-2 font-roboto">Your feedback helps us improve.</p>
                </div>
              ) : (
                <>
                  {/* Header */}
                  <div className="flex items-center justify-between mb-6">
                    <h3 className="text-white font-bold text-lg font-roboto">Rate this analysis</h3>
                    <button onClick={() => setIsOpen(false)} className="text-white/50 hover:text-white">
                      <X className="w-5 h-5" />
                    </button>
                  </div>

                  {/* Star Ratings */}
                  <div className="space-y-4 mb-6">
                    <StarRating 
                      label="How accurate was the analysis?" 
                      value={accuracy} 
                      onChange={setAccuracy} 
                    />
                    <StarRating 
                      label="How helpful were the insights?" 
                      value={helpfulness} 
                      onChange={setHelpfulness} 
                    />
                  </div>

                  {/* Quick Issues */}
                  <div className="mb-6">
                    <span className="text-white/70 text-sm font-roboto block mb-3">
                      Any issues? (select all that apply)
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {QUICK_ISSUES.map((issue) => (
                        <button
                          key={issue.id}
                          onClick={() => toggleIssue(issue.id)}
                          className={`px-3 py-1.5 rounded-full text-xs font-roboto transition-colors ${
                            selectedIssues.includes(issue.id)
                              ? 'bg-cyan-500/30 text-cyan-300 border border-cyan-500'
                              : 'bg-white/10 text-white/70 border border-white/20 hover:bg-white/20'
                          }`}
                        >
                          {issue.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Additional Feedback */}
                  <div className="mb-6">
                    <span className="text-white/70 text-sm font-roboto block mb-2">
                      Additional feedback (optional)
                    </span>
                    <textarea
                      value={additionalFeedback}
                      onChange={(e) => setAdditionalFeedback(e.target.value)}
                      placeholder="Tell us more..."
                      className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-xl text-white text-sm font-roboto placeholder-white/40 focus:outline-none focus:border-cyan-500 resize-none"
                      rows={3}
                    />
                  </div>

                  {/* Submit */}
                  <button
                    onClick={handleSubmit}
                    disabled={accuracy === 0 || helpfulness === 0}
                    className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-cyan-500 hover:bg-cyan-600 disabled:bg-white/20 disabled:cursor-not-allowed text-white rounded-xl font-roboto font-medium transition-colors"
                  >
                    <Send className="w-4 h-4" />
                    Submit Feedback
                  </button>
                </>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

export default RatingWidget;
