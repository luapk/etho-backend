import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Upload, Check, X, Loader, AlertTriangle, FolderOpen, ArrowLeft } from 'lucide-react';
import { uploadBatch, getBatchStatus, friendlyError } from '../api';
import CaptureSetup from '../components/CaptureSetup';

/*
 * Bulk import from the camera roll.
 *
 * The value here is not convenience, it's history: each file is dated by when
 * it was RECORDED (EXIF for photos, container metadata for videos), so
 * importing a backlog rebuilds months of real timeline rather than stacking
 * everything on today. That's worth saying on screen, because it's the reason
 * a guardian should bother.
 *
 * Videos take about a minute each, so the backend processes in the background
 * and we poll for progress.
 */

const MAX_FILES = 30;
const POLL_MS = 3000;

const isImage = (f) => (f.type || '').startsWith('image/');

export default function BatchImport({ petId, onChangePet, onAddPet, onDone, onViewTimeline }) {
  const [files, setFiles] = useState([]);
  const [context, setContext] = useState('weekly_baseline');
  const [batch, setBatch] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);
  const pollRef = useRef(null);

  // Poll batch progress until the backend reports it finished.
  useEffect(() => {
    if (!batch?.batch_id || batch.status === 'done') return undefined;
    pollRef.current = setInterval(() => {
      getBatchStatus(batch.batch_id)
        .then((b) => {
          setBatch(b);
          if (b.status === 'done') clearInterval(pollRef.current);
        })
        .catch(() => {});
    }, POLL_MS);
    return () => clearInterval(pollRef.current);
  }, [batch?.batch_id, batch?.status]);

  const pick = (e) => {
    const chosen = Array.from(e.target.files || []).slice(0, MAX_FILES);
    setFiles(chosen);
    setError(null);
  };

  const start = async () => {
    if (!files.length) return;
    setUploading(true);
    setError(null);
    try {
      const res = await uploadBatch(files, { petId, context, onProgress: setProgress });
      setBatch({
        batch_id: res.batch_id, status: 'processing',
        total: res.queued, completed: 0, failed: 0,
        items: [], rejected: res.rejected || [],
      });
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setUploading(false);
    }
  };

  const photos = files.filter(isImage).length;
  const videos = files.length - photos;
  const done = batch?.status === 'done';
  const pct = batch ? Math.round(((batch.completed + batch.failed) / Math.max(batch.total, 1)) * 100) : 0;

  return (
    <div className="min-h-screen px-4 py-8 md:px-6">
      <div className="max-w-xl mx-auto">
        <button
          onClick={onDone}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl glass-card hover:bg-white/25 text-white font-roboto font-medium transition-colors mb-4"
        >
          <ArrowLeft className="w-4 h-4" /> Back
        </button>

        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="font-roboto font-black text-3xl text-white mb-1">Import your camera roll</h1>
          <p className="font-roboto text-white/70 mb-5">
            Pick photos and clips you already have. Each one is dated by when it
            was <strong className="text-white">taken</strong>, not today — so a
            year of photos rebuilds a year of history.
          </p>
        </motion.div>

        {!batch && (
          <>
            <CaptureSetup
              petId={petId}
              context={context}
              onChangePet={onChangePet}
              onChangeContext={setContext}
              onAddPet={onAddPet}
            />

            <div
              onClick={() => inputRef.current?.click()}
              className="glass-card rounded-2xl p-8 text-center cursor-pointer hover:bg-white/25 transition-colors border-2 border-dashed border-white/30"
            >
              <input
                ref={inputRef}
                type="file"
                multiple
                accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm"
                onChange={pick}
                className="hidden"
              />
              <FolderOpen className="w-12 h-12 text-white/70 mx-auto mb-3" />
              <p className="font-roboto font-bold text-white text-lg mb-1">
                {files.length ? `${files.length} selected` : 'Choose photos & videos'}
              </p>
              <p className="font-roboto text-white/60 text-sm">
                {files.length
                  ? `${photos} photo${photos === 1 ? '' : 's'}, ${videos} video${videos === 1 ? '' : 's'} · tap to change`
                  : `Up to ${MAX_FILES} at a time`}
              </p>
            </div>

            {files.length > 0 && (
              <>
                {videos > 0 && (
                  <p className="font-roboto text-white/60 text-xs text-center mt-3">
                    Videos take roughly a minute each — about{' '}
                    {Math.max(1, Math.round(videos))} minute{videos === 1 ? '' : 's'} for this batch.
                    You can leave this page; the analyses keep saving.
                  </p>
                )}
                <button
                  onClick={start}
                  disabled={uploading}
                  className="w-full mt-4 py-4 rounded-xl bg-white/35 hover:bg-white/45 disabled:opacity-50 text-white font-roboto font-bold text-lg transition-colors flex items-center justify-center gap-2"
                >
                  <Upload className="w-5 h-5" />
                  {uploading ? `Uploading… ${progress}%` : `Import ${files.length} file${files.length === 1 ? '' : 's'}`}
                </button>
              </>
            )}
          </>
        )}

        {error && (
          <div className="glass-card rounded-2xl p-4 mt-4 border-2 border-amber-500/50 flex gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-300 flex-none mt-0.5" />
            <p className="font-roboto text-white/90 text-sm">{error}</p>
          </div>
        )}

        {/* Progress */}
        {batch && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass-card rounded-2xl p-5 mt-4">
            <div className="flex items-center justify-between mb-2">
              <h2 className="font-roboto font-bold text-white">
                {done ? 'Import complete' : 'Analysing…'}
              </h2>
              <span className="font-roboto text-white/70 text-sm">
                {batch.completed + batch.failed} / {batch.total}
              </span>
            </div>

            <div className="w-full bg-white/15 rounded-full h-2 mb-4 overflow-hidden">
              <motion.div
                className="h-full bg-white rounded-full"
                animate={{ width: `${pct}%` }}
                transition={{ duration: 0.4 }}
              />
            </div>

            {!done && (
              <p className="font-roboto text-white/60 text-xs mb-3">
                Each finished analysis is saved as it completes — you can close
                this and come back.
              </p>
            )}

            <div className="space-y-1.5 max-h-64 overflow-y-auto scroll-container">
              {batch.items?.map((item, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  {item.status === 'done' && <Check className="w-4 h-4 text-green-300 flex-none" />}
                  {item.status === 'failed' && <X className="w-4 h-4 text-red-300 flex-none" />}
                  {item.status === 'processing' && <Loader className="w-4 h-4 text-white/70 flex-none animate-spin" />}
                  <span className="font-roboto text-white/80 truncate flex-1">{item.filename}</span>
                  {item.status === 'done' && item.observed_at && (
                    <span className="font-roboto text-white/50 text-xs whitespace-nowrap">
                      {new Date(item.observed_at).toLocaleDateString()}
                    </span>
                  )}
                  {item.status === 'done' && item.distress_score != null && (
                    <span className="font-roboto text-white font-bold text-xs">{item.distress_score}</span>
                  )}
                  {item.status === 'failed' && (
                    <span className="font-roboto text-red-200 text-xs truncate max-w-[40%]">{item.error}</span>
                  )}
                </div>
              ))}
            </div>

            {batch.rejected?.length > 0 && (
              <p className="font-roboto text-white/50 text-xs mt-3">
                Skipped {batch.rejected.length}: {batch.rejected.map((r) => r.filename).join(', ')}
              </p>
            )}

            {done && (
              <div className="flex gap-2 mt-4">
                <button
                  onClick={() => { setBatch(null); setFiles([]); }}
                  className="px-4 py-3 rounded-xl bg-white/15 hover:bg-white/25 text-white/85 font-roboto font-medium transition-colors"
                >
                  Import more
                </button>
                {petId && (
                  <button
                    onClick={() => onViewTimeline?.(petId)}
                    className="flex-1 py-3 rounded-xl bg-white/35 hover:bg-white/45 text-white font-roboto font-bold transition-colors"
                  >
                    See the timeline
                  </button>
                )}
              </div>
            )}
          </motion.div>
        )}
      </div>
    </div>
  );
}
