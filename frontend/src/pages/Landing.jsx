import React, { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, AlertCircle, Circle, Square, Eye, Volume2, Brain,
         CheckCircle, ChevronDown, Check, X, Loader } from 'lucide-react';
import Footer from '../components/Footer';
import { listPets, createPet, updatePet, uploadMedia, uploadBatch,
         getBatchStatus, friendlyError } from '../api';

/*
 * One screen, one decision at a time.
 *
 * First visit asks a single question — the pet's name — and nothing else.
 * Species is NOT asked: the analysis detects it, and we backfill the profile
 * afterwards, so the guardian answers one question instead of two.
 *
 * After that it's just a drop zone. The same zone takes one file or thirty:
 * pick several and it becomes a batch import automatically, rather than
 * hiding bulk upload behind a separate page.
 */

const OPTIMAL_RECORD_DURATION = 30;
const MAX_RECORD_DURATION = 45;
const MAX_BATCH = 30;
const POLL_MS = 3000;

const ANALYSIS_STEPS = [
  { id: 'upload', label: 'Uploading', icon: Upload },
  { id: 'detect', label: 'Finding your pet', icon: Eye },
  { id: 'visual', label: 'Reading body language', icon: Eye },
  { id: 'audio', label: 'Listening to sounds', icon: Volume2 },
  { id: 'synthesis', label: 'Putting it together', icon: Brain },
  { id: 'complete', label: 'Done', icon: CheckCircle },
];

const isImage = (f) => (f.type || '').startsWith('image/');
const isMedia = (f) => isImage(f) || (f.type || '').startsWith('video/');

function Landing({ onAnalysisComplete, petId, onChangePet, onViewTimeline }) {
  const [pets, setPets] = useState(null);          // null while loading
  const [nameInput, setNameInput] = useState('');
  const [creating, setCreating] = useState(false);
  const [switching, setSwitching] = useState(false);

  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState(0);
  const [error, setError] = useState(null);
  const [asleep, setAsleep] = useState(false);
  const [batch, setBatch] = useState(null);

  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);
  const streamRef = useRef(null);
  const fileRef = useRef(null);
  const pollRef = useRef(null);

  useEffect(() => {
    listPets().then(setPets).catch(() => setPets([]));
  }, []);

  const pet = pets?.find((p) => p.id === petId) || pets?.[0] || null;
  const petName = pet?.name || '';

  // Poll a running batch until the backend says it's finished.
  useEffect(() => {
    if (!batch?.batch_id || batch.status === 'done') return undefined;
    pollRef.current = setInterval(() => {
      getBatchStatus(batch.batch_id)
        .then((b) => { setBatch(b); if (b.status === 'done') clearInterval(pollRef.current); })
        .catch(() => {});
    }, POLL_MS);
    return () => clearInterval(pollRef.current);
  }, [batch?.batch_id, batch?.status]);

  const nameSubmit = async (e) => {
    e.preventDefault();
    const name = nameInput.trim();
    if (!name) return;
    setCreating(true);
    try {
      // Species is left blank on purpose — the first analysis detects it and
      // we fill it in below, so this stays a one-question sign-up.
      const created = await createPet({ name });
      setPets((prev) => [...(prev || []), { ...created, analysis_count: 0 }]);
      onChangePet?.(created.id);
      setNameInput('');
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setCreating(false);
    }
  };

  const simulateSteps = () => {
    let step = 0;
    const interval = setInterval(() => {
      step += 1;
      if (step < ANALYSIS_STEPS.length - 1) setCurrentStep(step);
      else clearInterval(interval);
    }, 1500);
    return interval;
  };

  const analyseOne = async (file) => {
    setError(null);
    setIsUploading(true);
    setUploadProgress(0);
    setCurrentStep(0);
    const stepInterval = simulateSteps();
    try {
      const data = await uploadMedia(file, {
        petId: pet?.id,
        context: asleep ? 'sleeping_baseline' : null,
        onProgress: (p) => { setUploadProgress(p); if (p === 100) setCurrentStep(1); },
      });
      clearInterval(stepInterval);
      setCurrentStep(ANALYSIS_STEPS.length - 1);

      if (data.data?.error && data.data?.error_type === 'no_pet_detected') {
        setError(data.data.message || "We couldn't find a pet in that one.");
        setIsUploading(false);
        return;
      }
      if (!data.success) {
        setError(data.error || 'Analysis failed. Please try again.');
        setIsUploading(false);
        return;
      }
      // Backfill the species we never asked for.
      if (pet && !pet.species && data.data?.species) {
        updatePet(pet.id, { species: data.data.species }).catch(() => {});
      }
      const mediaUrl = URL.createObjectURL(file);
      setTimeout(() => onAnalysisComplete(data.data, mediaUrl), 500);
    } catch (err) {
      clearInterval(stepInterval);
      setError(friendlyError(err));
      setIsUploading(false);
    }
  };

  const analyseMany = async (files) => {
    setError(null);
    setIsUploading(true);
    setUploadProgress(0);
    try {
      const res = await uploadBatch(files, {
        petId: pet?.id,
        context: asleep ? 'sleeping_baseline' : null,
        onProgress: setUploadProgress,
      });
      setBatch({
        batch_id: res.batch_id, status: 'processing',
        total: res.queued, completed: 0, failed: 0,
        items: [], rejected: res.rejected || [],
      });
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setIsUploading(false);
    }
  };

  const handleFiles = (fileList) => {
    const files = Array.from(fileList || []).filter(isMedia).slice(0, MAX_BATCH);
    if (!files.length) {
      setError('Please choose a video or a photo.');
      return;
    }
    if (files.length === 1) analyseOne(files[0]);
    else analyseMany(files);
  };

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  }, [pet?.id, asleep]);

  // ── Recording ──────────────────────────────────────────────────────────────
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' }, audio: true,
      });
      streamRef.current = stream;
      chunksRef.current = [];
      const rec = new MediaRecorder(stream, { mimeType: 'video/webm;codecs=vp9' });
      mediaRecorderRef.current = rec;
      rec.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'video/webm' });
        analyseOne(new File([blob], `recording-${Date.now()}.webm`, { type: 'video/webm' }));
        streamRef.current?.getTracks().forEach((t) => t.stop());
      };
      rec.start();
      setIsRecording(true);
      setRecordingTime(0);
      timerRef.current = setInterval(() => {
        setRecordingTime((prev) => {
          if (prev >= MAX_RECORD_DURATION - 1) { stopRecording(); return prev; }
          return prev + 1;
        });
      }, 1000);
    } catch {
      setError('Unable to use the camera. Check permissions, or upload a file instead.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) clearInterval(timerRef.current);
    }
  };

  const fmt = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

  if (pets === null) return <div className="min-h-screen" />;

  // ── First visit: one question ──────────────────────────────────────────────
  if (!pets.length) {
    return (
      <div className="min-h-screen flex flex-col">
        <header className="py-10 px-6 text-center">
          <img src="/etho-logo.png" alt="Etho" className="h-12 mx-auto drop-shadow-lg"
               onError={(e) => { e.target.style.display = 'none'; }} />
        </header>

        <div className="flex-1 flex items-center justify-center px-6 pb-24">
          <motion.form
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            onSubmit={nameSubmit}
            className="w-full max-w-2xl text-center"
          >
            <p className="font-roboto text-white/80 text-xl md:text-2xl mb-6">
              Welcome. What's your pet's name?
            </p>

            <input
              autoFocus
              value={nameInput}
              onChange={(e) => setNameInput(e.target.value)}
              placeholder="Type their name"
              className="keep-font-size w-full bg-transparent border-0 border-b-2 border-white/40
                         focus:border-white text-white placeholder-white/30 font-roboto font-black
                         text-center text-5xl md:text-7xl py-4 focus:outline-none transition-colors"
            />

            <AnimatePresence>
              {nameInput.trim() && (
                <motion.button
                  initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                  type="submit" disabled={creating}
                  className="mt-10 px-10 py-4 rounded-2xl bg-white/30 hover:bg-white/40 disabled:opacity-50
                             text-white font-roboto font-bold text-lg transition-colors"
                >
                  {creating ? 'One moment…' : `Continue with ${nameInput.trim()}`}
                </motion.button>
              )}
            </AnimatePresence>

            {error && (
              <p className="font-roboto text-red-200 text-sm mt-6">{error}</p>
            )}
          </motion.form>
        </div>
        <Footer />
      </div>
    );
  }

  // ── Batch in progress ──────────────────────────────────────────────────────
  if (batch) {
    const done = batch.status === 'done';
    const pct = Math.round(((batch.completed + batch.failed) / Math.max(batch.total, 1)) * 100);
    return (
      <div className="min-h-screen flex flex-col">
        <header className="py-8 px-6 text-center">
          <img src="/etho-logo.png" alt="Etho" className="h-10 mx-auto drop-shadow-lg"
               onError={(e) => { e.target.style.display = 'none'; }} />
        </header>
        <div className="flex-1 px-6 pb-16">
          <div className="max-w-xl mx-auto glass-card rounded-2xl p-6">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-roboto font-bold text-white text-lg">
                {done ? 'All done' : `Analysing ${petName}'s photos…`}
              </h2>
              <span className="font-roboto text-white/70 text-sm">
                {batch.completed + batch.failed} / {batch.total}
              </span>
            </div>
            <div className="w-full bg-white/15 rounded-full h-2 mb-4 overflow-hidden">
              <motion.div className="h-full bg-white rounded-full"
                          animate={{ width: `${pct}%` }} transition={{ duration: 0.4 }} />
            </div>
            {!done && (
              <p className="font-roboto text-white/60 text-sm mb-4">
                Each one is saved as it finishes — you can leave this page.
              </p>
            )}
            <div className="space-y-1.5 max-h-72 overflow-y-auto scroll-container">
              {batch.items?.map((it, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  {it.status === 'done' && <Check className="w-4 h-4 text-green-300 flex-none" />}
                  {it.status === 'failed' && <X className="w-4 h-4 text-red-300 flex-none" />}
                  {it.status === 'processing' && <Loader className="w-4 h-4 text-white/70 flex-none animate-spin" />}
                  <span className="font-roboto text-white/80 truncate flex-1">{it.filename}</span>
                  {it.observed_at && (
                    <span className="font-roboto text-white/50 text-xs whitespace-nowrap">
                      {new Date(it.observed_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
              ))}
            </div>
            {done && (
              <div className="flex gap-2 mt-5">
                <button onClick={() => setBatch(null)}
                        className="px-4 py-3 rounded-xl bg-white/15 hover:bg-white/25 text-white/85 font-roboto font-medium">
                  Add more
                </button>
                <button onClick={() => onViewTimeline?.(pet?.id)}
                        className="flex-1 py-3 rounded-xl bg-white/35 hover:bg-white/45 text-white font-roboto font-bold">
                  See {petName}'s timeline
                </button>
              </div>
            )}
          </div>
        </div>
        <Footer />
      </div>
    );
  }

  // ── Main: drop zone ────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen flex flex-col">
      <header className="py-8 px-6">
        <div className="max-w-xl mx-auto flex flex-col items-center">
          <img src="/etho-logo.png" alt="Etho" className="h-12 mb-3 drop-shadow-lg"
               onError={(e) => { e.target.style.display = 'none'; }} />

          {/* Whose clip this is — a quiet control, not a form */}
          <button
            onClick={() => setSwitching(!switching)}
            className="flex items-center gap-1.5 font-roboto text-white/70 hover:text-white text-sm transition-colors"
          >
            {petName}
            <ChevronDown className={`w-4 h-4 transition-transform ${switching ? 'rotate-180' : ''}`} />
          </button>

          <AnimatePresence>
            {switching && (
              <motion.div
                initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
                className="glass-card rounded-xl p-2 mt-2 flex flex-wrap gap-1.5 justify-center"
              >
                {pets.map((p) => (
                  <button key={p.id}
                    onClick={() => { onChangePet?.(p.id); setSwitching(false); }}
                    className={`px-3 py-2 rounded-lg font-roboto text-sm transition-colors ${
                      p.id === pet?.id ? 'bg-white/35 text-white' : 'bg-white/10 text-white/75 hover:bg-white/20'
                    }`}>
                    {p.name}
                  </button>
                ))}
                <form onSubmit={nameSubmit} className="flex gap-1.5">
                  <input value={nameInput} onChange={(e) => setNameInput(e.target.value)}
                         placeholder="New pet"
                         className="w-28 px-3 py-2 rounded-lg bg-white/10 border border-white/25 text-white placeholder-white/40 font-roboto text-sm focus:outline-none focus:border-white/60" />
                  {nameInput.trim() && (
                    <button type="submit" className="px-3 py-2 rounded-lg bg-white/30 text-white font-roboto text-sm font-bold">
                      Add
                    </button>
                  )}
                </form>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </header>

      <div className="flex-1 px-6 pb-12 flex items-center">
        <div className="w-full max-w-xl mx-auto">
          {error && (
            <div className="glass-card rounded-2xl p-4 mb-4 border-2 border-amber-500/50 flex gap-3">
              <AlertCircle className="w-5 h-5 text-amber-300 flex-none mt-0.5" />
              <p className="font-roboto text-white/90 text-sm">{error}</p>
            </div>
          )}

          {isRecording ? (
            <div className="glass-card rounded-2xl p-8 text-center">
              <div className="relative inline-flex items-center justify-center mb-6">
                <div className="w-24 h-24 rounded-full bg-red-500/30 flex items-center justify-center backdrop-blur-sm">
                  <Circle className="w-10 h-10 text-red-400 fill-red-400 animate-pulse" />
                </div>
                <div className="absolute -bottom-2 bg-red-500 text-white px-3 py-1 rounded-full text-sm font-roboto font-medium">
                  {fmt(recordingTime)}
                </div>
              </div>
              <p className="font-roboto text-white/80 mb-2">
                {recordingTime < OPTIMAL_RECORD_DURATION
                  ? `Keep going — ${OPTIMAL_RECORD_DURATION - recordingTime}s for a good read`
                  : 'Plenty captured. Stop whenever you like.'}
              </p>
              <div className="w-full bg-white/10 rounded-full h-1 my-5">
                <div className="bg-white h-1 rounded-full transition-all"
                     style={{ width: `${(recordingTime / MAX_RECORD_DURATION) * 100}%` }} />
              </div>
              <button onClick={stopRecording}
                      className="px-8 py-3 rounded-xl bg-white/30 hover:bg-white/40 text-white font-roboto font-bold inline-flex items-center gap-2">
                <Square className="w-4 h-4 fill-white" /> Stop and analyse
              </button>
            </div>
          ) : isUploading ? (
            <div className="glass-card rounded-2xl p-8">
              <div className="text-center mb-8">
                <p className="font-roboto text-white/80">
                  {uploadProgress < 100 ? `Uploading… ${uploadProgress}%` : `Looking at ${petName}`}
                </p>
              </div>
              <div className="space-y-3">
                {ANALYSIS_STEPS.map((step, idx) => {
                  const Icon = step.icon;
                  const active = idx === currentStep;
                  const done = idx < currentStep;
                  return (
                    <div key={step.id} className={`flex items-center gap-3 transition-opacity ${
                      active || done ? 'opacity-100' : 'opacity-30'}`}>
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                        done ? 'bg-white/30' : active ? 'bg-white/20 animate-pulse' : 'bg-white/10'}`}>
                        {done ? <CheckCircle className="w-4 h-4 text-white" />
                              : <Icon className="w-4 h-4 text-white" />}
                      </div>
                      <span className="font-roboto text-white/90">{step.label}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <>
              {/* The one thing to do on this screen */}
              <div
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={(e) => { e.preventDefault(); setIsDragging(false); }}
                onDrop={onDrop}
                onClick={() => fileRef.current?.click()}
                className={`glass-card rounded-2xl p-12 text-center cursor-pointer transition-all ${
                  isDragging ? 'ring-2 ring-white bg-white/30' : 'hover:bg-white/25'
                }`}
              >
                <input
                  ref={fileRef}
                  type="file"
                  multiple
                  accept="video/*,image/jpeg,image/png,image/webp"
                  onChange={(e) => handleFiles(e.target.files)}
                  className="hidden"
                />
                <Upload className="w-12 h-12 mx-auto mb-4 text-white/70" strokeWidth={1.5} />
                <p className="font-roboto text-white text-xl font-bold mb-2">
                  Drop a video or photo of {petName} here
                </p>
                <p className="font-roboto text-white/60 text-sm">
                  or tap to choose — pick as many as you like
                </p>
              </div>

              {/* One line of guidance, not a manual */}
              <p className="font-roboto text-white/55 text-sm text-center mt-4">
                Film {petName} in good light, in focus, with their whole body in
                frame. 30 seconds is plenty.
              </p>

              {/* The only option, and only because it unlocks a measurement */}
              <label className="mt-5 mx-auto flex w-fit max-w-xs items-start gap-2.5 cursor-pointer">
                <input type="checkbox" checked={asleep}
                       onChange={(e) => setAsleep(e.target.checked)}
                       className="w-4 h-4 mt-0.5 flex-none rounded accent-white" />
                <span className="font-roboto text-white/60 text-sm text-left">
                  {petName} is asleep in this — measure their breathing rate
                </span>
              </label>

              <div className="mt-8 text-center">
                <button onClick={startRecording}
                        className="font-roboto text-white/70 hover:text-white text-sm transition-colors">
                  Or film {petName} right now →
                </button>
              </div>
            </>
          )}
        </div>
      </div>
      <Footer />
    </div>
  );
}

export default Landing;
