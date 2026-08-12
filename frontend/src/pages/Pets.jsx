import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, ChevronDown, ChevronUp, Check, PawPrint, AlertTriangle,
         Calendar, Scale, ChevronRight } from 'lucide-react';
import { listPets, createPet, fetchPetAvatar, friendlyError } from '../api';
import { ageString } from './PetProfile';

/*
 * Pet profiles.
 *
 * Creating a pet is deliberately TWO fields — a name and cat-or-dog. That is
 * genuinely all the record layer needs to start: the species picks which
 * assessment instrument applies. Everything else (breed, birthday, weight)
 * sharpens the analysis but is optional and can be added later, so a guardian
 * is never blocked behind a form on their first visit.
 */

const SPECIES = [
  { id: 'dog', label: 'Dog' },
  { id: 'cat', label: 'Cat' },
];

/** A pet's portrait, or a paw. Blob-fetched because avatars are owner-scoped
 *  and an <img src> can't carry the API key. */
function Avatar({ pet }) {
  const [url, setUrl] = useState(null);

  useEffect(() => {
    if (!pet.has_avatar) { setUrl(null); return undefined; }
    let objectUrl = null;
    let cancelled = false;
    fetchPetAvatar(pet.id).then((u) => {
      if (cancelled) { if (u) URL.revokeObjectURL(u); return; }
      objectUrl = u;
      setUrl(u);
    });
    return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [pet.id, pet.has_avatar]);

  return (
    <div className="w-14 h-14 rounded-full overflow-hidden bg-white/20 flex items-center justify-center flex-none">
      {url
        ? <img src={url} alt="" className="w-full h-full object-cover" />
        : <PawPrint className="w-6 h-6 text-white" />}
    </div>
  );
}

function TrendPill({ pet }) {
  const n = pet.analysis_count || 0;
  if (!n) {
    return <span className="text-white/50 text-xs">No observations yet</span>;
  }
  return (
    <span className="text-white/70 text-xs">
      {n} observation{n === 1 ? '' : 's'}
      {pet.last_analysis_at && ` · last ${new Date(pet.last_analysis_at).toLocaleDateString()}`}
    </span>
  );
}

export default function Pets({ activePetId, onSelectPet, onViewTimeline, onOpenProfile }) {
  const [pets, setPets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [adding, setAdding] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showMore, setShowMore] = useState(false);
  const [form, setForm] = useState({
    name: '', species: 'dog', breed: '', sex: '', birthdate: '', weight_kg: '',
  });

  const load = () => {
    setLoading(true);
    listPets()
      .then((p) => { setPets(p); setError(null); })
      .catch((e) => setError(friendlyError(e)))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        species: form.species,
        breed: form.breed.trim() || null,
        sex: form.sex || null,
        birthdate: form.birthdate || null,
        weight_kg: form.weight_kg ? parseFloat(form.weight_kg) : null,
      };
      const pet = await createPet(payload);
      setPets((prev) => [...prev, { ...pet, analysis_count: 0 }]);
      setForm({ name: '', species: 'dog', breed: '', sex: '', birthdate: '', weight_kg: '' });
      setAdding(false);
      setShowMore(false);
      onSelectPet?.(pet.id);
      if (!showMore) onOpenProfile?.(pet.id);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setSaving(false);
    }
  };

  const field = 'w-full px-4 py-3 rounded-xl bg-white/20 border border-white/30 text-white placeholder-white/50 font-roboto focus:outline-none focus:border-white/60';

  return (
    <div className="min-h-screen px-4 py-8 md:px-6">
      <div className="max-w-3xl mx-auto">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="font-roboto font-black text-3xl text-white mb-1">Your pets</h1>
          <p className="font-roboto text-white/70 mb-6">
            Add a pet to build a record over time. Each pet is compared only
            against their own history.
          </p>
        </motion.div>

        {error && (
          <div className="glass-card rounded-2xl p-4 mb-4 border-2 border-amber-500/50 flex gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-300 flex-none mt-0.5" />
            <p className="font-roboto text-white/90 text-sm">{error}</p>
          </div>
        )}

        {/* Existing pets */}
        {loading ? (
          <div className="glass-card rounded-2xl p-8 text-center">
            <p className="font-roboto text-white/60">Loading…</p>
          </div>
        ) : (
          <div className="space-y-3 mb-4">
            {pets.map((pet, i) => {
              const active = pet.id === activePetId;
              return (
                <motion.div
                  key={pet.id}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className={`glass-card rounded-2xl p-4 transition-all ${
                    active ? 'ring-2 ring-white' : ''
                  }`}
                >
                  <div className="flex items-center gap-4">
                    <Avatar pet={pet} />
                    <button
                      onClick={() => onOpenProfile?.(pet.id)}
                      className="flex-1 min-w-0 text-left"
                    >
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="font-roboto font-bold text-white text-lg">{pet.name}</h3>
                        {active && (
                          <span className="px-2 py-0.5 rounded-full bg-white/25 text-white text-[10px] font-bold tracking-wide uppercase">
                            Selected
                          </span>
                        )}
                      </div>
                      {/* capitalize is scoped to the species/breed span: applied
                          to the whole line it title-cases "old" and "kg". */}
                      <p className="font-roboto text-white/60 text-sm">
                        <span className="capitalize">
                          {[pet.species, pet.breed].filter(Boolean).join(' · ')}
                        </span>
                        {(() => {
                          const rest = [ageString(pet.birthdate),
                                        pet.weight_kg ? `${pet.weight_kg} kg` : null]
                            .filter(Boolean).join(' · ');
                          const head = [pet.species, pet.breed].filter(Boolean).length;
                          if (!rest) return head ? null : 'Tap to add their details';
                          return `${head ? ' · ' : ''}${rest}`;
                        })()}
                      </p>
                      <TrendPill pet={pet} />
                    </button>
                    <ChevronRight className="w-5 h-5 text-white/40 flex-none" />
                  </div>

                  <div className="flex gap-2 mt-3 pt-3 border-t border-white/10">
                    {!active && (
                      <button
                        onClick={() => onSelectPet?.(pet.id)}
                        className="px-3 py-2 rounded-xl bg-white/15 hover:bg-white/25 text-white/85 text-sm font-roboto font-medium transition-colors"
                      >
                        Select
                      </button>
                    )}
                    <button
                      onClick={() => onOpenProfile?.(pet.id)}
                      className="px-3 py-2 rounded-xl bg-white/15 hover:bg-white/25 text-white/85 text-sm font-roboto font-medium transition-colors"
                    >
                      Edit profile
                    </button>
                    {pet.analysis_count > 0 && (
                      <button
                        onClick={() => onViewTimeline?.(pet.id)}
                        className="px-3 py-2 rounded-xl bg-white/15 hover:bg-white/25 text-white/85 text-sm font-roboto font-medium transition-colors ml-auto"
                      >
                        Timeline
                      </button>
                    )}
                  </div>
                </motion.div>
              );
            })}
          </div>
        )}

        {/* Add a pet — two fields, everything else optional */}
        <AnimatePresence mode="wait">
          {!adding ? (
            <motion.button
              key="addbtn"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setAdding(true)}
              className="w-full glass-card rounded-2xl p-5 flex items-center justify-center gap-3 hover:bg-white/25 transition-colors"
            >
              <Plus className="w-5 h-5 text-white" />
              <span className="font-roboto font-bold text-white">
                {pets.length ? 'Add another pet' : 'Add your first pet'}
              </span>
            </motion.button>
          ) : (
            <motion.form
              key="addform"
              initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              onSubmit={submit}
              className="glass-card rounded-2xl p-5 space-y-4"
            >
              <div>
                <label className="font-roboto text-white/80 text-sm mb-2 block">
                  What's their name?
                </label>
                <input
                  autoFocus
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="e.g. Miso"
                  className={field}
                />
              </div>

              <div>
                <label className="font-roboto text-white/80 text-sm mb-2 block">
                  Cat or dog?
                </label>
                <div className="flex gap-2">
                  {SPECIES.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      onClick={() => setForm({ ...form, species: s.id })}
                      className={`flex-1 py-3 rounded-xl font-roboto font-medium transition-colors ${
                        form.species === s.id
                          ? 'bg-white/35 text-white ring-1 ring-white/60'
                          : 'bg-white/15 text-white/70 hover:bg-white/25'
                      }`}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
                <p className="font-roboto text-white/50 text-xs mt-2">
                  This decides which welfare scale we use — cats and dogs are
                  assessed differently.
                </p>
              </div>

              {/* Optional extras, hidden by default */}
              <button
                type="button"
                onClick={() => setShowMore(!showMore)}
                className="flex items-center gap-2 text-white/70 hover:text-white font-roboto text-sm"
              >
                {showMore ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                Add more details (optional)
              </button>

              <AnimatePresence>
                {showMore && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="space-y-3 overflow-hidden"
                  >
                    <input
                      value={form.breed}
                      onChange={(e) => setForm({ ...form, breed: e.target.value })}
                      placeholder="Breed (helps tailor the analysis)"
                      className={field}
                    />
                    <div className="flex gap-2">
                      {['female', 'male'].map((s) => (
                        <button
                          key={s}
                          type="button"
                          onClick={() => setForm({ ...form, sex: form.sex === s ? '' : s })}
                          className={`flex-1 py-3 rounded-xl font-roboto capitalize transition-colors ${
                            form.sex === s
                              ? 'bg-white/35 text-white ring-1 ring-white/60'
                              : 'bg-white/15 text-white/70 hover:bg-white/25'
                          }`}
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                    <div>
                      <label className="font-roboto text-white/60 text-xs mb-1 flex items-center gap-2">
                        <Calendar className="w-3.5 h-3.5" /> Date of birth
                      </label>
                      <input
                        type="date"
                        value={form.birthdate}
                        onChange={(e) => setForm({ ...form, birthdate: e.target.value })}
                        className={field}
                      />
                    </div>
                    <div>
                      <label className="font-roboto text-white/60 text-xs mb-1 flex items-center gap-2">
                        <Scale className="w-3.5 h-3.5" /> Weight (kg)
                      </label>
                      <input
                        type="number" step="0.1" min="0"
                        value={form.weight_kg}
                        onChange={(e) => setForm({ ...form, weight_kg: e.target.value })}
                        placeholder="e.g. 4.2"
                        className={field}
                      />
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              <div className="flex gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => { setAdding(false); setShowMore(false); }}
                  className="px-5 py-3 rounded-xl bg-white/15 hover:bg-white/25 text-white/80 font-roboto transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!form.name.trim() || saving}
                  className="flex-1 py-3 rounded-xl bg-white/35 hover:bg-white/45 disabled:opacity-40 disabled:cursor-not-allowed text-white font-roboto font-bold transition-colors flex items-center justify-center gap-2"
                >
                  <Check className="w-5 h-5" />
                  {saving ? 'Saving…' : 'Save pet'}
                </button>
              </div>
            </motion.form>
          )}
        </AnimatePresence>

        <p className="font-roboto text-white/50 text-xs text-center mt-6">
          You can analyse a clip without adding a pet — but linking it lets Etho
          spot changes over time.
        </p>
      </div>
    </div>
  );
}
