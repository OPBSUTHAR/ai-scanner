# AI Scanner — Deployment Guide

> Step-by-step hosting instructions for the AI Scanner.
> **One service hosts BOTH frontend and backend** — pick ONE option below (A, B, or C).

---

## 0. Read This First — Architecture

The AI Scanner is a **monolithic Flask app**, not a split frontend/backend:

```
Browser ──HTTPS──> Flask + Gunicorn (ONE container)
                    ├── serves HTML/CSS/JS  (src/templates/, src/static/)
                    └── serves JSON API     (/scan, /history, /api/...)
```

There is **no separate frontend to deploy**. The HTML, CSS, and JS live inside
the Flask app and are served by it. You deploy **one thing**.

### Why NOT Vercel / Netlify?

| Problem | Detail |
|---|---|
| Serverless timeouts | Vercel kills functions at 10s (free) / 300s (max). OCR pipeline needs `--timeout=120`. |
| Ephemeral disk | Scans saved to `/app/data` are wiped after every request. |
| No custom Docker | The app needs system packages (`tesseract-ocr`, `libzbar0`, Mesa/GL). |
| Size limits | `easyocr` + `transformers` exceed Vercel's ~250 MB function limit. |

Vercel is only useful here if you someday split out a React SPA — that static
part could go on Vercel while Flask stays on Render/Railway/VPS.

---

## 1. Prerequisites

1. Code pushed to GitHub → https://github.com/OPBSUTHAR/ai-scanner
2. **Repo layout note**: this GitHub repo's root contains `ai_scanner/` as a
   subfolder. On every platform below you MUST set
   **Root Directory = `ai_scanner`** so the Dockerfile is found.

Verify locally before deploying (optional but saves debug cycles):

```bash
cd ai_scanner
docker build -t ai-scanner .
docker run -p 8000:8000 ai-scanner
# open http://localhost:8000 — if this works, the deploy will work
```

---

## 2. Option A — Render (Free, easiest)

### A.1 Create the Web Service
1. Sign up at https://render.com with GitHub.
2. Dashboard → **New +** → **Web Service**.
3. Pick the `ai-scanner` repo (grant access if asked).
4. Configure:
   - **Name**: `ai-scanner`
   - **Root Directory**: `ai_scanner`  ← REQUIRED (Dockerfile lives here)
   - **Runtime**: `Docker`
   - **Instance Type**: `Free`
5. Click **Create Web Service**. First build takes 5–10 min (installs
   Tesseract, OpenCV, OCR libs).

Render assigns: `https://<your-app>.onrender.com` — **HTTPS included**, which
is what makes the live camera view work on phones.

> `render.yaml` in `ai_scanner/` mirrors these settings for Render Blueprints,
> but manual setup above is more reliable given the subfolder layout.

### A.2 Environment Variables
Dashboard → your service → **Environment**:

| Key | Value | Required? |
|-----|-------|-----------|
| `APP_ENV` | `production` | Yes |
| `APP_DEBUG` | `False` | Yes |
| `DATA_DIR` | `/app/data` | Yes |
| `PORT` | *(leave unset — Render injects it)* | — |

Cloud-feature keys are **optional** (Tesseract OCR works without them):

| Key | Used for |
|-----|----------|
| `GROQ_API_KEY` | **AI Assistant full chat quality for all users** — free key from console.groq.com (no credit card). Without it the assistant still works via the built-in rule-based engine |
| `GOOGLE_DRIVE_CLIENT_ID` / `GOOGLE_DRIVE_CLIENT_SECRET` | Drive sync |
| `GOOGLE_VISION_API_KEY` | Cloud OCR fallback |
| `DROPBOX_APP_KEY` / `DROPBOX_APP_SECRET` / `DROPBOX_ACCESS_TOKEN` | Dropbox sync |
| `ONEDRIVE_CLIENT_ID` / `ONEDRIVE_CLIENT_SECRET` / `ONEDRIVE_TENANT_ID` | OneDrive sync |

You can also skip env vars entirely and enter keys later in the app:
**Settings → API Keys** (stored encrypted).

### A.3 OAuth redirect URIs (only if using cloud sync)
The defaults in `.env.example` point at `localhost:5000`. For the hosted app,
register these exact URIs in each provider's console instead:

```
https://<your-app>.onrender.com/auth/google/callback        (Google Console)
https://<your-app>.onrender.com/cloud/callback/dropbox      (Dropbox app settings)
https://<your-app>.onrender.com/cloud/callback/onedrive     (Azure App Registration)
```

### A.4 Verify
Open `https://<your-app>.onrender.com` → log in (or Continue as Guest) → Scanner.

### A.5 Know the free-tier limits

| Limit | Reality | Workaround |
|---|---|---|
| Sleeps after 15 min idle | First visit takes ~30–60 s to wake | Upgrade ($7/mo Starter) or ping periodically |
| **No persistent disk on Free** | Uploaded scans are LOST on every redeploy/restart | Enable cloud sync (Drive/Dropbox), or paid plan + Disk mounted at `/app/data`, or self-host (Option C) |
| 512 MB RAM | Heavy batch scans may be slow | Keep batches small; upgrade for 2 GB |

---

## 3. Option B — Railway

1. Sign up at https://railway.app with GitHub (free trial credit; $5/mo Hobby for always-on).
2. **New Project** → **Deploy from GitHub repo** → select `ai-scanner`.
3. Service → **Settings**:
   - **Root Directory**: `/ai_scanner` ← REQUIRED
   - Railway auto-detects `railway.json` (Dockerfile build, health check `/`, restart policy).
4. **Variables** tab → add `APP_ENV=production`, `APP_DEBUG=False`, `DATA_DIR=/app/data`.
5. **Settings → Networking → Generate Domain** → you get an HTTPS URL.
6. Deploy → verify same as A.4.

Railway does not sleep like Render free, but trial credit runs out — add a
payment method or move to Option C when it does.

---

## 4. Option C — Self-Host with Coolify (100% open-source stack)

Render/Railway are closed-source platforms. If you want an **open-source**
hosting stack, run [Coolify](https://coolify.io) (open-source Heroku/Railway
alternative) on a cheap VPS. Alternatives: **Dokku** (CLI-only), **CapRover** (web UI).

### C.1 Get a VPS (~$4–6/month)
| Provider | Suggestion | Notes |
|---|---|---|
| Hetzner | CX22 (2 vCPU / 4 GB) | Best value; Docker builds of OpenCV/Torch deps need ≥2 GB RAM |
| Oracle Cloud | Always-Free VM (4 ARM OCPU / 24 GB) | Genuinely free forever, capacity varies |
| DigitalOcean | Basic 2 GB droplet | Simplest UI |

### C.2 Install Coolify (one command)
On a fresh Ubuntu 22.04/24.04 VPS:

```bash
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

Note the printed admin password, open `http://<VPS_IP>:8000`, log in, and set
the new password. Coolify automatically provisions HTTPS via Let's Encrypt
when you attach a domain.

### C.3 Deploy the app
1. Coolify → **+ New Resource** → **Docker Compose / Dockerfile** based app.
2. Connect the GitHub repo `OPBSUTHAR/ai-scanner`.
3. Set:
   - **Branch**: `main`
   - **Base Directory** (a.k.a. Root Directory): `/ai_scanner` ← REQUIRED
   - **Build Pack**: `Dockerfile` (it finds `./Dockerfile` inside the base dir)
4. **Environment Variables** → same table as A.2.
5. **Domains** → enter your domain (e.g. `scanner.yourdomain.com`) → Coolify
   issues a free Let's Encrypt cert → HTTPS live-view camera works.
6. **Deploy**. Subsequent `git push` redeployments can be enabled via
   **Webhooks** (or the built-in GitHub integration).
7. Optional: Resources → **Storage** → mount a persistent volume at
   `/app/data` so scans survive redeploys (something Render free can't do).

### C.4 DNS
Point an `A` record of your domain to the VPS IP. No domain? Use the VPS IP
over HTTP — the app still works, and the camera button now **auto-falls back
to the native OS camera app** (see §6), but the live in-page view requires HTTPS.

---

## 5. Post-Deployment Checklist

- [ ] Open the URL → login page loads (or guest mode works)
- [ ] Upload a photo/PDF → processes → appears in Vault
- [ ] Phone browser → Scanner → OPEN CAMERA:
  - over **HTTPS** → live view with edge detection + auto-capture
  - over **HTTP** → native phone camera opens instead (expected)
- [ ] Settings → API Keys → add cloud credentials (if using sync)
- [ ] Cloud sync test: scan a doc → confirm it lands in Drive/Dropbox/OneDrive
- [ ] Auto-deploy: push a commit → platform rebuilds (Render/Railway default ON)

Every push to `main` triggers a rebuild on Render/Railway. On Coolify enable
webhooks for the same behavior.

---

## 6. Camera Behavior (Cross-Platform Strategy)

Implemented in `src/static/js/app.js` — no configuration needed:

| Environment | What happens when user clicks OPEN CAMERA |
|---|---|
| HTTPS + modern browser | In-page **live view** with edge detection & auto-capture |
| HTTP / LAN IP / old browser / webview | Toast shown, then the **native OS camera app** opens via hidden `<input capture>` — works on Android, iOS, tablets, desktops |
| Permission denied | Same native-camera fallback |

So the scanner captures documents on **every device**, but for the premium
live-view experience serve over HTTPS (all three options above do).

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Build fails "Dockerfile not found" | Root Directory not set | Set it to `ai_scanner` (§A.1 / §3 / §C.3) |
| Build OOM-killed on VPS | <2 GB RAM during pip install | Use 4 GB VPS or add swap: `sudo fallocate -l 4G /swapfile` |
| App sleeps / slow first load | Render free spin-down | Expected; upgrade or keep-alive ping |
| Scans disappear after redeploy | Ephemeral disk on free tier | Cloud sync, persistent disk, or Option C |
| Camera shows error toast then native camera opens | You're on HTTP | Normal fallback — use HTTPS URL for live view |
| Live view black screen on iPhone | Missing playsinline/gesture | Already handled; use Safari 12+, tap the shutter once |
| Google/Dropbox login loops back to localhost | Redirect URI mismatch | Register hosted callback URIs (§A.3) |
| OCR returns empty | Scan too blurry/small | Retake closer, flatter, well-lit; or set `GOOGLE_VISION_API_KEY` |
| 502 after deploy | App crashed at boot | Check platform logs; usually a missing env var — `DATA_DIR=/app/data` |

---

## Quick Reference

### URLs (after deploy, replace host)
| Endpoint | Purpose |
|---|---|
| `GET /` | Dashboard (after login) |
| `GET /login` | Login page (guest mode available) |
| `POST /scan` | Single-document scan |
| `POST /scan/advanced` | Full pipeline (crop/enhance/classify/save) |
| `POST /api/batch/process` | Batch processing |
| `GET /history` · `GET /search?q=` · `GET /stats` | Vault data |
| `POST /pdf/merge` | Merge PDFs |
| `GET /api/ai/status` · `POST /api/ai/chat` | Local AI assistant |

### Deploy-critical files
```
ai_scanner/
├── Dockerfile        ← container image (Python 3.11 + Tesseract + zbar + GL)
├── .dockerignore     ← keeps .env/tokens out of the image
├── railway.json      ← Railway build/deploy settings
├── render.yaml       ← Render blueprint mirror
├── startup.sh        ← gunicorn launcher honoring $PORT
└── src/web_app.py    ← Flask entrypoint (gunicorn target: src.web_app:app)
```

### Cost summary
| Option | Monthly cost | Persistent scans? | Always-on? |
|---|---|---|---|
| Render Free | $0 | ✗ (ephemeral) | Sleeps after idle |
| Railway Hobby | $5 | Optional volume | ✓ |
| Coolify on Hetzner CX22 | ~$4.5 | ✓ (volume) | ✓ |
| Oracle Cloud free VM + Coolify | $0 | ✓ | ✓ |

---

## Recommendation

- **Demo/portfolio right now:** Option A (Render Free) — zero cost, HTTPS, live in 10 min.
- **Always-on production:** Option C (Coolify on a $4–5 VPS) — open-source stack, persistent disk, no sleep, full control.
