# AI Scanner

> AI-powered document scanner with edge detection, enhancement, OCR, classification, and cloud sync.

**Rating:** 5.0  
**Duration:** 2–3 Months  
**Tech Stack:** Python, OpenCV, PyTorch, Tesseract, Google Cloud Vision, Google Drive API, Dropbox API, OneDrive API

---

## Features

- **Document Capture** — Auto-detects document edges, corrects perspective
- **Enhancement** — Auto-contrast, sharpening, shadow removal, dewarping
- **OCR** — Extracts text via Tesseract + Google Cloud Vision
- **Auto-Naming** — Names files based on content (e.g. `Invoice_AcmeCorp_March15.pdf`)
- **Cloud Sync** — Auto-uploads to Google Drive, Dropbox, OneDrive
- **Multi-Page** — Scans multiple pages into a single document
- **QR / Barcode Detection** — Extracts information from codes
- **Search** — Full-text search within scanned documents

### AI Features

- Document type classification (invoice, receipt, ID, contract)
- Content extraction (amounts, dates, names)
- Quality assessment (blur detection, lighting check)
- Auto-crop and perspective correction

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
│   ├── storage/             # Cloud sync + local storage
│   │   ├── cloud_sync.py
│   │   └── local_storage.py
│   ├── utils/               # Auto-naming, QR detection, search
│   └── main.py              # Entry point
├── tests/                   # Unit tests
├── config/                  # Configuration
├── data/                    # Working directory (gitignored)
├── .env                     # API keys & secrets (gitignored)
├── .gitignore
├── requirements.txt
├── log_file.txt             # Auto-generated timestamped logs
├── diary_log.txt            # Development diary (auto-generated)
└── README.md
```

---

## Pipeline

```
Camera → Edge Detection → Enhancement → OCR → Classification → Storage
```

### Edge Cases Handled

| Edge Case | Solution |
|---|---|
| Curved pages | Dewarping algorithm |
| Glare on glossy documents | Multi-shot fusion |
| Handwritten text | Handwriting OCR model (EasyOCR) |

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

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env .env
# Fill in your API keys in .env
```

### API Keys Required

| Service | File | Variables |
|---|---|---|
| Google Drive | `.env` | `GOOGLE_DRIVE_CLIENT_ID`, `GOOGLE_DRIVE_CLIENT_SECRET` |
| Google Cloud Vision | `.env` | `GOOGLE_VISION_API_KEY` or `GOOGLE_APPLICATION_CREDENTIALS` |
| Dropbox | `.env` | `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET`, `DROPBOX_ACCESS_TOKEN` |
| OneDrive | `.env` | `ONEDRIVE_CLIENT_ID`, `ONEDRIVE_CLIENT_SECRET`, `ONEDRIVE_TENANT_ID` |

### Usage

```bash
python src/main.py
```

---

## Development Log

Two files track progress automatically:

- **`log_file.txt`** — Timestamped one-liners (use `update_log()`)
- **`diary_log.txt`** — Detailed diary entries (use `update_diary()`)

Run `python generate_project.py` to append a new entry whenever you make changes.

---

## Security

- All API keys and secrets are stored in `.env` (gitignored)
- Never commit `.env` or `*.json` service account files
- See `.gitignore` for the full exclusion list

---

## License

MIT
