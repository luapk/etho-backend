import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { PawPrint, Plus, Info, Moon, AlertCircle, CalendarCheck, Stethoscope } from 'lucide-react';
import { listPets } from '../api';

/*
 * Who is this clip of, and what kind of capture is it?
 *
 * Shown above the upload zone. Two deliberate UX decisions:
 *
 *  - A pet is NEVER required. Someone trying Etho for the first time should
 *    get an analysis without filling in a profile. The prompt to add a pet is
 *    an invitation, not a gate.
 *  - The capture-type chips only appear once a pet is chosen, because the tag
 *    only means anything if the clip is being saved to a record. Showing them
 *    otherwise is noise.
 */

const CONTEXTS = [
  { id: 'weekly_baseline', label: 'Regular check-in', icon: CalendarCheck,
    hint: 'A normal day — this is what builds their baseline.' },
  { id: 'incident', label: 'Something\'s wrong', icon: AlertCircle,
    hint: 'Kept separate so it doesn\'t skew their normal range.' },
  { id: 'sleeping_baseline', label: 'Sleeping', icon: Moon,
    hint: 'Breathing rate is measured — needs them fully asleep, camera propped still, 30s+.' },
  { id: 'post_vet', label: 'After treatment', icon: Stethoscope,
    hint: 'Track how they respond to a medication or procedure.' },
];

export default function CaptureSetup({ petId, context, onChangePet, onChangeContext, onAddPet }) {
  const [pets, setPets] = useState([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    listPets()
      .then(setPets)
      .catch(() => setPets([]))
      .finally(() => setLoaded(true));
  }, []);

  if (!loaded) return null;

  const selected = pets.find((p) => p.id === petId);
  const activeContext = CONTEXTS.find((c) => c.id === context);

  return (
    <div className="glass-card rounded-2xl p-4 mb-4 w-full">
      {/* Who */}
      <p className="font-roboto text-white/70 text-xs font-bold uppercase tracking-wider mb-2">
        Who's this of?
      </p>

      <div className="flex flex-wrap gap-2">
        {pets.map((p) => (
          <button
            key={p.id}
            onClick={() => onChangePet(p.id === petId ? null : p.id)}
            className={`flex items-center gap-2 px-3 py-2 rounded-xl font-roboto text-sm font-medium transition-colors ${
              p.id === petId
                ? 'bg-white/35 text-white ring-1 ring-white/60'
                : 'bg-white/15 text-white/75 hover:bg-white/25'
            }`}
          >
            <PawPrint className="w-4 h-4" />
            {p.name}
          </button>
        ))}

        <button
          onClick={onAddPet}
          className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-white/70 font-roboto text-sm font-medium transition-colors border border-dashed border-white/30"
        >
          <Plus className="w-4 h-4" />
          {pets.length ? 'New pet' : 'Add a pet'}
        </button>
      </div>

      {!petId && (
        <p className="font-roboto text-white/55 text-xs mt-2.5 flex items-start gap-1.5">
          <Info className="w-3.5 h-3.5 flex-none mt-0.5" />
          {pets.length
            ? "We'll analyse this clip but won't save it to anyone's record."
            : 'Analysing as a one-off. Add a pet to start tracking changes over time.'}
        </p>
      )}

      {/* What kind — only relevant when it's being saved */}
      <AnimatePresence>
        {petId && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <p className="font-roboto text-white/70 text-xs font-bold uppercase tracking-wider mt-4 mb-2">
              What kind of capture?
            </p>
            <div className="flex flex-wrap gap-2">
              {CONTEXTS.map((c) => {
                const Icon = c.icon;
                const on = c.id === context;
                return (
                  <button
                    key={c.id}
                    onClick={() => onChangeContext(on ? null : c.id)}
                    className={`flex items-center gap-2 px-3 py-2 rounded-xl font-roboto text-sm transition-colors ${
                      on
                        ? 'bg-white/35 text-white ring-1 ring-white/60 font-medium'
                        : 'bg-white/15 text-white/75 hover:bg-white/25'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {c.label}
                  </button>
                );
              })}
            </div>
            {activeContext && (
              <p className="font-roboto text-white/55 text-xs mt-2.5 flex items-start gap-1.5">
                <Info className="w-3.5 h-3.5 flex-none mt-0.5" />
                {activeContext.hint}
              </p>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {selected && (
        <p className="font-roboto text-white/45 text-[11px] mt-3">
          Saving to {selected.name}'s record
          {selected.analysis_count > 0 && ` · ${selected.analysis_count} so far`}
        </p>
      )}
    </div>
  );
}
