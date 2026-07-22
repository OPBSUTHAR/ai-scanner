# AI Scanner — Project Status & Roadmap

## What Has Been Done (Fixed)

### Storage Fix
- Fixed `LocalStorage.__init__` default base_dir to resolve relative to `src/storage/local_storage.py`, not `os.getcwd()`. This prevents the orphaned `data/` folder outside `ai_scanner/`.
- Deleted the orphaned root `data/` folder that was created due to the CWD bug.

### UI Rewrite (Classic Archive Theme)
- Complete CSS rewrite: cream/parchment palette with burgundy, gold, and emerald accents.
- Font stack: Playfair Display (headings), Lora (body), JetBrains Mono (code), Cormorant Garamond (classic).
- Sidebar: leather-book styling with gold gradient border animation.
- Top bar: gilded edge with telemetry, clock, search.
- Cards, buttons, modals, stats, gallery — all restyled to antique archive aesthetic.

### Bug Fixes (This Session)

| # | Bug | Fix |
|---|-----|-----|
| 1 | Captured images not stored | LocalStorage path fixed (previous session) |
| 2 | Process Scan button stayed disabled after camera capture | `addFilmstripThumb()` now enables `#btn-process` and `#btn-process-captures` on every capture |
| 3 | No retake/delete per captured image | Filmstrip thumbnails now have a ✕ delete button per image |
| 4 | Merge PDF not working | Sidebar Merge button now switches to gallery first; backend endpoint verified working |
| 5 | "Done" button instead of filmstrip gallery | Replaced with horizontal thumbnail filmstrip showing all captures |
| 6 | Images saved zoomed/corner | Removed `||1280`/`||720` fallback dimensions; added `if(!v.videoWidth)return` guard |
| 7 | No capture animation/sound | Added `shutterSound()` (Web Audio API — noise burst + sine ring) |
| 8 | No edge detection animation | Corner brackets now pulse green and grow during steady-state detection, flash on capture |

---

## Features That Work Out of the Box (No Configuration Needed)

- Document upload (file picker + drag-and-drop)
- Camera capture (browser getUserMedia or native `<input capture>` fallback)
- Edge detection + perspective correction (auto-crop)
- Image enhancement: shadow removal, CLAHE contrast, sharpen
- Effects: grayscale, binarize (Otsu), sharpen, invert
- Quality assessment: blur (Laplacian variance), brightness/lighting
- **Tesseract OCR** — Tesseract v5.5.0 is installed at `C:\Program Files\Tesseract-OCR\tesseract.exe`
- Document classification (keyword/regex: invoice, receipt, ID, contract)
- Content extraction (amounts, dates, names/merchants via regex)
- Auto-naming (`Invoice_AcmeCorp_Mar15_$150.00`)
- QR / barcode detection (pyzbar + OpenCV QRCodeDetector)
- Local storage + metadata JSON (`data/documents/{type}/{filename}`)
- Full-text search across OCR text
- PDF merge (reportlab)
- Multi-page capture (sequential camera captures → Process All)
- Dashboard with stats, recent scans, activity feed
- Gallery/Vault with filters, preview, rename, delete
- Settings: storage path, API key management (encrypted)

---

## Features That Need User Configuration (API Keys)

| Feature | Keys Required | Where to Get |
|---------|---------------|--------------|
| Google Cloud Vision OCR | `google_vision_api_key` | GCP Console → APIs & Services → Credentials |
| Google Drive Sync | `google_drive_client_id` + `google_drive_client_secret` | GCP Console → OAuth consent screen → Credentials |
| Dropbox Sync | `dropbox_app_key` + `dropbox_app_secret` (+ access token) | Dropbox Developer Console |
| OneDrive Sync | `onedrive_client_id` + `onedrive_client_secret` + `onedrive_tenant_id` | Azure Portal → App Registrations |

**How to configure:** Open the app → Settings → scroll to API Keys → click "Add Key" → select service + paste key.

---

## Features That Are Incomplete or Not Wired

| Feature | Status | What's Missing |
|---------|--------|----------------|
| EasyOCR Handwriting | Backend exists, **not connected** | `use_handwriting=true` is never passed; add toggle in UI ctrl-panel |
| OCR.space / OCR API / Azure Vision | UI key entry only, **no backend** | No implementation in `web_app.py` or `ocr/` |
| Multi-shot fusion (glare reduction) | Backend complete, **not connected** | No endpoint calls `enhancer.multi_shot_fusion()` |
| Dewarping (curved pages) | Backend complete, **not connected** | No endpoint calls `EdgeDetector.dewarp()` |
| Cloud usage stats | Backend complete, **not auto-displayed** | Only shown on demand via "Check Cloud Usage" button |
| Token persistence | **Partial** | `_save_token()` writes to disk but `_load_token()` is missing — tokens lost on restart |
| Tests | **Empty** | All `tests/*.py` files are zero bytes |

---

## Steps to Implement Remaining Features

### 1. Wire EasyOCR Handwriting Toggle
- Edit `src/templates/index.html` — add a toggle in the ctrl-panel (e.g., "Handwriting OCR" toggle)
- Edit `src/web_app.py` `/scan/advanced` — pass `use_handwriting` from the form data
- Note: EasyOCR is slow on CPU; consider adding a loading indicator

### 2. Wire Dewarp + Multi-Shot Fusion
- Add toggles in `index.html` ctrl-panel (e.g., "Dewarp", "Anti-Glare")
- In `/scan/advanced`, call `scanner.edges.detect()` → if dewarp toggle on, call `scanner.edges.dewarp()` before crop
- For multi-shot, create a new endpoint or modify existing to accept multiple images and call `enhancer.multi_shot_fusion()`

### 3. Implement Missing Cloud OCR Backends (Optional)
- Create `src/ocr/ocrspace.py`, `src/ocr/ocrapi.py`, `src/ocr/azure_vision.py`
- Each should expose a function matching the `extract_text(image, api_key)` signature
- Wire into `ocr_service.py` or `web_app.py` switch-case

### 4. Fix Token Persistence
- Edit `src/cloud/cloud_sync.py` — add `_load_token(provider)` method
- Call it in `_get_authenticated_service()` before creating a new OAuth flow

### 5. Write Tests
- `tests/test_scanner.py` — test `process_file()` with sample images
- `tests/test_ocr.py` — test `extract_text()` with known images
- `tests/test_enhancement.py` — test enhancement pipeline
- `tests/test_classification.py` — test keyword/regex classification
- `tests/test_endpoints.py` — test Flask endpoints via `app.test_client()`

### 6. Remove Unused Dependencies (Optional)
- `torch`, `transformers` — ~2GB, never imported
- Comment out or remove from `requirements.txt` if not needed

---

## How to Run

```bash
cd ai_scanner
pip install -r requirements.txt
python -m src.web_app
```

Then open http://localhost:5000

Camera requires HTTPS on mobile. For testing with phone over LAN:

```bash
pip install pyngrok
python -m src.web_app --ngrok
```

Or deploy with `gunicorn src.web_app:app` on a VPS with HTTPS.

---

## Project Architecture

```
ai_scanner/
├── src/
│   ├── web_app.py              # Flask backend (all endpoints)
│   ├── scanner/
│   │   ├── scanner.py          # AIScanner pipeline class
│   │   ├── edge_detector.py    # Edge detection + perspective correction
│   │   ├── qr_detector.py      # QR/barcode detection
│   ├── enhancement/
│   │   └── enhancer.py         # Shadow removal, contrast, sharpen, fusion
│   ├── ocr/
│   │   └── ocr_service.py      # Tesseract + Google Vision OCR
│   ├── classification/
│   │   └── classifier.py       # Keyword/regex document classifier
│   ├── cloud/
│   │   └── cloud_sync.py       # Google Drive, Dropbox, OneDrive sync
│   ├── utils/
│   │   ├── auto_naming.py      # Content-based file naming
│   │   └── search.py           # Full-text search
│   ├── storage/
│   │   └── local_storage.py    # Local file + metadata persistence
│   ├── templates/
│   │   └── index.html          # Single-page frontend (2568 lines)
│   └── main.py                 # CLI entry point
├── tests/                      # All empty (zero bytes)
├── requirements.txt
└── DEPLOYMENT_GUIDE.md
```
