# Etho — Project Handoff
**Date:** 2026-08-04
**Backend repo:** github.com/luapk/etho-backend (branch: `main`)
**Frontend repo:** github.com/luapk/etho-frontend (branch: `feat/annotated-video-pose-metrics`)

---

## What Etho does

Etho is an AI-powered pet behaviour analysis tool. A user uploads or records a short video of their pet; the system returns:
- A structured ethological analysis (distress score, behavioural markers, timeline)
- An annotated MP4 with bounding boxes, skeleton overlay, breed tag, and distress meter overlaid
- First-person "pet POV" interpretation lines
- An actionable advisory with urgency rating

---

## Architecture

```
Frontend (Vercel)  →  POST /api/video/upload  →  Backend (Railway)
                                                        │
                                          ┌─────────────┼─────────────┐
                                    Step 1: YOLO    Step 2-3:     Step 4:
                                    pose detect     Gemini 2-pass  annotate
                                    (yolo11n.pt +   (scene verify  video
                                    yolo11n-pose)   + analysis)    (OpenCV)
```

### Services

| File | Responsibility |
|------|---------------|
| `app/main.py` | FastAPI app, pipeline orchestration, API key auth |
| `app/services/gemini_service.py` | Gemini File API, two-pass analysis, JSON validation |
| `app/services/yolo_pose_service.py` | Pet detection, keypoint extraction, spinal angle + head tilt |
| `app/services/video_annotator.py` | Annotated MP4 rendering (bbox, skeleton, distress meter, text) |
| `app/prompts/ethological_prompt.py` | Full Gemini system prompt — output schema + research frameworks |
| `research/` | 8 framework reference cards + BibTeX library + MODEL_GUIDE.md |

### Key endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/video/upload` | X-API-Key | Main analysis pipeline |
| GET | `/api/video/annotated/{id}` | None | Download annotated MP4 |
| GET | `/api/research/bundle` | X-API-Key | Download research ZIP |
| GET | `/health` | None | Health check |

---

## Environment variables

### Railway (backend)
| Variable | Required | Value |
|----------|----------|-------|
| `GEMINI_API_KEY` | Yes | Google AI Studio key |
| `API_KEY` | **Yes — set this now** | Any strong random string — protects all upload/research endpoints |

### Vercel (frontend)
| Variable | Required | Value |
|----------|----------|-------|
| `VITE_API_URL` | Yes | Your Railway backend URL |
| `VITE_API_KEY` | **Yes — set this now** | Same value as `API_KEY` above |
| `VITE_APP_PASSWORD` | Yes | Frontend password gate |

**Warning:** Until `API_KEY` is set in Railway, the auth check is skipped and the backend is open. Set it immediately.

---

## Immediate actions required

1. **Push frontend branch**
   ```bash
   cd /home/user/etho-frontend
   git push -u origin feat/annotated-video-pose-metrics
   ```

2. **Set Railway env vars** — Railway dashboard → Variables:
   ```
   API_KEY = <strong-random-string>
   ```

3. **Set Vercel env vars** — Vercel dashboard → Settings → Environment Variables:
   ```
   VITE_API_KEY      = <same-value-as-API_KEY>
   VITE_APP_PASSWORD = <strong-password>
   ```

4. **Redeploy frontend on Vercel** after env vars are saved

5. **Merge or deploy frontend PR** on Vercel from `feat/annotated-video-pose-metrics`

---

## Security notes

- The frontend password gate is cosmetic — the password is embedded in the compiled JS bundle. Anyone with DevTools can read it. The real protection is the `API_KEY` header on the backend.
- The backend `API_KEY` check is enforced server-side — requests without it receive `401 Unauthorized`
- Annotated videos are ephemeral — stored in `/tmp/etho_annotated/` and cleaned up after 2 hours
- No Google Analytics or traffic logging is currently configured. To investigate past usage: Railway logs (search `NEW ANALYSIS REQUEST`) + Google Cloud Console → Gemini API metrics

---

## Deployment

- **Backend:** Push to `main` on `luapk/etho-backend` → Railway auto-deploys via Nixpacks
- **Frontend:** Push to Vercel-connected branch → Vercel auto-deploys
- **First cold start:** YOLO downloads `yolo11n.pt` + `yolo11n-pose.pt` (~12MB total) — first request will be slow

---

## Research framework

The analysis is grounded in 22 peer-reviewed papers. The prompt (`app/prompts/ethological_prompt.py`) encodes:

| Framework | Source |
|-----------|--------|
| DogFACS | Waller et al., 2013; Caeiro et al., 2017 |
| CatFACS | Caeiro et al., 2013 |
| Feline Grimace Scale | Evangelista et al., 2019 |
| Inner brow raise (AU101) | Kaminski et al., 2019 — PNAS |
| Tail lateralisation | Quaranta et al., 2007 — Current Biology |
| Canine voice cortex | Andics et al., 2016 — Science |
| Morton's acoustic rules | Morton, 1977 |
| Canine bio-acoustics | Pongrácz et al., 2005; Faragó et al., 2010, 2014 |
| Cat prosody | Schötz Meowsic project, 2016–2022 |
| Solicitation purr | McComb et al., 2009 |
| Glasgow CMPS pain scale | Reid et al., 2007 |
| WSAVA pain guidelines | Mathews et al., 2014 |
| Umwelt theory | von Uexküll, 1934 |
| Breed morphology | McGreevy et al., 2004; Goodwin et al., 1997 |
| Nosework & autonomy | Duranton & Horowitz, 2019 |
| Separation welfare | Rehn & Keeling, 2011 |
| YOLO11-Pose | Jocher & Qiu, 2024 |

Full BibTeX library: `research/references.bib`
Full AI model guide: `research/MODEL_GUIDE.md`

---

## Known issues / future improvements

- YOLO uses a human-pose model (COCO-17) applied to animals — accuracy is approximate. Upgrading to an AP-10K animal pose model would improve keypoint localisation for tail, spine, and limb endpoints
- Annotated videos use `mp4v` codec — plays in most browsers but not all mobile Safari versions
- No request logging beyond print statements — add structured logging + IP capture for traffic auditing
- No Google Analytics on the frontend — add GA4 tag to `index.html` when ready
- Frontend password gate is client-side only — purely cosmetic, real auth is the API key
