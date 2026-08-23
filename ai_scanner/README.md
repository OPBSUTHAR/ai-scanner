# AI Scanner

> AI-powered document scanner with edge detection, enhancement, OCR, classification, and cloud sync.
> Access from **any device** (phone, tablet, desktop) via web browser.

**Rating:** 5.0  
**Duration:** 2–3 Months  
**Tech Stack:** Python, OpenCV, PyTorch, Tesseract, Google Cloud Vision, Google Drive API, Dropbox API, OneDrive API

---

## Features

- **Document Capture** — Upload or snap from phone camera, auto-detects edges, corrects perspective
- **Enhancement** — Auto-contrast, sharpening, shadow removal, dewarping
- **OCR** — Extracts text via Tesseract + Google Cloud Vision
- **Auto-Naming** — Names files based on content (e.g. `Invoice_AcmeCorp_March15.pdf`)
- **Cloud Sync** — Auto-uploads to Google Drive, Dropbox, OneDrive
- **QR / Barcode Detection** — Extracts information from codes
- **Search** — Full-text search within scanned documents

### AI Features

- Document type classification (invoice, receipt, ID, contract)
- Content extraction (amounts, dates, names)
- Quality assessment (blur detection, lighting check)
- Auto-crop and perspective correction

### AI Assistant (Local · Free · No API Keys)

Built-in assistant powered by **open-source models that never leave your machine**:

- **Summarize** any scanned document (invoices → key amounts/dates in seconds)
- **Ask questions** about document content ("what's the total?", "who's the vendor?")
- **Key-fact extraction** (amounts, dates, emails, phone numbers)
- **Chat help** for app features (merging PDFs, cloud sync, OCR engines...)
- Available everywhere: sidebar **AI Assistant** view, **AI SUMMARY / ASK AI** buttons
  in every document inspector, and an **Ask AI** button on scan results

Provider chain — first available wins, zero configuration required:

| Engine | Requirement | Notes |
|---|---|---|
| Ollama | Install [Ollama](https://ollama.com) + `ollama pull llama3.2` | Full LLM chat quality |
| Transformers | `pip install transformers` | Auto-downloads `google/flan-t5-small` (~300 MB) once, then offline |
| Built-in helper | Nothing — always available | Rule-based summaries, fact extraction & app guidance |

All three are 100% free, open-source, and require **no API keys and no internet**
(after the one-time model download).

---

## Project Structure

```
ai_scanner/
├── src/
│   ├── camera/              # Camera access & capture
│   ├── edge_detection/      # Edge detection & perspective correction
│   ├── enhancement/         # Image enhancement (contrast, sharpening, shadow removal)
│   ├── ocr/                 # OCR engine (Tesseract, Google Vision)
│   ├── classification/      # Document type classifier
│   │   ├── ai_assistant/    # Local AI assistant (Ollama + flan-t5 + builtin)
│   ├── storage/             # Cloud sync + local storage
│   │   ├── cloud_sync.py
│   │   └── local_storage.py
│   ├── utils/               # Auto-naming, QR detection, search
│   ├── templates/           # Web UI templates
│   ├── web_app.py           # Flask web server
│   └── main.py              # Core scanner pipeline
├── tests/                   # Unit tests
├── config/                  # Configuration
├── data/                    # Working directory (gitignored)
├── .env                     # API keys & secrets (gitignored)
├── .gitignore
├── requirements.txt
├── startup.sh               # Azure App Service startup script
├── log_file.txt             # Auto-generated timestamped logs
├── diary_log.txt            # Development diary (auto-generated)
└── README.md
```

---

## Pipeline

```
Upload/Camera → Edge Detection → Enhancement → OCR → Classification → Storage
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- Tesseract OCR ([install guide](https://github.com/tesseract-ocr/tesseract))
- Git

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd ai_scanner

# Create virtual environment (isolated from your system Python)
python -m venv .venv

# Activate it
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt   # optional: pytest for running tests

# Set up environment variables (template tracked in repo)
cp .env.example .env    # Windows: copy .env.example .env
# Fill in your API keys in .env
```

### Running Tests

```bash
pytest tests/
```

### System Dependencies

- **Tesseract OCR** required for text extraction ([install guide](https://github.com/tesseract-ocr/tesseract)). The app auto-detects the binary on Windows/Linux/Mac.
- **Windows**: install Tesseract from the official installer; path is auto-detected.
- **Docker/Linux**: handled by the Dockerfile (installs tesseract + libzbar0).
- QR/barcode decoding uses `pyzbar`, which needs the platform zbar library
  (`libzbar0` on Debian/Ubuntu, `zbar-tools` via Homebrew on Mac).

### API Keys Required

Only if using cloud features (optional — scanner works without them):

| Service | File | Variables |
|---|---|---|
| Google Drive | `.env` | `GOOGLE_DRIVE_CLIENT_ID`, `GOOGLE_DRIVE_CLIENT_SECRET` |
| Google Cloud Vision | `.env` | `GOOGLE_VISION_API_KEY` or `GOOGLE_APPLICATION_CREDENTIALS` |
| Dropbox | `.env` | `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET`, `DROPBOX_ACCESS_TOKEN` |
| OneDrive | `.env` | `ONEDRIVE_CLIENT_ID`, `ONEDRIVE_CLIENT_SECRET`, `ONEDRIVE_TENANT_ID` |

The **AI Assistant needs no keys at all** — see the AI Assistant section above.
Optional tuning in `.env`: `OLLAMA_HOST`, `OLLAMA_MODEL`, `AI_LOCAL_MODEL`.

### Usage

```bash
# Start the web server
python -m src.web_app

# Or double-click run.bat
```

Open `http://localhost:5000` in your browser.  
On your phone (same Wi-Fi), use `http://YOUR_PC_IP:5000`.

To deploy to Azure App Service:
```bash
gunicorn --bind=0.0.0.0:8000 src.web_app:app
```

---

## Development Log

Two files track progress automatically:

- **`log_file.txt`** — Timestamped one-liners
- **`diary_log.txt`** — Detailed diary entries

---

## Security

- All API keys and secrets are stored in `.env` (gitignored)
- Never commit `.env` or `*.json` service account files
- See `.gitignore` for the full exclusion list

---

## License

MIT
