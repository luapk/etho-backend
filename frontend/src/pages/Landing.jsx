import React, { useState, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, Loader2, AlertCircle, Video, Circle, Square, Clock, Eye, Volume2, Brain, CheckCircle } from 'lucide-react';
import axios from 'axios';
import Footer from '../components/Footer';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

const OPTIMAL_RECORD_DURATION = 30;
const MAX_RECORD_DURATION = 45;

// Analysis steps for thinking UI
const ANALYSIS_STEPS = [
  { id: 'upload', label: 'Uploading video', icon: Upload },
  { id: 'detect', label: 'Detecting pet', icon: Eye },
  { id: 'visual', label: 'Analyzing visual cues', icon: Eye },
  { id: 'audio', label: 'Processing vocalizations', icon: Volume2 },
  { id: 'synthesis', label: 'Synthesizing findings', icon: Brain },
  { id: 'complete', label: 'Analysis complete', icon: CheckCircle }
];

function Landing({ onAnalysisComplete }) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState(0);
  const [error, setError] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [showRecordOption, setShowRecordOption] = useState(false);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);
  const streamRef = useRef(null);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('video/')) {
      processFile(file);
    } else {
      setError('Please upload a video file (MP4, MOV, AVI, WebM)');
    }
  }, []);

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      processFile(file);
    }
  };

  // Simulate analysis steps for UX
  const simulateSteps = () => {
    let step = 0;
    const interval = setInterval(() => {
      step++;
      if (step < ANALYSIS_STEPS.length - 1) {
        setCurrentStep(step);
      } else {
        clearInterval(interval);
      }
    }, 1500);
    return interval;
  };

  const processFile = async (file) => {
    setSelectedFile(file);
    setError(null);
    setIsUploading(true);
    setUploadProgress(0);
    setCurrentStep(0);

    const formData = new FormData();
    formData.append('file', file);

    // Start step simulation
    const stepInterval = simulateSteps();

    try {
      const response = await axios.post(`${API_URL}/api/video/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        params: {
          mode: 'full',
          use_cache: true
        },
        onUploadProgress: (progressEvent) => {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(progress);
          if (progress === 100) {
            setCurrentStep(1); // Move to detection
          }
        },
      });

      clearInterval(stepInterval);
      setCurrentStep(ANALYSIS_STEPS.length - 1); // Complete

      // Check for errors
      if (response.data.data?.error && response.data.data?.error_type === "no_pet_detected") {
        setError(response.data.data.message || 'No pet detected in video');
        setIsUploading(false);
        return;
      }

      if (response.data.success) {
        const videoUrl = URL.createObjectURL(file);
        setTimeout(() => {
          onAnalysisComplete(response.data.data, videoUrl);
        }, 500);
      } else {
        setError(response.data.error || 'Analysis failed. Please try again.');
      }
    } catch (err) {
      clearInterval(stepInterval);
      console.error('Upload error:', err);
      if (err.code === 'ERR_NETWORK') {
        setError('Cannot connect to server. Make sure the backend is running on port 8001.');
      } else {
        setError(err.response?.data?.detail || err.message || 'Upload failed. Please try again.');
      }
    } finally {
      setIsUploading(false);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        video: { facingMode: 'environment' }, 
        audio: true 
      });
      
      streamRef.current = stream;
      chunksRef.current = [];
      
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'video/webm;codecs=vp9'
      });
      
      mediaRecorderRef.current = mediaRecorder;
      
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };
      
      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'video/webm' });
        const file = new File([blob], `recording-${Date.now()}.webm`, { type: 'video/webm' });
        processFile(file);
        
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => track.stop());
        }
      };
      
      mediaRecorder.start();
      setIsRecording(true);
      setRecordingTime(0);
      
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => {
          if (prev >= MAX_RECORD_DURATION - 1) {
            stopRecording();
            return prev;
          }
          return prev + 1;
        });
      }, 1000);
      
    } catch (err) {
      console.error('Recording error:', err);
      setError('Unable to access camera. Please check permissions or upload a video instead.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-sky-400 via-blue-500 to-cyan-600 flex flex-col">
      {/* Header */}
      <header className="py-8 px-6">
        <div className="max-w-xl mx-auto flex flex-col items-center">
          <img 
            src="/etho-logo.png" 
            alt="Etho" 
            className="h-12 mb-3 drop-shadow-lg" 
            onError={(e) => {
              e.target.style.display = 'none';
              e.target.nextSibling.style.display = 'block';
            }} 
          />
          <span className="font-roboto font-bold text-4xl text-white hidden drop-shadow-lg">Etho</span>
          <p className="font-roboto text-white/80 text-center mt-2">
            AI-powered pet behavior analysis
          </p>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 pb-12">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="w-full max-w-xl"
        >
          {/* Recording View */}
          {isRecording ? (
            <div className="glass-card rounded-2xl p-8 text-center">
              <div className="relative inline-flex items-center justify-center mb-6">
                <div className="w-24 h-24 rounded-full bg-red-500/30 flex items-center justify-center backdrop-blur-sm">
                  <Circle className="w-8 h-8 text-red-400 animate-pulse" fill="currentColor" />
                </div>
                <div className="absolute -bottom-2 bg-red-500 text-white px-3 py-1 rounded-full text-sm font-roboto font-medium">
                  {formatTime(recordingTime)}
                </div>
              </div>
              
              <p className="font-roboto text-white text-lg mb-2">Recording...</p>
              <p className="font-roboto text-white/60 text-sm mb-6">
                Optimal: {OPTIMAL_RECORD_DURATION}s • Max: {MAX_RECORD_DURATION}s
              </p>
              
              <div className="w-full bg-white/10 rounded-full h-1 mb-6">
                <div 
                  className="h-full bg-red-400 rounded-full transition-all"
                  style={{ width: `${(recordingTime / MAX_RECORD_DURATION) * 100}%` }}
                />
              </div>
              
              <button
                onClick={stopRecording}
                className="inline-flex items-center gap-2 px-6 py-3 bg-red-500 text-white rounded-full font-roboto font-medium hover:bg-red-600 transition-colors"
              >
                <Square className="w-5 h-5" fill="currentColor" />
                Stop Recording
              </button>
            </div>
          ) : isUploading ? (
            /* Analysis Progress View */
            <div className="glass-card rounded-2xl p-8">
              <div className="text-center mb-8">
                <Loader2 className="w-12 h-12 text-white mx-auto animate-spin mb-4" />
                <p className="font-roboto text-white text-lg font-medium">
                  Analyzing your video...
                </p>
                <p className="font-roboto text-white/60 text-sm mt-1">
                  {selectedFile?.name}
                </p>
              </div>
              
              {/* Progress Steps */}
              <div className="space-y-3">
                {ANALYSIS_STEPS.map((step, idx) => {
                  const Icon = step.icon;
                  const isActive = idx === currentStep;
                  const isComplete = idx < currentStep;
                  
                  return (
                    <motion.div
                      key={step.id}
                      initial={{ opacity: 0.5 }}
                      animate={{ 
                        opacity: isComplete || isActive ? 1 : 0.5,
                        x: isActive ? 5 : 0
                      }}
                      className={`flex items-center gap-3 p-3 rounded-xl transition-colors ${
                        isActive ? 'bg-white/20' : isComplete ? 'bg-white/10' : ''
                      }`}
                    >
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                        isComplete ? 'bg-green-500/30' : isActive ? 'bg-white/20' : 'bg-white/10'
                      }`}>
                        {isComplete ? (
                          <CheckCircle className="w-4 h-4 text-green-400" />
                        ) : (
                          <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-white/50'}`} />
                        )}
                      </div>
                      <span className={`font-roboto text-sm ${
                        isActive ? 'text-white font-medium' : isComplete ? 'text-white/80' : 'text-white/50'
                      }`}>
                        {step.label}
                      </span>
                      {isActive && (
                        <Loader2 className="w-4 h-4 text-white/60 animate-spin ml-auto" />
                      )}
                    </motion.div>
                  );
                })}
              </div>
            </div>
          ) : (
            <>
              {/* Upload Area */}
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`
                  glass-card rounded-2xl p-12 transition-all duration-300 cursor-pointer
                  ${isDragging ? 'ring-2 ring-white bg-white/30' : 'hover:bg-white/20'}
                `}
              >
                <input
                  type="file"
                  accept="video/*"
                  onChange={handleFileSelect}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />

                <div className="text-center">
                  <Upload className={`w-12 h-12 mx-auto mb-4 ${
                    isDragging ? 'text-white' : 'text-white/70'
                  }`} strokeWidth={1.5} />
                  <p className="font-roboto text-white text-lg font-medium mb-2">
                    Drop your pet video here
                  </p>
                  <p className="font-roboto text-white/60 text-sm">
                    or click to browse • MP4, MOV, WebM supported
                  </p>
                </div>
              </div>

              {/* Record Option */}
              <div className="mt-6 text-center">
                <button
                  onClick={() => setShowRecordOption(!showRecordOption)}
                  className="font-roboto text-white/70 text-sm hover:text-white transition-colors"
                >
                  Or record directly from your device →
                </button>
                
                <AnimatePresence>
                  {showRecordOption && (
                    <motion.div
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      className="glass-card mt-4 p-5 rounded-xl"
                    >
                      <div className="flex items-center justify-center gap-2 text-white/80 text-sm mb-4">
                        <Clock className="w-4 h-4" />
                        <span className="font-roboto">Optimal: {OPTIMAL_RECORD_DURATION} seconds</span>
                      </div>
                      <button
                        onClick={startRecording}
                        className="inline-flex items-center gap-2 px-5 py-2.5 bg-white/20 hover:bg-white/30 text-white rounded-full font-roboto font-medium transition-colors backdrop-blur-sm border border-white/30"
                      >
                        <Video className="w-5 h-5" />
                        Start Recording
                      </button>
                      <p className="font-roboto text-white/50 text-xs mt-3">
                        Requires camera and microphone permission
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </>
          )}

          {/* Error Message */}
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 10 }}
                className="mt-4 p-4 rounded-xl flex items-start gap-3"
                style={{ backgroundColor: 'rgba(239, 68, 68, 0.2)', backdropFilter: 'blur(12px)' }}
              >
                <AlertCircle className="w-5 h-5 text-red-300 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-roboto text-white text-sm">{error}</p>
                  <button
                    onClick={() => setError(null)}
                    className="font-roboto text-red-300 text-xs mt-2 hover:text-red-200"
                  >
                    Dismiss
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>

        {/* Features */}
        {!isUploading && !isRecording && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="mt-16 grid grid-cols-3 gap-8 max-w-2xl"
          >
            <div className="text-center">
              <div className="w-12 h-12 glass-card rounded-full flex items-center justify-center mx-auto mb-3">
                <span className="text-xl">📚</span>
              </div>
              <h3 className="font-roboto font-bold text-white text-sm mb-1">Research-Backed</h3>
              <p className="font-roboto text-white/60 text-xs">
                DogFACS, FGS & bio-acoustics
              </p>
            </div>
            
            <div className="text-center">
              <div className="w-12 h-12 glass-card rounded-full flex items-center justify-center mx-auto mb-3">
                <span className="text-xl">👁️</span>
              </div>
              <h3 className="font-roboto font-bold text-white text-sm mb-1">Visual + Audio</h3>
              <p className="font-roboto text-white/60 text-xs">
                Expression & vocalization analysis
              </p>
            </div>
            
            <div className="text-center">
              <div className="w-12 h-12 glass-card rounded-full flex items-center justify-center mx-auto mb-3">
                <span className="text-xl">💡</span>
              </div>
              <h3 className="font-roboto font-bold text-white text-sm mb-1">Actionable</h3>
              <p className="font-roboto text-white/60 text-xs">
                Practical recommendations
              </p>
            </div>
          </motion.div>
        )}
      </main>

      {/* Footer */}
      <Footer />
    </div>
  );
}

export default Landing;
