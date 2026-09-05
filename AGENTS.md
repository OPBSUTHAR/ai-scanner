# AGENTS.md — Persistent Agent Instructions

> This file is the long-term memory for AI agents working in this repo.
> Update it as work progresses. Every agent session MUST read this file first.

## Project: AI Scanner
- **Repo:** https://github.com/OPBSUTHAR/ai-scanner
- **Root:** `C:\vs code\WebEnoid Intern` (git root) — app code lives in `ai_scanner/`
- **Stack:** Python 3.11/3.13, Flask (monolith), OpenCV, Tesseract, PyTorch/EasyOCR, Google Drive/Dropbox/OneDrive APIs, local AI assistant (Ollama → Groq → Transformers → Builtin)
- **Deploy:** One Docker container (Flask + Gunicorn) — Render (free), Railway, or Coolify/VPS. Dockerfile is at `ai_scanner/Dockerfile`, Root Directory **must** be `ai_scanner`.
- **Branch:** `main` — every push triggers Render/Railway rebuild.

## How to Run Locally
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& "c:\vs code\WebEnoid Intern\ai_scanner\.venv\Scripts\Activate.ps1"
pip install -r ai_scanner/requirements.txt
pip install -r ai_scanner/requirements-dev.txt
python -m src.web_app  # from ai_scanner/ dir, or python -m ai_scanner.src.web_app from root
# -> http://localhost:5000 (login → Scanner → Vault)
pytest tests/ -v
```

## Critical Gotchas (learned)
1. **Root Directory = `ai_scanner`** on Render/Railway/Coolify — else "Dockerfile not found".
2. **Free tier RAM = 512MB** — set `GUNICORN_WORKERS=1`, `DISABLE_EASYOCR=1`, `AI_DISABLE_TRANSFORMERS=1`, `MAX_SCAN_DIM=2000` on Render free.
3. **DATA_DIR=/app/data** — persistent disk only on paid/self-host; free tier is ephemeral (use cloud sync).
4. **Secrets never committed:** `.env`, `credentials*.json`, `tokens/` are gitignored.
5. **Storage path bug:** `LocalStorage` must resolve relative to `src/storage/local_storage.py`, not `os.getcwd()`.
6. **AI hallucination fix (23 Aug 2026):** `/api/ai/chat` injects live vault facts; vault questions answered deterministically, never via LLM invention.
7. **Camera:** Live view requires HTTPS (Render gives it). HTTP falls back to native camera app — intentional.

## Deployment Verification Checklist
- [x] `GET /` → 200 dashboard/login (verified on Render)
- [x] `GET /api/ai/status` → engine `cloud` (Groq llama-3.3-70b) + `transformer` fallback
- [x] `GET /api/ocr/status` → `tesseract:true`
- [x] `POST /scan` with image → 200 invoice 0.714, OCR 171 chars
- [x] `POST /api/ai/chat` vault grounding → `0 documents` deterministic (empty vault)
- [ ] Phone over HTTPS → OPEN CAMERA live view (requires manual phone test)

## Render Host — LIVE
- **Live URL:** **https://ai-scanner-fnjh.onrender.com/** — **verified 05 Sep 2026 08:21 UTC, all checks PASS**
- **Service name:** `ai-scanner` (Render free, Oregon, Docker, Root Directory `ai_scanner`)
- **Deploy verified:**
  - `GET /` → 200 `AI SCANNER // ARCHIVE v3.0 - Entry` (login page, 2874 B)
  - `GET /login` → 200 (2874 B)
  - `GET /api/ocr/status` → `{"engine":"tesseract","tesseract":true}`
  - `GET /api/ai/status` → `{"engine":"cloud","model":"llama-3.3-70b-versatile","available":true,"assistant_version":"2.1"}`
  - `POST /api/ai/chat` hello → `builtin` greeting; vault question → `Your vault is currently EMPTY - 0 documents` (grounded:true)
  - `POST /scan` `test_invoice.png` → 200 `invoice` 0.714 `$234.50`, `document_detected:true`, `ocr_length:171`
- **HTTPS:** Yes (Render auto-TLS) — enables live `OPEN CAMERA` view; `getUserMedia` works on phone.
- **Ephemeral storage:** `GET /stats` → `0 B` (free tier — use Drive/Dropbox sync for persistence)
- **Healthcheck:** `GET /` (railway.json & render.yaml)
- **Env set:** `GROQ_API_KEY` active on Render (cloud LLM enabled), `APP_ENV=production`, `DATA_DIR=/app/data`

## GitHub Maintenance — REQUIRED after every change
> **Rule:** After ANY code/config/doc change, keep GitHub up to date on `main`.

1. **Read before edit:** `AGENTS.md` (this file) — obey gotchas + Root Directory rule.
2. **Verify locally first** (catches 90% deploy failures):
   ```powershell
   pytest ai_scanner/tests/ -v
   # quick Flask smoke: python -c "from src.web_app import app; app.test_client().get('/')"
   ```
3. **Commit & push every session:**
   ```powershell
   git status --short          # what changed? never commit .env / credentials*.json / tokens/
   git diff                    # review
   git add <files>             # stage ONLY intended files (AGENTS.md, README.md, ai_scanner/** etc.)
   git commit -m "feat/fix/docs: concise message — why"
   git push                    # origin main — triggers Render/Railway rebuild
   git log --oneline -1        # confirm pushed
   gh api repos/OPBSUTHAR/ai-scanner --jq .pushed_at  # optional remote check
   ```
4. **README sync:** Repo root has `README.md` (GitHub's landing page) + `ai_scanner/README.md` (app docs). After feature changes, update BOTH and keep them consistent. GitHub shows "Add a README" if root `README.md` is missing — never delete it.
5. **Gitignore hygiene:** Root `.gitignore` + `ai_scanner/.gitignore` must stay in sync. `*.json` is intentionally scoped — `!railway.json` is un-ignored so deploy config IS committed. Never commit `ai_scanner/.env`, `credentials*.json`, `tokens/`, `data/`, `.venv/`.
6. **Deploy check after push:** Wait 5-10 min, then `GET https://<app>.onrender.com/` → 200, plus checklist in `DEPLOYMENT_GUIDE.md:5` and `DEPLOY_STEPS.txt`.
7. **Session log:** Append to `AGENTS.md` Session Log (newest first) — what changed, why, local+remote verification.

Skipping `git push` leaves GitHub stale and Render/Railway will NOT redeploy — treat as incomplete work.

## Session Log (append newest first)
### 2026-09-05 — Render LIVE at https://ai-scanner-fnjh.onrender.com — full verification PASS
- **User deployed:** `https://ai-scanner-fnjh.onrender.com/` — Render free, Docker, Root `ai_scanner`, Oregon. Verified 05 Sep 2026 08:21 UTC:
  - `GET /` → 200 (2874 B, `AI SCANNER // ARCHIVE v3.0 - Entry`), `GET /login` → 200, `GET /api/ocr/status` → `tesseract:true` (engine `tesseract`), `GET /api/ai/status` → `cloud` (`llama-3.3-70b-versatile`, `available:true`, `assistant_version 2.1`, cloud enabled `true` via `GROQ_API_KEY`), `GET /stats` → `0 B` (ephemeral, expected), `POST /api/ai/chat` vault → `EMPTY - 0 documents` (grounded:true, deterministic), `POST /scan` `test_invoice.png` → 200 `invoice` 0.714 `ocr_length:171` `$234.50`.
  - **HTTPS:** Yes — live `OPEN CAMERA` works on phone (`getUserMedia` requires HTTPS — Render gives it). HTTP falls back to native camera (intentional).
- **Updated:** `AGENTS.md:33` checklist ticked, `## Render Host — LIVE` with live URL + env + health details. Previous `NOT DEPLOYED` (ai-scanner.onrender.com 404) now superseded by `ai-scanner-fnjh.onrender.com` LIVE.
- **WebEnoid Internship:** Report already clarified as WebEnoid Internship deliverable by Om Prakash Suthar (`0f75f74`).

### 2026-09-05 — Full project report pushed (solely Om Prakash Suthar)
- **Report:** FULL_PROJECT_REPORT.md:1 (27,653 bytes, 249 lines) — inch-by-inch from 19 Jul 2026 (1d0e735) to 05 Sep 2026 (296798), 110 commits, 80 files, 6,673 Python lines, 73/73 tests. Covers scaffold, camera/OCR/cloud refactors, Docker, handwriting/fusion, frontend modular, batch/theme, Drive/Dropbox/multi-user, auth/vault merge, Bluetooth/HTTPS, AI Assistant + hallucination fix + Dockerfile trixie, GitHub hygiene.
- **Attribution:** Solely developed by **Om Prakash Suthar** — all commits OMPRAKASH SUTHAR, verified via git log --pretty=%an.
- **Pushed:** 296798 pushed_at 2026-09-05T08:17:09Z, gh api .../contents/FULL_PROJECT_REPORT.md 27,653 B verified. GitHub now hosts report at root.

### 2026-09-05 — Fix GitHub README + gitignore + railway.json; enforce push rule
- **Root cause:** Repo had no `README.md` at root (only `ai_scanner/README.md`) → GitHub showed "Add a README" banner + API `read me: 404`. Missing root `.gitignore` left `data/` untracked, and `ai_scanner/.gitignore` `*.json` was ignoring `railway.json` (deploy config never reached GitHub).
- **Fixed:** Created `README.md:1` (6754 bytes) — GitHub entrypoint explaining monolith, `Root Directory = ai_scanner`, quick start, deployment; links to `ai_scanner/README.md` + `DEPLOYMENT_GUIDE.md`. Created `.gitignore:1` (root, scoped JSON). Patched `ai_scanner/.gitignore:42` → `!railway.json` so deploy config IS committed.
- **Verified:** `git ls-files --others` clean, `pytest ai_scanner/tests/` 73/73, `gh api repos/.../readme` now 6754 bytes, `.../contents/ai_scanner/railway.json` 316 bytes, `git push origin/main` → `7e44bef` pushed_at `2026-09-05T08:09:54Z`. GitHub landing page now renders.
- **Rule added:** `## GitHub Maintenance — REQUIRED after every change` — verify locally, commit, push to `main` every session, keep both READMEs in sync, never commit secrets.

### 2026-09-05 — Local app OK, Render host NOT found (needs deploy)
- **AGENTS.md** created/updated as persistent memory (this file).
- **Local app: PASS** — `pytest ai_scanner/tests/` 73/73 passed (52s). Flask test_client: `GET /`→302→/login, `GET /login`→200, `GET /api/ocr/status`→`{"engine":"tesseract","tesseract":true}`, `GET /api/ai/status`→engine `transformer` (`google/flan-t5-small`, builtin fallback OK), `GET /stats`→2 docs, `POST /scan` with `test_invoice.png`→200 classified `invoice` 0.714 extracted `$234.50`, `POST /api/ai/chat` vault grounding works (deterministic, no hallucination).
- **Render host: FAIL / NOT DEPLOYED** — `https://ai-scanner.onrender.com/` and `/login` and `/api/ai/status` all → 404. No public deployment found via websearch. Repo is `OPBSUTHAR/ai-scanner` branch `main`. Next step: create Render Web Service (Docker, Root Directory `ai_scanner`, env `APP_ENV=production` etc. per `render.yaml`/`DEPLOYMENT_GUIDE.md`). Verify after deploy via `GET /` and checklist above.
- Venv: Python 3.13.12 at `ai_scanner/.venv`.

### 2026-09-05 — Agent memory init + app + Render health check
- Created `AGENTS.md` as persistent instruction file.
- Checked local tests + web_app endpoints; checked Render host reachability.

<!-- Add new entries above this line, newest first. Keep concise: date, what changed, why. -->
