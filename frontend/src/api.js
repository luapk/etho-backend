/*
 * Central API client.
 *
 * Every call goes through here so the base URL and the X-API-Key header are
 * set in exactly one place. The backend rejects uploads with 401 when API_KEY
 * is configured server-side, so the header is always attached when we have a
 * key and omitted entirely when we don't (keeps local dev against an open
 * backend working).
 */
import axios from 'axios';

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
export const API_KEY = import.meta.env.VITE_API_KEY || '';

const client = axios.create({ baseURL: API_URL });

client.interceptors.request.use((config) => {
  if (API_KEY) config.headers['X-API-Key'] = API_KEY;
  return config;
});

/** Turn an axios failure into something a pet parent can act on. */
export function friendlyError(err) {
  if (err.code === 'ERR_NETWORK') {
    return "Can't reach the server. Check your connection and try again.";
  }
  if (err.response?.status === 401) {
    return API_KEY
      ? 'The API key was rejected. Check VITE_API_KEY matches the backend.'
      : 'This server needs an API key. Set VITE_API_KEY and redeploy.';
  }
  if (err.response?.status === 404) return 'Not found.';
  if (err.response?.status === 413) return 'That file is too large.';
  return err.response?.data?.detail || err.message || 'Something went wrong.';
}

// ── Pets ─────────────────────────────────────────────────────────────────────

export const listPets = () =>
  client.get('/api/pets').then((r) => r.data.pets || []);

export const getPet = (id) =>
  client.get(`/api/pets/${id}`).then((r) => r.data);

export const createPet = (pet) =>
  client.post('/api/pets', pet).then((r) => r.data.pet);

export const updatePet = (id, patch) =>
  client.patch(`/api/pets/${id}`, patch).then((r) => r.data.pet);

// ── Longitudinal record ──────────────────────────────────────────────────────

export const getTimeline = (id) =>
  client.get(`/api/pets/${id}/timeline`).then((r) => r.data.timeline || []);

export const getTrends = (id) =>
  client.get(`/api/pets/${id}/trends`).then((r) => r.data.trends);

export const getHistory = (id) =>
  client.get(`/api/pets/${id}/history`).then((r) => r.data.history || []);

export const getAnalysis = (id) =>
  client.get(`/api/analyses/${id}`).then((r) => r.data.analysis);

export const getVetReport = (id, reason) =>
  client
    .get(`/api/pets/${id}/vet-report`, {
      params: { reason: reason || undefined, format: 'markdown' },
      responseType: 'text',
    })
    .then((r) => r.data);

// ── Weights ──────────────────────────────────────────────────────────────────

export const getWeights = (id) =>
  client.get(`/api/pets/${id}/weights`).then((r) => r.data);

export const addWeight = (id, weight_kg, note) =>
  client.post(`/api/pets/${id}/weights`, { weight_kg, note }).then((r) => r.data);

// ── Capture protocol ─────────────────────────────────────────────────────────

export const getCaptureProtocol = () =>
  client.get('/api/capture-protocol').then((r) => r.data.protocol);

// ── Uploads ──────────────────────────────────────────────────────────────────

const isImage = (file) => (file.type || '').startsWith('image/');

/** Analyse one clip or photo. onProgress receives 0-100. */
export function uploadMedia(file, { petId, context, onProgress } = {}) {
  const form = new FormData();
  form.append('file', file);
  const endpoint = isImage(file) ? '/api/image/upload' : '/api/video/upload';
  return client
    .post(endpoint, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: {
        ...(isImage(file) ? {} : { mode: 'full' }),
        ...(petId ? { pet_id: petId } : {}),
        ...(context ? { context } : {}),
      },
      onUploadProgress: (e) => {
        if (onProgress && e.total) {
          onProgress(Math.round((e.loaded * 100) / e.total));
        }
      },
    })
    .then((r) => r.data);
}

/** Import many files at once. Returns { batch_id, queued, rejected }. */
export function uploadBatch(files, { petId, context, onProgress } = {}) {
  const form = new FormData();
  files.forEach((f) => form.append('files', f));
  return client
    .post('/api/batch/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: { ...(petId ? { pet_id: petId } : {}), ...(context ? { context } : {}) },
      onUploadProgress: (e) => {
        if (onProgress && e.total) {
          onProgress(Math.round((e.loaded * 100) / e.total));
        }
      },
    })
    .then((r) => r.data);
}

export const getBatchStatus = (batchId) =>
  client.get(`/api/batch/${batchId}`).then((r) => r.data.batch);

export const annotatedMediaUrl = (mediaId) =>
  `${API_URL}/api/video/annotated/${mediaId}`;
