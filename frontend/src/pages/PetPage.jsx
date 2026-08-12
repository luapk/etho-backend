import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { PawPrint, ChevronDown, Upload, X, CalendarRange, Settings2,
         FileText } from 'lucide-react';
import Timeline from './Timeline';
import PetProfile from './PetProfile';
import AnalysisDetail from './AnalysisDetail';
import { listPets, fetchPetAvatar } from '../api';

/*
 * One pet, three views.
 *
 * The app used to be organised by page type — a Timeline page, a Profile page,
 * a Dashboard page — with the pet passed in as a parameter. That is backwards
 * from how a guardian thinks: they are looking at their pet, and the timeline
 * and the profile are two ways of looking. So the pet became the container and
 * everything else is a tab inside it.
 *
 * Three rules make the tab bar behave:
 *
 *  - Timeline is the default. It answers "is my pet okay"; the profile is a
 *    settings screen visited rarely.
 *  - The observation tab appears only when one is open, and can be closed.
 *    A tab that appears but can never be dismissed is a trap.
 *  - Opening a second observation REPLACES the first rather than stacking.
 *    One open slot, labelled by the date it was recorded, so the tab bar can't
 *    grow without bound.
 *
 * Uploading is a button, not a tab: tabs are views of what exists, and adding
 * an observation is an action that produces something new.
 */

const fmtShort = (iso) =>
  new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });

export default function PetPage({
  petId, initialTab = 'timeline', openAnalysisId = null,
  onChangePet, onAddObservation, onOpenVetReport, onManagePets,
}) {
  const [tab, setTab] = useState(initialTab);
  const [detail, setDetail] = useState(openAnalysisId ? { id: openAnalysisId } : null);
  const [pets, setPets] = useState([]);
  const [switching, setSwitching] = useState(false);
  const [avatarUrl, setAvatarUrl] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);
  const urlRef = useRef(null);

  const pet = pets.find((p) => p.id === petId) || null;

  const loadPets = () => listPets().then(setPets).catch(() => setPets([]));

  useEffect(() => { loadPets(); }, [petId, reloadKey]);

  // Header portrait. Blob-fetched like every other owner-scoped image.
  useEffect(() => {
    let cancelled = false;
    const clear = () => {
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
      urlRef.current = null;
    };
    if (!pet?.has_avatar) { clear(); setAvatarUrl(null); return undefined; }
    fetchPetAvatar(petId).then((u) => {
      if (cancelled) { if (u) URL.revokeObjectURL(u); return; }
      clear();
      urlRef.current = u;
      setAvatarUrl(u);
    });
    return () => { cancelled = true; };
  }, [petId, pet?.has_avatar, reloadKey]);

  useEffect(() => () => { if (urlRef.current) URL.revokeObjectURL(urlRef.current); }, []);

  // A different pet means a different record — drop whatever observation was
  // open rather than showing one pet's clip under another pet's name.
  useEffect(() => {
    setDetail(openAnalysisId ? { id: openAnalysisId } : null);
    setTab(openAnalysisId ? 'detail' : initialTab);
  }, [petId, openAnalysisId, initialTab]);

  // Switching tab keeps the old scroll offset otherwise, so you arrive
  // halfway down a screen you have never seen.
  useEffect(() => { window.scrollTo({ top: 0, behavior: 'auto' }); }, [tab]);

  const openObservation = (analysisId, date) => {
    if (!analysisId) return;
    setDetail({ id: analysisId, date });
    setTab('detail');
  };

  const closeObservation = () => {
    setDetail(null);
    setTab('timeline');
  };

  const TABS = [
    { id: 'timeline', label: 'Timeline', icon: CalendarRange },
    { id: 'profile', label: 'Profile', icon: Settings2 },
    ...(detail
      ? [{ id: 'detail', label: detail.date ? fmtShort(detail.date) : 'Observation',
           icon: FileText, closable: true }]
      : []),
  ];

  if (!petId) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="glass-card rounded-2xl p-8 max-w-sm text-center">
          <PawPrint className="w-10 h-10 text-white/50 mx-auto mb-3" />
          <p className="font-roboto text-white mb-5">No pet selected yet.</p>
          <button onClick={onManagePets}
                  className="px-5 py-3 rounded-xl bg-white/30 hover:bg-white/40 text-white font-roboto font-bold">
            Go to your pets
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Shell header — shared by every tab, so no tab repeats the pet's name */}
      <div className="px-4 pt-8 md:px-6">
        <div className="max-w-4xl mx-auto">
          {/* pr-16 keeps the Add button clear of the fixed menu button, which
              is pinned to the same corner. */}
          <div className="flex items-center gap-4 pr-16">
            <div className="w-14 h-14 rounded-full overflow-hidden bg-white/20 flex items-center justify-center flex-none">
              {avatarUrl
                ? <img src={avatarUrl} alt="" className="w-full h-full object-cover" />
                : <PawPrint className="w-6 h-6 text-white" />}
            </div>

            <div className="flex-1 min-w-0">
              <button
                onClick={() => pets.length > 1 && setSwitching(!switching)}
                className="flex items-center gap-2 text-left"
              >
                <h1 className="font-roboto font-black text-3xl text-white truncate">
                  {pet?.name || 'Loading…'}
                </h1>
                {pets.length > 1 && (
                  <ChevronDown className={`w-5 h-5 text-white/60 flex-none transition-transform ${
                    switching ? 'rotate-180' : ''}`} />
                )}
              </button>
              <p className="font-roboto text-white/60 text-sm">
                <span className="capitalize">
                  {[pet?.species, pet?.breed].filter(Boolean).join(' · ')}
                </span>
                {pet?.analysis_count > 0 && (
                  `${pet?.species || pet?.breed ? ' · ' : ''}${pet.analysis_count} observation${
                    pet.analysis_count === 1 ? '' : 's'}`
                )}
              </p>
            </div>

            <button
              onClick={onAddObservation}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/30 hover:bg-white/40 text-white font-roboto font-bold text-sm transition-colors flex-none"
            >
              <Upload className="w-4 h-4" />
              <span className="hidden sm:inline">Add</span>
            </button>
          </div>

          {/* Switching pets, not managing them — adding one happens on My pets */}
          <AnimatePresence>
            {switching && (
              <motion.div
                initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
                className="glass-card rounded-xl p-2 mt-3 flex flex-wrap gap-1.5"
              >
                {pets.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => { onChangePet?.(p.id); setSwitching(false); }}
                    className={`px-3 py-2 rounded-lg font-roboto text-sm transition-colors ${
                      p.id === petId ? 'bg-white/35 text-white' : 'bg-white/10 text-white/75 hover:bg-white/20'
                    }`}
                  >
                    {p.name}
                  </button>
                ))}
                <button
                  onClick={() => { setSwitching(false); onManagePets?.(); }}
                  className="px-3 py-2 rounded-lg bg-white/5 text-white/60 hover:bg-white/15 font-roboto text-sm border border-dashed border-white/25"
                >
                  Manage pets
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Tabs */}
      <div className="sticky top-0 z-30 mt-5 border-b border-white/15 bg-black/10 backdrop-blur-md">
        <div className="max-w-4xl mx-auto px-4 md:px-6 flex gap-1 overflow-x-auto scroll-container">
          {TABS.map(({ id, label, icon: Icon, closable }) => {
            const on = tab === id;
            return (
              <div key={id} className="relative flex items-center flex-none">
                <button
                  onClick={() => setTab(id)}
                  className={`flex items-center gap-2 px-4 py-3.5 font-roboto text-sm transition-colors ${
                    on ? 'text-white font-bold' : 'text-white/60 hover:text-white/90'
                  } ${closable ? 'pr-8' : ''}`}
                >
                  <Icon className="w-4 h-4" />
                  {label}
                </button>
                {closable && (
                  <button
                    onClick={closeObservation}
                    aria-label="Close this observation"
                    className="absolute right-2 p-1 rounded-md text-white/50 hover:text-white hover:bg-white/15 transition-colors"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
                {on && <span className="absolute inset-x-0 -bottom-px h-0.5 bg-white rounded-full" />}
              </div>
            );
          })}
        </div>
      </div>

      {/* Panels. Each is the full existing screen minus its own pet header,
          which the shell above now owns. */}
      {tab === 'timeline' && (
        <Timeline
          petId={petId}
          embedded
          refreshKey={reloadKey}
          onOpenVetReport={onOpenVetReport}
          onUpload={onAddObservation}
          onOpenAnalysis={openObservation}
        />
      )}

      {tab === 'profile' && (
        <PetProfile
          petId={petId}
          embedded
          onViewTimeline={() => setTab('timeline')}
          onChanged={() => setReloadKey((k) => k + 1)}
        />
      )}

      {tab === 'detail' && detail && (
        <AnalysisDetail
          analysisId={detail.id}
          embedded
          onBack={closeObservation}
          onDateChanged={(iso) => {
            setDetail((d) => ({ ...d, date: iso }));
            // The date decides where it sits on the timeline, so that view is
            // now stale too.
            setReloadKey((k) => k + 1);
          }}
          onDeleted={() => {
            // Close the tab it was in and rebuild the timeline and the header
            // count around what's left.
            setDetail(null);
            setTab('timeline');
            setReloadKey((k) => k + 1);
          }}
        />
      )}
    </div>
  );
}
