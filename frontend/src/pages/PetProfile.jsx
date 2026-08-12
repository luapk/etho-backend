import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { ArrowLeft, Camera, Check, Trash2, PawPrint, AlertTriangle,
         CalendarRange, Loader, Image as ImageIcon } from 'lucide-react';
import { getPet, updatePet, uploadPetAvatar, deletePetAvatar, fetchPetAvatar,
         uploadPetWallpaper, deletePetWallpaper, fetchPetWallpaper,
         wallpaperFromAvatar, getBreedContext, friendlyError } from '../api';
import AvatarCropper from '../components/AvatarCropper';

/*
 * One pet's profile, editable.
 *
 * Sign-up asks for a name and nothing else, which is right for a first visit
 * and leaves everything the record actually benefits from unfilled. This is
 * where a guardian fills it in later, at their own pace.
 *
 * Each field says what it CHANGES rather than just what it is, because none of
 * them are administrative: species picks the welfare instrument, breed unlocks
 * the capture plan and the weight range, birthdate is signalment on the vet
 * report. A field with no consequence shouldn't be on the form.
 */

const SPECIES = [{ id: 'dog', label: 'Dog' }, { id: 'cat', label: 'Cat' }];
const SEXES = [{ id: 'female', label: 'Female' }, { id: 'male', label: 'Male' }];

/** Years and months, the way a vet writes signalment. */
export function ageString(birthdate) {
  if (!birthdate) return null;
  const bd = new Date(birthdate);
  if (Number.isNaN(bd.getTime())) return null;
  const days = Math.floor((Date.now() - bd.getTime()) / 86400000);
  if (days < 0) return null;
  const years = Math.floor(days / 365);
  const months = Math.floor((days % 365) / 30);
  if (years === 0) return `${months} month${months === 1 ? '' : 's'} old`;
  return `${years}y ${months}m old`;
}

/* How filled-in a pet's profile is.
 *
 * Only fields that CHANGE something are counted — species picks the welfare
 * instrument, breed unlocks the capture plan and the weight range, birthdate
 * is signalment on the vet report. Free-text notes are deliberately excluded:
 * counting them would mean nobody ever reaches 100%, which turns the ring into
 * permanent nagging rather than a finishable task.
 */
export const PROFILE_FIELDS = [
  { key: 'has_avatar', label: 'a photo' },
  { key: 'species', label: 'cat or dog' },
  { key: 'breed', label: 'their breed' },
  { key: 'sex', label: 'sex' },
  { key: 'birthdate', label: 'date of birth' },
  { key: 'weight_kg', label: 'weight' },
];

export function profileCompleteness(pet) {
  if (!pet) return { done: 0, total: PROFILE_FIELDS.length, percent: 0, missing: [] };
  const missing = PROFILE_FIELDS.filter((f) => {
    const v = pet[f.key];
    return v === null || v === undefined || v === '' || v === false;
  });
  const done = PROFILE_FIELDS.length - missing.length;
  return {
    done,
    total: PROFILE_FIELDS.length,
    percent: Math.round((done / PROFILE_FIELDS.length) * 100),
    missing: missing.map((f) => f.label),
  };
}

const FIELD =
  'w-full px-4 py-3 rounded-xl bg-white/20 border border-white/30 text-white ' +
  'placeholder-white/40 font-roboto focus:outline-none focus:border-white/60';
const LABEL = 'font-roboto text-white/80 text-sm mb-1.5 block';
const HINT = 'font-roboto text-white/45 text-xs mt-1.5';

export default function PetProfile({ petId, onBack, onViewTimeline, onChanged,
                                     embedded = false }) {
  const [pet, setPet] = useState(null);
  const [form, setForm] = useState(null);
  const [avatarUrl, setAvatarUrl] = useState(null);
  const [avatarBusy, setAvatarBusy] = useState(false);
  const [wallpaperUrl, setWallpaperUrl] = useState(null);
  const [wallBusy, setWallBusy] = useState(false);
  const [pendingPhoto, setPendingPhoto] = useState(null);   // awaiting framing
  const [breedCtx, setBreedCtx] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);
  const fileRef = useRef(null);
  const urlRef = useRef(null);
  const wallRef = useRef(null);
  const wallUrlRef = useRef(null);

  const setAvatar = (url) => {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = url;
    setAvatarUrl(url);
  };

  const loadAvatar = () => fetchPetAvatar(petId).then(setAvatar);

  useEffect(() => {
    getPet(petId)
      .then((r) => {
        setPet(r.pet);
        setForm({
          name: r.pet.name || '',
          species: r.pet.species || '',
          breed: r.pet.breed || '',
          sex: r.pet.sex || '',
          birthdate: (r.pet.birthdate || '').slice(0, 10),
          weight_kg: r.pet.weight_kg ?? '',
          notes: r.pet.notes || '',
        });
      })
      .catch((e) => setError(friendlyError(e)));
    loadAvatar();
    loadWallpaper();
    getBreedContext(petId).then(setBreedCtx).catch(() => {});
    return () => {
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
      if (wallUrlRef.current) URL.revokeObjectURL(wallUrlRef.current);
    };
  }, [petId]);

  const pickAvatar = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    // Frame it first. A centre crop is a guess and usually puts the floor in
    // the circle instead of the face.
    setPendingPhoto(file);
    e.target.value = '';
  };

  const saveCropped = async (cropped) => {
    setAvatarBusy(true);
    try {
      await uploadPetAvatar(petId, cropped);
      await loadAvatar();
      setPendingPhoto(null);
      onChanged?.();
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setAvatarBusy(false);
    }
  };

  const setWallpaper = (url) => {
    if (wallUrlRef.current) URL.revokeObjectURL(wallUrlRef.current);
    wallUrlRef.current = url;
    setWallpaperUrl(url);
  };

  const loadWallpaper = () => fetchPetWallpaper(petId).then(setWallpaper);

  const runWallpaper = async (fn) => {
    setWallBusy(true);
    setError(null);
    try {
      await fn();
      await loadWallpaper();
      onChanged?.();
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setWallBusy(false);
    }
  };

  const pickWallpaper = (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    // No cropper here, unlike the avatar: a background is displayed at every
    // shape a phone can be, so the browser has to do the cropping at render
    // time anyway and a fixed crop would only throw away the margin it needs.
    runWallpaper(() => uploadPetWallpaper(petId, file));
  };

  const useAvatarAsWallpaper = () => runWallpaper(() => wallpaperFromAvatar(petId));
  const removeWallpaper = () => runWallpaper(async () => {
    await deletePetWallpaper(petId);
    setWallpaper(null);
  });

  const removeAvatar = async () => {
    setAvatarBusy(true);
    try {
      await deletePetAvatar(petId);
      setAvatar(null);
      onChanged?.();
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setAvatarBusy(false);
    }
  };

  const save = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updatePet(petId, {
        name: form.name.trim(),
        species: form.species || null,
        breed: form.breed.trim() || null,
        sex: form.sex || null,
        birthdate: form.birthdate || null,
        weight_kg: form.weight_kg === '' ? null : parseFloat(form.weight_kg),
        notes: form.notes.trim() || null,
      });
      setPet(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2200);
      onChanged?.();
      // Breed drives the capture plan, so re-read what this pet now unlocks.
      getBreedContext(petId).then(setBreedCtx).catch(() => {});
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setSaving(false);
    }
  };

  if (error && !form) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="glass-card rounded-2xl p-8 max-w-md text-center">
          <AlertTriangle className="w-12 h-12 text-amber-400 mx-auto mb-3" />
          <p className="font-roboto text-white mb-5">{error}</p>
          <button onClick={onBack}
                  className="px-5 py-3 rounded-xl bg-white/30 hover:bg-white/40 text-white font-roboto font-bold">
            Back
          </button>
        </div>
      </div>
    );
  }

  if (!form) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="font-roboto text-white/60">Loading profile…</p>
      </div>
    );
  }

  const age = ageString(form.birthdate);
  const breedRecognised = breedCtx?.predispositions?.length > 0;

  return (
    <div className={`px-4 md:px-6 ${embedded ? 'pt-6 pb-12' : 'min-h-screen py-8'}`}>
      <div className="max-w-xl mx-auto">
        {/* Embedded in the pet page, the tab bar is the way back. */}
        {!embedded && onBack && (
          <button
            onClick={onBack}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl glass-card hover:bg-white/25 text-white font-roboto font-medium transition-colors mb-4"
          >
            <ArrowLeft className="w-4 h-4" /> All pets
          </button>
        )}

        {pendingPhoto && (
          <div className="mb-6">
            <AvatarCropper
              file={pendingPhoto}
              busy={avatarBusy}
              onCancel={() => setPendingPhoto(null)}
              onCropped={saveCropped}
            />
          </div>
        )}

        {/* Portrait */}
        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          className={`flex flex-col items-center mb-6 mt-1 ${pendingPhoto ? 'hidden' : ''}`}
        >
          <button
            onClick={() => fileRef.current?.click()}
            disabled={avatarBusy}
            className="relative w-[10.4rem] h-[10.4rem] rounded-full overflow-hidden bg-white/15 ring-2 ring-white/30 hover:ring-white/60 transition-all group"
          >
            {avatarUrl ? (
              <img src={avatarUrl} alt={form.name} className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <PawPrint className="w-16 h-16 text-white/50" />
              </div>
            )}
            <div className="absolute inset-0 bg-black/45 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
              {avatarBusy
                ? <Loader className="w-7 h-7 text-white animate-spin" />
                : <Camera className="w-7 h-7 text-white" />}
            </div>
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={pickAvatar}
            className="hidden"
          />

          {!embedded && (
          <h1 className="font-roboto font-black text-3xl text-white mt-4 text-center">
            {form.name || 'Unnamed'}
          </h1>
          )}
          {!embedded && (
          <p className="font-roboto text-white/60 text-sm">
            <span className="capitalize">
              {[form.species, form.breed].filter(Boolean).join(' · ')}
            </span>
            {age ? `${form.species || form.breed ? ' · ' : ''}${age}` : null}
            {!form.species && !form.breed && !age ? 'No details yet' : null}
          </p>
          )}
          {!embedded && pet?.analysis_count > 0 && (
            <button
              onClick={() => onViewTimeline?.(petId)}
              className="flex items-center gap-2 mt-3 px-4 py-2 rounded-xl bg-white/15 hover:bg-white/25 text-white/85 font-roboto text-sm transition-colors"
            >
              <CalendarRange className="w-4 h-4" />
              {pet.analysis_count} observation{pet.analysis_count === 1 ? '' : 's'} · timeline
            </button>
          )}
          <div className="flex gap-3 mt-3">
            <button
              onClick={() => fileRef.current?.click()}
              className="font-roboto text-white/60 hover:text-white text-xs transition-colors"
            >
              {avatarUrl ? 'Change photo' : 'Add a photo'}
            </button>
            {avatarUrl && (
              <button
                onClick={removeAvatar}
                className="flex items-center gap-1 font-roboto text-white/45 hover:text-white/80 text-xs transition-colors"
              >
                <Trash2 className="w-3 h-3" /> Remove
              </button>
            )}
          </div>
        </motion.div>

        {error && (
          <div className="glass-card rounded-2xl p-4 mb-4 border-2 border-amber-500/50 flex gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-300 flex-none mt-0.5" />
            <p className="font-roboto text-white/90 text-sm">{error}</p>
          </div>
        )}

        {/* Details. Every field says what it changes — none of them are
            paperwork, and one that changed nothing wouldn't be here. */}
        <form onSubmit={save} className="glass-card rounded-2xl p-5 space-y-5">
          <div>
            <label className={LABEL}>Name</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className={FIELD}
            />
          </div>

          <div>
            <label className={LABEL}>Cat or dog</label>
            <div className="flex gap-2">
              {SPECIES.map((s) => (
                <button
                  key={s.id} type="button"
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
            <p className={HINT}>
              Decides which welfare scale is used — cats are scored on the
              Feline Grimace Scale, dogs on an observable stress subset.
            </p>
          </div>

          <div>
            <label className={LABEL}>Breed</label>
            <input
              value={form.breed}
              onChange={(e) => setForm({ ...form, breed: e.target.value })}
              placeholder="e.g. Maine Coon"
              className={FIELD}
            />
            <p className={HINT}>
              Tailors what's worth filming, and sets the weight range we compare
              against. Only ever used when you've entered it yourself — Etho
              won't act on a breed it guessed from a video.
            </p>
            {breedRecognised && (
              <p className="font-roboto text-white/70 text-xs mt-2 flex items-start gap-1.5">
                <Check className="w-3.5 h-3.5 flex-none mt-0.5 text-green-300" />
                Recognised — {form.breed}'s capture suggestions are on their
                timeline, and the vet report gets a cited breed appendix.
              </p>
            )}
          </div>

          <div>
            <label className={LABEL}>Sex</label>
            <div className="flex gap-2">
              {SEXES.map((s) => (
                <button
                  key={s.id} type="button"
                  onClick={() => setForm({ ...form, sex: form.sex === s.id ? '' : s.id })}
                  className={`flex-1 py-3 rounded-xl font-roboto transition-colors ${
                    form.sex === s.id
                      ? 'bg-white/35 text-white ring-1 ring-white/60'
                      : 'bg-white/15 text-white/70 hover:bg-white/25'
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className={LABEL}>Date of birth</label>
            <input
              type="date"
              value={form.birthdate}
              max={new Date().toISOString().slice(0, 10)}
              onChange={(e) => setForm({ ...form, birthdate: e.target.value })}
              className={FIELD}
            />
            <p className={HINT}>
              {age ? `${age}. ` : ''}Shown as signalment on the vet report.
            </p>
          </div>

          <div>
            <label className={LABEL}>Weight (kg)</label>
            <input
              type="number" step="0.1" min="0"
              value={form.weight_kg}
              onChange={(e) => setForm({ ...form, weight_kg: e.target.value })}
              placeholder="e.g. 4.2"
              className={FIELD}
            />
            <p className={HINT}>
              Screened against the typical adult range for their breed. Body
              condition score by a vet is still the real measure.
            </p>
          </div>

          <div>
            <label className={LABEL}>Anything a vet should know</label>
            <textarea
              rows={3}
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              placeholder="Medication, past injuries, recent house move…"
              className={`${FIELD} resize-none`}
            />
            <p className={HINT}>Printed on the vet report under signalment.</p>
          </div>

          <button
            type="submit"
            disabled={saving || !form.name.trim()}
            className="w-full py-4 rounded-xl bg-white/35 hover:bg-white/45 disabled:opacity-40 text-white font-roboto font-bold transition-colors flex items-center justify-center gap-2"
          >
            {saved ? <Check className="w-5 h-5" /> : null}
            {saving ? 'Saving…' : saved ? 'Saved' : 'Save changes'}
          </button>
        </form>

        {/* Background photo.
            Offered from the camera roll or from the profile picture, and
            deliberately NOT from the stored captures: everything the library
            keeps is annotated, so a "photo of Louis" from the timeline would
            arrive with a green detection box and a distress meter burned into
            it. That is a screenshot of the tool, not a picture of the animal. */}
        <div className="glass-card rounded-2xl p-5 mt-4">
          <h2 className="font-roboto font-bold text-white mb-1">Background photo</h2>
          <p className="font-roboto text-white/50 text-sm mb-4">
            Fills the screen behind {form.name || 'them'}'s pages. Dimmed so the
            readings stay readable on top of it.
          </p>

          <div className="rounded-xl overflow-hidden bg-black/25 border border-white/15 aspect-[16/10] flex items-center justify-center mb-3">
            {wallpaperUrl ? (
              <img src={wallpaperUrl} alt="" className="w-full h-full object-cover" />
            ) : (
              <div className="text-center px-6">
                <ImageIcon className="w-7 h-7 text-white/25 mx-auto mb-2" />
                <p className="font-roboto text-white/40 text-xs">No background set</p>
              </div>
            )}
          </div>

          <input
            ref={wallRef}
            type="file"
            accept="image/*"
            onChange={pickWallpaper}
            className="hidden"
          />
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => wallRef.current?.click()}
              disabled={wallBusy}
              className="px-4 py-2.5 rounded-xl bg-white/20 hover:bg-white/30 disabled:opacity-50 text-white font-roboto text-sm font-bold transition-colors"
            >
              {wallBusy ? 'Saving…' : wallpaperUrl ? 'Change photo' : 'Choose a photo'}
            </button>
            {avatarUrl && (
              <button
                type="button"
                onClick={useAvatarAsWallpaper}
                disabled={wallBusy}
                className="px-4 py-2.5 rounded-xl bg-white/10 hover:bg-white/20 disabled:opacity-50 text-white/80 font-roboto text-sm transition-colors"
              >
                Use profile picture
              </button>
            )}
            {wallpaperUrl && (
              <button
                type="button"
                onClick={removeWallpaper}
                disabled={wallBusy}
                className="flex items-center gap-1 px-3 py-2.5 rounded-xl text-white/45 hover:text-white/85 font-roboto text-sm transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" /> Remove
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
