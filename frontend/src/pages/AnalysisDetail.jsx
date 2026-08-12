import React, { useState, useEffect } from 'react';
import { AlertTriangle } from 'lucide-react';
import Dashboard from './Dashboard';
import { getAnalysis, getPet, fetchAnalysisMedia, friendlyError } from '../api';

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

export default function AnalysisDetail({ analysisId, onBack }) {
  const [record, setRecord] = useState(null);
  const [petName, setPetName] = useState('');
  const [mediaUrl, setMediaUrl] = useState(null);
  const [mediaState, setMediaState] = useState(null);   // { reason, detail }
  const [error, setError] = useState(null);

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

  return (
    <>
      <Dashboard
        analysisData={record.full_json}
        videoUrl={mediaUrl}
        mediaType={record.media_type}
        onBack={onBack}
        headerNote={`${petName ? `${petName} · ` : ''}${observed}`}
      />
      {mediaState && (
        <div className="max-w-5xl mx-auto px-6 pb-10 -mt-6">
          {mediaState.reason === 'error' ? (
            <p className="font-roboto text-amber-200/90 text-xs text-center">
              The {record.media_type === 'image' ? 'photo' : 'clip'} couldn't be
              loaded — {mediaState.detail} The analysis below is unaffected.
            </p>
          ) : (
            <p className="font-roboto text-white/50 text-xs text-center">
              No {record.media_type === 'image' ? 'photo' : 'clip'} is stored for
              this observation — either it predates Etho keeping media, or it has
              been cleared to make room. Everything measured from it is kept.
            </p>
          )}
        </div>
      )}
    </>
  );
}
