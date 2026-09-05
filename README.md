# AI Scanner

> AI-powered document scanner with edge detection, enhancement, OCR, classification, and cloud sync.
> Access from **any device** (phone, tablet, desktop) via web browser.

**Rating:** 5.0 | **Duration:** 2–3 Months | **Stack:** Python, OpenCV, PyTorch, Tesseract, Google Cloud Vision, Google Drive / Dropbox / OneDrive APIs

- **Live Demo:** *(after deploy)* `https://ai-scanner.onrender.com` — see [Deployment Guide](DEPLOYMENT_GUIDE.md)
- **App Code:** lives in [`ai_scanner/`](ai_scanner/) — Dockerfile, `src/`, `requirements.txt` are inside there
- **Deploy Source:** Root Directory **must be `ai_scanner`** on Render / Railway / Coolify (else "Dockerfile not found")

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](ai_scanner/requirements.txt)
[![Flask](https://img.shields.io/badge/Flask-monolith-black)](ai_scanner/src/web_app.py)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED)](ai_scanner/Dockerfile)
[![Tests 73 passed](https://img.shields.io/badge/tests-73%20passed-brightgreen)](ai_scanner/tests/)

---

## Features

- **Document Capture** — Upload or snap from phone camera, auto-detects edges, corrects perspective
- **Enhancement** — Auto-contrast, sharpening, shadow removal, dewarping, multi-shot fusion
- **OCR** — Tesseract + Google Cloud Vision + EasyOCR (handwriting)
- **Auto-Naming** — Names files from content (e `Invoice_AcmeCorp_March15.pdf`)
- **Cloud Sync** — Google Drive, Dropbox, OneDrive (OAuth)
- **QR / Barcode** — `pyzbar` detection
- **Search** — Full-text search + vault filters
- **Camera** — Live view on HTTPS; native camera fallback on HTTP — works everywhere

### AI Assistant — Local · Free · No API Keys

Open-source assistant that never leaves your machine:

- Summarize any scan, ask questions ("what's the total?"), extract key facts
- Grounded in your real vault — never invents files
- Provider chain: **Ollama → Groq (free cloud) → Transformers (`flan-t5-small`) → Built-in**

| Engine | Requirement |
|---|---|
| Ollama | `ollama pull llama3.2` — best quality, fully local |
| Groq | Free `GROQ_API_KEY` — ideal for hosted deploys |
| Transformers | auto-downloads `google/flan-t5-small` (~300 MB) |
| Built-in | always available — rule-based |

> Full AI docs: [`ai_scanner/README.md`](ai_scanner/README.md) § AI Assistant

---

## Project Structure

```
repo root (this folder)          ← GitHub shows THIS README
├── ai_scanner/                  ← *** APP ROOT — set as Root Directory on deploy ***
│   ├── src/
│   │   ├── web_app.py           # Flask monolith (UI + API)
│   │   ├── ai_assistant/        # Ollama / Groq / Transformers / Builtin
│   │   ├── storage/             # LocalStorage + cloud_sync
│   │   ├── ocr/ classification/ edge_detection/ enhancement/ camera/
│   │   ├── templates/ static/   # Served by Flask (no separate frontend)
│   │   └── main.py              # Scanner pipeline
│   ├── Dockerfile               # Python 3.11 + Tesseract + zbar
│   ├── render.yaml  railway.json  startup.sh
│   ├── requirements.txt  .env.example
│   ├── tests/  (73 tests)
│   └── README.md                # Detailed app docs (run, API, env vars)
├── DEPLOYMENT_GUIDE.md          # Step-by-step: Render / Railway / Coolify
├── DEPLOY_STEPS.txt             # Checklist (tick-boxes)
├── PROJECT_STRUCTURE.txt
├── AGENTS.md                    # Agent memory — read before every session
└── end_of_day_report_*.txt
```

**Monolith:** `Browser ─HTTPS─> Flask + Gunicorn (ONE container)` — serves HTML *and* JSON. No Vercel/Netlify split.

---

## Quick Start (Local)

```powershell
# 1. Clone
git clone https://github.com/OPBSUTHAR/ai-scanner.git
cd ai-scanner

# 2. Venv + deps (Windows)
python -m venv ai_scanner\.venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\ai_scanner\.venv\Scripts\Activate.ps1
pip install -r ai_scanner/requirements.txt
pip install -r ai_scanner/requirements-dev.txt  # for tests

# Linux/Mac
# python3 -m venv ai_scanner/.venv && source ai_scanner/.venv/bin/activate
# pip install -r ai_scanner/requirements.txt

# 3. Env (optional — scanner works without keys)
copy ai_scanner\.env.example ai_scanner\.env   # fill keys if using cloud sync

# 4. Run
python -m src.web_app          # from ai_scanner/ dir
# or: python -m ai_scanner.src.web_app  (from repo root)
# -> http://localhost:5000  (login → Scanner → Vault)

# 5. Tests
pytest ai_scanner/tests/ -v    # 73 tests
```

**Tesseract:** required for OCR. Windows installer auto-detected; Docker/Linux handled by Dockerfile. QR needs `libzbar0` (Docker) / `zbar-tools` (Mac).

> Detailed prerequisites, env vars, and camera notes: [`ai_scanner/README.md`](ai_scanner/README.md)

---

## Deployment — One Container

| Option | Cost | Notes |
|---|---|---|
| **Render (free)** | $0 | Docker, HTTPS, sleeps after 15 min idle — best for demo |
| **Railway** | ~$5/mo | Always-on, no sleep |
| **Coolify on VPS** | ~$4.5/mo or free (Oracle) | Open-source, persistent disk |

**Critical:** On every platform set **Root Directory = `ai_scanner`** — Dockerfile lives inside that subfolder.

Full steps: **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** and **[DEPLOY_STEPS.txt](DEPLOY_STEPS.txt)**

Quick checklist:
- [ ] `APP_ENV=production`, `APP_DEBUG=False`, `DATA_DIR=/app/data`
- [ ] Free tier: `GUNICORN_WORKERS=1`, `DISABLE_EASYOCR=1`, `AI_DISABLE_TRANSFORMERS=1`, `MAX_SCAN_DIM=2000`
- [ ] Healthcheck `GET /` → 302 to `/login` or 200
- [ ] Optional: `GROQ_API_KEY` for hosted AI quality

---

## API (excerpt)

| Endpoint | Purpose |
|---|---|
| `GET /` `GET /login` | UI |
| `POST /scan` `POST /scan/advanced` `POST /scan/fusion` | Scan pipeline |
| `POST /api/batch/process` `POST /api/batch/done` | Batch (preview → Done) |
| `GET /history` `GET /search?q=` `GET /stats` | Vault |
| `GET /api/ocr/status` `GET /api/ai/status` `POST /api/ai/chat` | Health + AI |
| `GET /documents/<path>` | File serve |

Full list: [`ai_scanner/README.md`](ai_scanner/README.md) § Quick Reference + [`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md)

---

## Security

- Secrets: `ai_scanner/.env`, `credentials*.json`, `tokens/` — **gitignored** (never commit)
- Root `.gitignore` mirrors `ai_scanner/.gitignore` + `data/` / `AGENTS.md` history
- See [`.gitignore`](.gitignore) and [`ai_scanner/.gitignore`](ai_scanner/.gitignore)

## License

MIT

---

**Maintained at:** https://github.com/OPBSUTHAR/ai-scanner — `main` branch auto-deploys on Render/Railway. Keep `README.md` (root) and `ai_scanner/README.md` in sync after feature changes.
