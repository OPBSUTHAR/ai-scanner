import os
import datetime
import json

PROJECT_NAME = "ai_scanner"
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), PROJECT_NAME)

STRUCTURE = {
    "src": {
        "__init__.py": "",
        "camera": {
            "__init__.py": "",
            "capture.py": "# Camera module for document capture\n# Handles camera access, frame capture, auto-detection\n"
        },
        "edge_detection": {
            "__init__.py": "",
            "detector.py": "# Edge detection module\n# Auto-detects document edges, perspective correction\n"
        },
        "enhancement": {
            "__init__.py": "",
            "enhancer.py": "# Image enhancement module\n# Auto-contrast, sharpening, shadow removal, dewarping\n"
        },
        "ocr": {
            "__init__.py": "",
            "ocr_engine.py": "# OCR module\n# Extracts text from scanned documents\n"
        },
        "classification": {
            "__init__.py": "",
            "classifier.py": "# Document classification module\n# Classifies: invoice, receipt, ID, contract\n"
        },
        "storage": {
            "__init__.py": "",
            "cloud_sync.py": "# Cloud sync module\n# Google Drive, Dropbox, OneDrive integration\n",
            "local_storage.py": "# Local storage module\n# Auto-naming, folder organization\n"
        },
        "utils": {
            "__init__.py": "",
            "auto_naming.py": "# Auto-naming utility\n# Names files based on content analysis\n",
            "qr_detection.py": "# QR/Barcode detection module\n",
            "search.py": "# Search module\n# Searches text within scanned documents\n"
        },
        "main.py": "# Main entry point\n# Orchestrates: Camera -> Edge Detection -> Enhancement -> OCR -> Classification -> Storage\n\ndef main():\n    print(\"AI Scanner starting...\")\n\nif __name__ == \"__main__\":\n    main()\n"
    },
    "tests": {
        "__init__.py": "",
        "test_camera.py": "",
        "test_edge_detection.py": "",
        "test_enhancement.py": "",
        "test_ocr.py": "",
        "test_classification.py": "",
        "test_storage.py": ""
    },
    "config": {
        "__init__.py": "",
        "settings.py": "# Configuration settings\n# API keys, paths, model parameters\n\nCONFIG = {\n    \"ocr_engine\": \"tesseract\",\n    \"cloud_providers\": [\"google_drive\", \"dropbox\", \"onedrive\"],\n    \"supported_formats\": [\"pdf\", \"png\", \"jpg\", \"tiff\"],\n    \"auto_naming\": True,\n    \"quality_threshold\": 0.7\n}\n"
    },
    "data": {
        ".gitkeep": ""
    }
}

REQUIREMENTS = """# Core
opencv-python>=4.8.0
numpy>=1.24.0
Pillow>=10.0.0

# Camera & Image Processing
scikit-image>=0.21.0
scipy>=1.10.0

# OCR
pytesseract>=0.3.10
google-cloud-vision>=3.4.0

# Machine Learning
torch>=2.0.0
transformers>=4.30.0
easyocr>=1.7.0

# Cloud Storage
google-api-python-client>=2.95.0
google-auth-httplib2>=0.1.0
google-auth-oauthlib>=1.0.0
dropbox>=11.36.0
msal>=1.22.0
requests>=2.31.0

# QR/Barcode
pyzbar>=0.1.9
opencv-contrib-python>=4.8.0

# PDF Generation
reportlab>=4.0.0
img2pdf>=0.4.8

# Utilities
python-dotenv>=1.0.0
tqdm>=4.65.0
loguru>=0.7.0
"""

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def create_structure(base, structure):
    created = []
    for name, content in structure.items():
        path = os.path.join(base, name)
        if isinstance(content, dict):
            os.makedirs(path, exist_ok=True)
            created.append(f"[DIR]  {path}")
            created.extend(create_structure(path, content))
        else:
            write_file(path, content)
            created.append(f"[FILE] {path}")
    return created


def update_log(message):
    log_path = os.path.join(BASE_DIR, "log_file.txt")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {message}\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)
    return entry


def update_diary(message):
    diary_path = os.path.join(BASE_DIR, "diary_log.txt")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"=== {timestamp} ===\n{message}\n\n"
    with open(diary_path, "a", encoding="utf-8") as f:
        f.write(entry)
    return entry


def generate():
    print(f"Creating project structure at: {BASE_DIR}")

    results = create_structure(BASE_DIR, STRUCTURE)
    for r in results:
        print(f"  {r}")

    req_path = os.path.join(BASE_DIR, "requirements.txt")
    write_file(req_path, REQUIREMENTS)
    print(f"  [FILE] {req_path}")

    log_entry = update_log("Project structure generated successfully")
    print(f"  [LOG]  {log_entry.strip()}")

    diary_entry = update_diary(
        "Initialized AI Scanner project.\n"
        "Created project structure with modules:\n"
        "  - Camera, Edge Detection, Enhancement, OCR,\n"
        "  - Classification, Storage, Utils, Tests, Config\n"
        f"Requirements written to requirements.txt\n"
        f"Total files created: {len(results) + 1}"
    )
    print(f"  [DIARY] Added entry to diary_log.txt")

    print(f"\nProject generated successfully at: {BASE_DIR}")
    print("Run this script again to update logs after making changes.")


if __name__ == "__main__":
    generate()
