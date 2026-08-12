import React, { useState, useEffect } from 'react';
import { AlertTriangle, CalendarDays, Check, Trash2 } from 'lucide-react';
import Dashboard from './Dashboard';
import { getAnalysis, getPet, fetchAnalysisMedia, setAnalysisDate, deleteAnalysis,
         friendlyError } from '../api';

/*
 * One observation, reopened from the timeline.
 *
 * This is deliberately NOT a second, cut-down rendering of an analysis. The
 * record stores the complete result JSON, so a capture from six months ago
 * opens into exactly the screen the guardian saw the day they uploaded it —
 * same body-language read, same pet-POV lines, same advisory. A shortened
 * "history view" would quietly become a different, worse product over time.
 *
 * The clip is fetched separately because it may not be there: annotated media
 * is evicted oldest-first once the library fills. That's a normal end state,
 * not a failure — the analysis and the poster survive, so the page renders
 * fully and just says the clip has aged out.
 */

export default function AnalysisDetail({ analysisId, onBack, embedded = false,
                                        onDateChanged, onDeleted }) {
  const [record, setRecord] = useState(null);
  const [petName, setPetName] = useState('');
  const [mediaUrl, setMediaUrl] = useState(null);
  const [mediaState, setMediaState] = useState(null);   // { reason, detail }
  const [error, setError] = useState(null);
  const [editingDate, setEditingDate] = useState(false);
  const [dateInput, setDateInput] = useState('');
  const [savingDate, setSavingDate] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    let objectUrl = null;
    let cancelled = false;

    setRecord(null);
    setPetName('');
    setMediaUrl(null);
    setMediaState(null);
    setError(null);

    getAnalysis(analysisId)
      .then((rec) => {
        if (cancelled) return;
        setRecord(rec);
        // Named from the record itself rather than whichever pet happens to be
        // active, so a link to an observation always says whose it is.
        if (rec.pet_id) {
          getPet(rec.pet_id)
            .then((p) => { if (!cancelled) setPetName(p.pet?.name || ''); })
            .catch(() => {});
        }
      })
      .catch((e) => { if (!cancelled) setError(friendlyError(e)); });

    fetchAnalysisMedia(analysisId).then(({ url, reason, detail }) => {
      if (cancelled) {
        if (url) URL.revokeObjectURL(url);
        return;
      }
      objectUrl = url;
      if (url) setMediaUrl(url);
      else setMediaState({ reason, detail });
    });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [analysisId]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="glass-card rounded-2xl p-8 max-w-md text-center">
          <AlertTriangle className="w-12 h-12 text-amber-400 mx-auto mb-3" />
          <p className="font-roboto text-white mb-5">{error}</p>
          <button
            onClick={onBack}
            className="px-5 py-3 rounded-xl bg-white/30 hover:bg-white/40 text-white font-roboto font-bold transition-colors"
          >
            Back to timeline
          </button>
        </div>
      </div>
    );
  }

  if (!record) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="font-roboto text-white/60">Opening this observation…</p>
      </div>
    );
  }

  const observed = new Date(record.created_at).toLocaleDateString(undefined, {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  });

  // Where the date came from decides how loudly we invite a correction. A
  // photo with no usable metadata was dated to the day it was uploaded, which
  // puts it in the wrong place on the timeline and drags the trend with it —
  // so that case gets asked about rather than left to be noticed.
  const SOURCE_LABEL = {
    exif: 'from the photo\u2019s own metadata',
    video_metadata: 'from the video file',
    filename: 'read from the filename',
    manual: 'set by you',
    unknown: 'we couldn\u2019t read a date from this file, so it was filed under the day you uploaded it',
  };
  const src = record.capture_time_source || 'unknown';
  const dateUncertain = src === 'unknown' || src === 'filename';

  const saveDate = async () => {
    if (!dateInput) return;
    setSavingDate(true);
    try {
      const updated = await setAnalysisDate(analysisId, dateInput);
      setRecord(updated);
      setEditingDate(false);
      // The tab is labelled by this date, so it would otherwise keep the old one.
      onDateChanged?.(updated.created_at);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setSavingDate(false);
    }
  };

  const noun = record.media_type === 'image' ? 'photo' : 'clip';
  const mediaNote = !mediaState ? null
    : mediaState.reason === 'error'
      ? `The ${noun} couldn't be loaded — ${mediaState.detail} Everything below is unaffected.`
      : `No ${noun} is stored for this observation — either it predates Etho keeping media, `
        + `or it has been cleared to make room. Everything measured from it is kept.`;

  const dateBlock = (
    <div className={`max-w-5xl mx-auto px-6 ${embedded ? 'pt-4' : 'pt-2'}`}>
      {editingDate ? (
        <div className="glass-card rounded-2xl p-4 flex flex-wrap items-center gap-2">
          <CalendarDays className="w-4 h-4 text-white/70 flex-none" />
          <input
            type="date"
            autoFocus
            value={dateInput}
            max={new Date().toISOString().slice(0, 10)}
            onChange={(e) => setDateInput(e.target.value)}
            className="px-3 py-2 rounded-lg bg-white/20 border border-white/30 text-white font-roboto text-sm focus:outline-none focus:border-white/60"
          />
          <button
            onClick={saveDate}
            disabled={savingDate || !dateInput}
            className="px-4 py-2 rounded-lg bg-white/35 hover:bg-white/45 disabled:opacity-40 text-white font-roboto font-bold text-sm"
          >
            {savingDate ? 'Saving…' : 'Save date'}
          </button>
          <button
            onClick={() => setEditingDate(false)}
            className="px-3 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-white/75 font-roboto text-sm"
          >
            Cancel
          </button>
          <p className="font-roboto text-white/50 text-xs w-full">
            Moves this observation on the timeline, and recalculates the trend
            around it.
          </p>
        </div>
      ) : (
        <div className={`rounded-2xl px-4 py-3 flex flex-wrap items-center gap-x-3 gap-y-1 ${
          dateUncertain ? 'glass-card border border-amber-400/40' : ''}`}>
          <CalendarDays className="w-4 h-4 text-white/60 flex-none" />
          <span className="font-roboto text-white text-sm font-medium">{observed}</span>
          <span className="font-roboto text-white/50 text-xs">
            {src === 'unknown' ? SOURCE_LABEL.unknown : `Date ${SOURCE_LABEL[src] || SOURCE_LABEL.unknown}`}
          </span>
          <button
            onClick={() => {
              setDateInput((record.created_at || '').slice(0, 10));
              setEditingDate(true);
            }}
            className="font-roboto text-white/70 hover:text-white text-xs underline underline-offset-2 ml-auto"
          >
            {dateUncertain ? 'Set the right date' : 'Change date'}
          </button>
        </div>
      )}
    </div>
  );

  /* Deleting is offered HERE rather than on the timeline tile, and only after
     the media and the analysis are on screen. A small × beside a tap-to-open
     thumbnail is a mis-tap waiting to happen, and you should see what you are
     about to destroy. Two steps, and the second one says what goes. */
  const removeObservation = async () => {
    setDeleting(true);
    try {
      await deleteAnalysis(analysisId);
      onDeleted?.(analysisId);
    } catch (e) {
      setError(friendlyError(e));
      setDeleting(false);
    }
  };

  const deleteBlock = (
    <div className="max-w-5xl mx-auto px-6 pb-12">
      {confirmingDelete ? (
        <div className="glass-card rounded-2xl p-5 border-2 border-red-400/50">
          <p className="font-roboto font-bold text-white mb-1">
            Delete this observation?
          </p>
          <p className="font-roboto text-white/70 text-sm mb-4">
            The {record.media_type === 'image' ? 'photo' : 'clip'} and everything
            measured from it are removed for good. {petName ? `${petName}'s` : 'Their'}{' '}
            baseline and trend are worked out again from what's left — so if this was a
            bad capture, it stops counting. This can't be undone.
          </p>
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={removeObservation}
              disabled={deleting}
              className="flex items-center gap-2 px-5 py-3 rounded-xl bg-red-500/80 hover:bg-red-500 disabled:opacity-50 text-white font-roboto font-bold text-sm transition-colors"
            >
              <Trash2 className="w-4 h-4" />
              {deleting ? 'Deleting…' : 'Yes, delete it'}
            </button>
            <button
              onClick={() => setConfirmingDelete(false)}
              disabled={deleting}
              className="px-5 py-3 rounded-xl bg-white/15 hover:bg-white/25 text-white/85 font-roboto font-medium text-sm transition-colors"
            >
              Keep it
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setConfirmingDelete(true)}
          className="flex items-center gap-2 font-roboto text-white/50 hover:text-red-200 text-sm transition-colors"
        >
          <Trash2 className="w-4 h-4" />
          Delete this observation
        </button>
      )}
    </div>
  );

  return (
    <>
      {dateBlock}
      <Dashboard
        analysisData={record.full_json}
        videoUrl={mediaUrl}
        mediaType={record.media_type}
        mediaNote={mediaNote}
        onBack={onBack}
        embedded={embedded}
        headerNote={embedded ? null : petName || null}
      />
      {deleteBlock}
    </>
  );
}
