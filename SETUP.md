# Etho — Setup

Two services. The backend runs the AI pipeline on Railway; the frontend is a
web app on Vercel. They talk over HTTPS.

```
  Vercel (frontend)  ──►  Railway (backend)  ──►  Google Gemini
   what people see          the analysis            the AI model
```

You only ever set **four** values. Everything else configures itself.

---

## Step 1 — Railway (the backend)

**Variables** tab → add:

| Name | Value |
|---|---|
| `GEMINI_API_KEY` | your Google AI Studio key |
| `API_KEY` | any long random string you invent — this is the password that protects your backend |

Keep `API_KEY` somewhere safe; you need the identical value in Step 2.

**Volumes** tab → **Add Volume**, mount path `/data`.

That's it — no `DATA_DIR` variable needed. The app detects the volume
automatically. Without a volume, every pet's history is erased each time you
deploy.

---

## Step 2 — Vercel (the frontend)

**Settings → Environment Variables** → add:

| Name | Value |
|---|---|
| `VITE_API_URL` | your Railway URL, e.g. `https://etho-backend-production.up.railway.app` |
| `VITE_API_KEY` | the **exact same** string you used for `API_KEY` above |

**Settings → Git**: point the project at `luapk/etho-backend`
(the frontend now lives in the same repository as the backend).

**Settings → General → Root Directory**: set to `frontend`.

**Deployments → ⋯ → Redeploy.** Vercel does not pick up new variables until
you rebuild.

---

## Step 3 — Check it worked

Open in a browser:

```
https://<your-railway-url>/health
```

Look at the `setup` section. Every check should say `"ok": true`. If any says
false, its `detail` tells you exactly what to fix in plain English.

Then upload a video through the site. If it analyses, you're done.

---

## If something breaks

**"The API key was rejected"** — `VITE_API_KEY` in Vercel doesn't match
`API_KEY` in Railway, or you changed it without redeploying Vercel.

**"Cannot connect to server"** — `VITE_API_URL` is wrong or missing the
`https://` prefix.

**Pet history disappeared after a deploy** — no volume is mounted in Railway.
Step 1, Volumes.

**First upload after a deploy is very slow** — normal. The pose models
(~12 MB) download once on the first request.

**Something else** — `/health` names the problem. Railway's deploy log prints
the same checklist every time the app starts.

---

## Order matters

Setting `API_KEY` on Railway before Vercel has a matching `VITE_API_KEY` will
break uploads in the gap. Safe order:

1. Railway: volume + `GEMINI_API_KEY` (leave `API_KEY` unset for now)
2. Vercel: both variables, repo, root directory → redeploy → confirm the site works
3. Railway: now add `API_KEY`
4. Upload a test video — if it works, protection is live

---

## Local development

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000     # backend, no keys needed
cd frontend && npm install && npm run dev     # frontend
```

With `API_KEY` unset the backend is open, so no key juggling locally. Seed
demo pets with weeks of history:

```bash
PYTHONPATH=. python scripts/seed_demo.py
```
