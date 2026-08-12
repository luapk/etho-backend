import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { PawPrint, ChevronDown, Upload, X, CalendarRange, Settings2,
         FileText } from 'lucide-react';
import Timeline from './Timeline';
import PetProfile, { profileCompleteness } from './PetProfile';
import AnalysisDetail from './AnalysisDetail';
import Landing from './Landing';
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
  onChangePet, onOpenVetReport, onManagePets, onPetChanged, onAnalysisComplete,
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

  /* The portrait is the way into the profile, so Profile is no longer a
     permanent tab — it opens like an observation does, and closes the same
     way. Resting state is just the timeline. */
  const TABS = [
    { id: 'timeline', label: 'Timeline', icon: CalendarRange },
    // Adding a capture is part of being on this pet's page, not a trip to
    // another screen. As a tab it keeps the Etho bar, the portrait and the
    // way back to the timeline, all of which the standalone page had to
    // reinvent — and did without, which is why it felt detached.
    { id: 'add', label: 'Add', icon: Upload },
    ...(tab === 'profile'
      ? [{ id: 'profile', label: 'Profile', icon: Settings2, closable: true,
           onClose: () => setTab('timeline') }]
      : []),
    ...(detail
      ? [{ id: 'detail', label: detail.date ? fmtShort(detail.date) : 'Observation',
           icon: FileText, closable: true, onClose: closeObservation }]
      : []),
  ];

  const completeness = profileCompleteness(pet);

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
      <div className="px-4 pt-3 md:px-6">
        <div className="max-w-4xl mx-auto">
          {/* pr-16 keeps the Add button clear of the fixed menu button, which
              is pinned to the same corner. */}
          <div className="flex items-center gap-4 pr-16">
            {/* Tap the pet to edit them. The ring is how much of their profile
                is filled in — a finishable task, so it can reach 100% and
                stop asking. */}
            <button
              onClick={() => setTab('profile')}
              className="relative w-16 h-16 flex-none group"
              aria-label={`Edit ${pet?.name || 'pet'} — profile ${completeness.percent}% complete`}
              title={completeness.missing.length
                ? `Profile ${completeness.percent}% — still to add: ${completeness.missing.join(', ')}`
                : 'Profile complete'}
            >
              <svg viewBox="0 0 64 64" className="absolute inset-0 -rotate-90 w-16 h-16">
                <circle cx="32" cy="32" r="29" fill="none"
                        stroke="rgba(255,255,255,0.18)" strokeWidth="3" />
                <circle
                  cx="32" cy="32" r="29" fill="none"
                  stroke={completeness.percent === 100 ? '#4ade80' : '#ffffff'}
                  strokeWidth="3" strokeLinecap="round"
                  strokeDasharray={`${(completeness.percent / 100) * 2 * Math.PI * 29} ${2 * Math.PI * 29}`}
                  className="transition-all duration-500"
                />
              </svg>
              <div className="absolute inset-[5px] rounded-full overflow-hidden bg-white/20 flex items-center justify-center group-hover:brightness-110 transition-all">
                {avatarUrl
                  ? <img src={avatarUrl} alt="" className="w-full h-full object-cover" />
                  : <PawPrint className="w-6 h-6 text-white" />}
              </div>
            </button>

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
              {completeness.missing.length > 0 && tab !== 'profile' && (
                <button
                  onClick={() => setTab('profile')}
                  className="font-roboto text-white/45 hover:text-white/80 text-xs mt-0.5 underline underline-offset-2 text-left"
                >
                  Profile {completeness.percent}% — add {completeness.missing[0]}
                </button>
              )}
            </div>

            {/* No Add button up here any more. Uploading is a tab now, and a
                second door to the same room — squeezed against a long pet
                name on a phone — was only ever a workaround for it not being
                one. */}
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
          {TABS.map(({ id, label, icon: Icon, closable, onClose }) => {
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
                    onClick={onClose}
                    aria-label={`Close ${label}`}
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
          onUpload={() => setTab('add')}
          onOpenAnalysis={openObservation}
          onChanged={() => { setReloadKey((k) => k + 1); onPetChanged?.(); }}
        />
      )}

      {tab === 'add' && (
        <div className="max-w-3xl mx-auto px-4 md:px-6 pb-10">
          <Landing
            embedded
            petId={petId}
            onChangePet={onChangePet}
            onAnalysisComplete={onAnalysisComplete}
            onViewTimeline={() => setTab('timeline')}
            onManagePets={onManagePets}
          />
        </div>
      )}

      {tab === 'profile' && (
        <PetProfile
          petId={petId}
          embedded
          onViewTimeline={() => setTab('timeline')}
          onChanged={() => { setReloadKey((k) => k + 1); onPetChanged?.(); }}
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
