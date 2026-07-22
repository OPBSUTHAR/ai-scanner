# AI Scanner — Deployment Guide

> Manual steps to deploy the AI Scanner on **Render** (backend) + **Vercel** (frontend) with **MongoDB Atlas** (optional).

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Deploy Backend on Render (Free)](#2-deploy-backend-on-render-free)
3. [Deploy Frontend on Vercel (Free)](#3-deploy-frontend-on-vercel-free)
4. [Connect MongoDB Atlas (Optional)](#4-connect-mongodb-atlas-optional)
5. [Post-Deployment Manual Tasks](#5-post-deployment-manual-tasks)
6. [Troubleshooting](#6-troubleshooting)

---

## 1. Prerequisites

### Accounts (Sign Up — All Free)
| Service | Sign Up URL | What For |
|---------|------------|----------|
| **Render** | https://render.com | Host backend API server |
| **Vercel** | https://vercel.com | Host frontend static files |
| **MongoDB Atlas** | https://www.mongodb.com/atlas | Database (512MB free) |
| **GitHub** | https://github.com | Source code & auto-deploy |

### Local Tools
```bash
git --version         # Should be 2.30+
node --version        # Should be 18+ (for Vercel CLI, optional)
```

### Local Repo Setup
```bash
# Make sure your code is in a GitHub repo
cd ai_scanner
git init
git add .
git commit -m "Initial commit"
# Create a repo on GitHub.com (no README, no .gitignore)
git remote add origin https://github.com/YOUR_USERNAME/ai-scanner.git
git branch -M main
git push -u origin main
```

---

## 2. Deploy Backend on Render (Free)

### Step 2.1 — Create Render Account
1. Go to https://render.com
2. Sign up with **GitHub** (recommended)
3. Verify email

### Step 2.2 — Deploy as Web Service
1. Click **"New +"** → **"Web Service"**
2. **Connect repo**: Select `ai-scanner` (or your repo name)
3. Configure:
   - **Name**: `ai-scanner-api`
   - **Region**: `Oregon` (or closest to you)
   - **Branch**: `main`
   - **Runtime**: `Docker`
   - **Plan**: **Free**
4. Click **"Create Web Service"**

Render will:
- Detect `ai_scanner/Dockerfile` automatically
- Build the Docker image (3–5 min)
- Deploy to `https://ai-scanner-api.onrender.com`

### Step 2.3 — Set Environment Variables
After first deploy, go to **Dashboard → ai-scanner-api → Environment** and add:

| Key | Value | Required? |
|-----|-------|-----------|
| `PORT` | `8000` | Yes |
| `APP_ENV` | `production` | Yes |
| `APP_DEBUG` | `False` | Yes |
| `DATA_DIR` | `/app/data` | Yes |

**API Keys** (only if using cloud features):
| Key | Value |
|-----|-------|
| `GOOGLE_DRIVE_CLIENT_ID` | From Google Cloud Console |
| `GOOGLE_DRIVE_CLIENT_SECRET` | From Google Cloud Console |
| `GOOGLE_VISION_API_KEY` | From Google Cloud Console |
| `DROPBOX_APP_KEY` | From Dropbox Dev Console |
| `DROPBOX_APP_SECRET` | From Dropbox Dev Console |
| `DROPBOX_ACCESS_TOKEN` | From Dropbox Dev Console |
| `ONEDRIVE_CLIENT_ID` | From Azure App Registration |
| `ONEDRIVE_CLIENT_SECRET` | From Azure App Registration |
| `ONEDRIVE_TENANT_ID` | From Azure App Registration |

> **Note**: If you don't set API keys, OCR falls back to **Tesseract** (already installed in the Docker image). Cloud sync features will show as "not configured".

### Step 2.4 — Verify Backend
Once deployed, visit:
```
https://ai-scanner-api.onrender.com
```
You should see the AI Scanner dashboard. If it loads, the backend is live.

---

## 3. Deploy Frontend on Vercel (Free)

### Step 3.1 — Prepare for Vercel (Skip if using Render for both)
The AI Scanner already serves its own frontend via Flask templates. **Vercel is not required** — the frontend is served by Render.

**If you want to split frontend/backend:**

Create `ai_scanner/vercel.json`:
```json
{
  "buildCommand": "echo 'Static frontend ready'",
  "outputDirectory": "."
}
```

### Step 3.2 — Deploy
1. Go to https://vercel.com/new
2. Import your GitHub repo
3. Configure:
   - **Framework Preset**: `Other`
   - **Root Directory**: `ai_scanner`
   - **Build Command**: `(leave empty)`
   - **Output Directory**: `.`
4. Click **"Deploy"**

### Step 3.3 — Configure API URL
In the frontend JavaScript, update the API base URL to point to Render:
```js
// In src/templates/index.html, find:
const API_BASE = window.location.origin;

// Change to (for split deployment):
const API_BASE = "https://ai-scanner-api.onrender.com";
```

> If you keep everything on Render, this step is **not needed**.

---

## 4. Connect MongoDB Atlas (Optional)

The AI Scanner currently uses **local file storage** (JSON metadata + images on disk). To persist across deploys, you have two options:

### Option A: Use Render's Disk (Simpler)
1. Go to **Render Dashboard → ai-scanner-api → Disks**
2. Click **"Add Disk"**
3. **Name**: `ai-scanner-data`
4. **Mount Path**: `/app/data`
5. **Size**: 1 GB (free)
6. Click **"Save"**

This persists all scans even when the service restarts.

### Option B: MongoDB Atlas (For Cloud DB)
1. Go to https://www.mongodb.com/atlas → **"Try Free"**
2. Create a **Shared Cluster** (M0 — free, 512MB)
3. Set up:
   - **Username** + **Password** (save these)
   - **IP Whitelist**: `0.0.0.0/0` (allow all — or Render's IP)
4. Click **"Connect"** → **"Connect your application"**
5. Copy the connection string:
   ```
   mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/ai_scanner?retryWrites=true&w=majority
   ```
6. Add to Render environment:
   - Key: `MONGODB_URI`
   - Value: *(your connection string)*

> **Note**: The app currently does not use MongoDB by default. To enable it, you'd need to add `pymongo` to `requirements.txt` and modify `local_storage.py` to store metadata in MongoDB. This is an enhancement, not a blocker.

---

## 5. Post-Deployment Manual Tasks

### 5.1 — Push Code to GitHub
```bash
git add .
git commit -m "Add Dockerfile, Render/Railway configs"
git push
```
Render auto-deploys on every push to `main`.

### 5.2 — Test on Phone
1. Open the Render URL on your phone:
   ```
   https://ai-scanner-api.onrender.com
   ```
2. Go to **Scanner** view
3. Click the camera icon to use your phone camera (requires HTTPS — Render provides this)
4. Take a photo of a document → it auto-processes

### 5.3 — Set Up Custom Domain (Optional)
1. Go to **Render Dashboard → ai-scanner-api → Settings → Custom Domain**
2. Add your domain (e.g., `scanner.yourdomain.com`)
3. Update DNS records as instructed

### 5.4 — Replace Default Credentials (If using cloud APIs)
- Go to **Settings → API Keys** in the app
- Add your Google Drive / Dropbox / OneDrive / OCR credentials
- These get saved to encrypted local storage

---

## 6. Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| **Backend won't deploy** | Docker build fails | Check Render build logs. Ensure `requirements.txt` is up to date. |
| **"Cannot read image"** | OpenCV missing deps | Dockerfile includes `libgl1-mesa-glx`, `libglib2.0-0` — verify they're installed. |
| **OCR returns no text** | Tesseract not installed | Dockerfile installs `tesseract-ocr`. Run `which tesseract` in Render shell. |
| **App slow on free plan** | Render free tier spins down after 15 min of inactivity | First request after idle takes ~30s to wake up. Upgrade to paid plan for always-on. |
| **Camera not working on phone** | HTTP blocks camera access | Render provides HTTPS by default. Check URL starts with `https://`. |
| **Uploads lost after restart** | No persistent disk | Add Render Disk (Option A in Section 4) or switch to cloud storage. |
| **Need more workers** | Free plan limits | Upgrade to Render Starter ($7/mo) for more CPU/RAM. |

---

## Quick Reference

### URLs After Deployment
| Service | URL |
|---------|-----|
| **App (Dashboard)** | `https://ai-scanner-api.onrender.com` |
| **Scan API** | `POST https://ai-scanner-api.onrender.com/scan` |
| **History** | `GET https://ai-scanner-api.onrender.com/history` |
| **Admin (Settings)** | `https://ai-scanner-api.onrender.com` → Config tab |

### File Structure (for Deployment)
```
ai_scanner/
├── Dockerfile          ← Container build instructions
├── .dockerignore       ← Files to exclude from Docker build
├── render.yaml         ← Render auto-deploy config
├── railway.json        ← Railway auto-deploy config
├── startup.sh          ← Server start script (uses $PORT)
├── src/
│   └── web_app.py      ← Flask app entry point
└── requirements.txt    ← Python dependencies
```

### Estimated Free Tier Limits
| Service | Limit | Resets |
|---------|-------|--------|
| **Render** | 750 hours/month | Monthly |
| **Vercel** | 100 GB bandwidth | Monthly |
| **MongoDB Atlas** | 512 MB storage | Never |
| **Render Disk** | 1 GB | One-time |

---

## What Users See

After deployment, users simply open the URL on any device:

```
https://ai-scanner-api.onrender.com
```

- **Phone**: Full responsive UI, camera works via HTTPS
- **Tablet**: Same experience, larger preview area
- **Desktop**: Full HUD with dashboard, gallery, and advanced settings

No app store, no install — just a browser.
