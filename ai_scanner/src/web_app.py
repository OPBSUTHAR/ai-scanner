import os, sys, json, mimetypes, shutil, re, socket
from pathlib import Path
from datetime import datetime
from io import BytesIO

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import (
    Flask, request, jsonify, render_template,
    send_file, url_for, Response
)
import cv2
import numpy as np
from PIL import Image

from src.main import AIScanner
from src.storage.local_storage import LocalStorage
from src.utils.search import DocumentSearch
from src.utils.key_manager import KeyManager

CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "app_config.json"

def _load_app_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            return {}
    return {}

def _save_app_config(data):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024

scanner = AIScanner()
searcher = DocumentSearch()
key_manager = KeyManager()

# Load saved storage path
_app_config = _load_app_config()
_saved_storage = _app_config.get("storage_path", "")
if _saved_storage:
    p = Path(_saved_storage).resolve()
    scanner.storage.base_dir = p
    scanner.storage._ensure_dirs()

UPLOAD_FOLDER = scanner.storage.base_dir / "uploads"
DOCUMENTS_FOLDER = scanner.storage.base_dir / "documents"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)


def _sync_keys_to_env():
    for name, value in key_manager.get_all().items():
        os.environ[name.upper()] = value


_sync_keys_to_env()

# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _to_bool(v):
    return bool(v)

def _fmt_size(b):
    if b < 1024: return f"{b} B"
    if b < 1024**2: return f"{b/1024:.1f} KB"
    return f"{b/(1024**2):.1f} MB"

def _serialize_result(r):
    out = {
        "quality": {
            "blur_score": round(float(r["quality"]["blur_score"]), 1),
            "brightness": round(float(r["quality"]["brightness"]), 1),
            "good_lighting": _to_bool(r["quality"].get("good_lighting", False)),
            "quality_pass": _to_bool(r["quality"].get("quality_pass", False)),
            "is_blurry": _to_bool(r["quality"].get("is_blurry", False)),
        },
        "document_detected": _to_bool(r.get("document_detected", False)),
        "enhanced": _to_bool(r.get("enhanced", False)),
        "ocr": {
            "text": r["ocr"]["text"],
            "confidence": round(float(r["ocr"]["confidence"]), 3),
        },
        "classification": {
            "type": r.get("classification", {}).get("type", "Unknown"),
            "confidence": round(float(r.get("classification", {}).get("confidence", 0)), 3),
            "extracted_data": r.get("classification", {}).get("extracted_data", {}),
        },
        "qr_codes": r.get("qr_codes", []),
        "filename": r.get("filename", ""),
        "saved_path": r.get("saved_path", ""),
        "original_shape": r.get("original_shape", []),
        "warning": r.get("warning"),
    }
    saved = r.get("saved_path", "")
    if saved:
        rel = os.path.relpath(saved, str(DOCUMENTS_FOLDER))
        out["image_url"] = url_for("serve_image", subpath=rel.replace("\\", "/"))
        if os.path.exists(saved):
            out["file_size"] = _fmt_size(os.path.getsize(saved))
    if "_orig_url" in r:
        out["original_url"] = r["_orig_url"]
    shape = r.get("original_shape", [])
    if len(shape) >= 2:
        out["dimensions"] = f"{shape[1]} \u00d7 {shape[0]} px"
    out["ocr_length"] = len(r["ocr"]["text"])
    return out

def _doc_info(fpath):
    rel = os.path.relpath(fpath, str(DOCUMENTS_FOLDER))
    mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M")
    return {
        "name": fpath.name,
        "path": rel.replace("\\", "/"),
        "size": _fmt_size(os.path.getsize(fpath)),
        "date": mtime,
        "folder": fpath.parent.name,
        "image_url": url_for("serve_image", subpath=rel.replace("\\", "/")),
    }

# ---------------------------------------------------------------------------
#  API Key Management
# ---------------------------------------------------------------------------

KEY_META = {
    "google_drive_client_id": {"label": "Google Drive Client ID", "service": "google_drive"},
    "google_drive_client_secret": {"label": "Google Drive Client Secret", "service": "google_drive", "secret": True},
    "dropbox_app_key": {"label": "Dropbox App Key", "service": "dropbox"},
    "dropbox_app_secret": {"label": "Dropbox App Secret", "service": "dropbox", "secret": True},
    "dropbox_access_token": {"label": "Dropbox Access Token", "service": "dropbox", "secret": True},
    "onedrive_client_id": {"label": "OneDrive Client ID", "service": "onedrive"},
    "onedrive_client_secret": {"label": "OneDrive Client Secret", "service": "onedrive", "secret": True},
    "onedrive_tenant_id": {"label": "OneDrive Tenant ID", "service": "onedrive", "secret": True},
    "google_vision_api_key": {"label": "Google Vision API Key", "service": "google_vision", "secret": True},
    "google_application_credentials": {"label": "Google Service Account JSON (full path or raw JSON)", "service": "google_vision", "secret": True},
    "ocr_space_api_key": {"label": "OCR.space API Key (free)", "service": "ocr", "secret": True},
    "ocr_api_key": {"label": "OCR API Key (ocr-api.com)", "service": "ocr", "secret": True},
    "azure_vision_key": {"label": "Azure Vision API Key", "service": "ocr", "secret": True},
    "azure_vision_endpoint": {"label": "Azure Vision Endpoint", "service": "ocr"},
}


@app.route("/api/keys", methods=["GET"])
def api_list_keys():
    stored = key_manager.list_keys()
    result = []
    for name, meta in KEY_META.items():
        entry = {
            "name": name,
            "label": meta["label"],
            "service": meta["service"],
            "configured": name in stored,
            "masked_value": stored.get(name, None),
        }
        result.append(entry)
    return jsonify(result)


@app.route("/api/keys", methods=["POST"])
def api_save_key():
    data = request.json or {}
    name = data.get("name", "").strip()
    value = data.get("value", "").strip()
    if not name or not value:
        return jsonify({"error": "Name and value required"}), 400
    if name not in KEY_META:
        return jsonify({"error": f"Unknown key: {name}"}), 400
    key_manager.set_key(name, value)
    _sync_keys_to_env()
    return jsonify({"saved": True, "name": name})


@app.route("/api/keys/<name>", methods=["DELETE"])
def api_delete_key(name):
    if name not in KEY_META:
        return jsonify({"error": f"Unknown key: {name}"}), 400
    key_manager.delete_key(name)
    _sync_keys_to_env()
    return jsonify({"deleted": True, "name": name})


# ---------------------------------------------------------------------------
#  Routes
# ---------------------------------------------------------------------------

@app.route("/api/storage/path", methods=["GET", "POST"])
def api_storage_path():
    if request.method == "POST":
        data = request.json or {}
        path = data.get("path", "").strip()
        if not path:
            return jsonify({"error": "Path required"}), 400
        path_obj = Path(path).resolve()
        config = _load_app_config()
        config["storage_path"] = str(path_obj)
        _save_app_config(config)
        scanner.storage.base_dir = path_obj
        scanner.storage._ensure_dirs()
        global UPLOAD_FOLDER, DOCUMENTS_FOLDER
        UPLOAD_FOLDER = path_obj / "uploads"
        DOCUMENTS_FOLDER = path_obj / "documents"
        UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
        return jsonify({"saved": True, "path": str(path_obj)})
    config = _load_app_config()
    saved = config.get("storage_path", "")
    if saved:
        return jsonify({"path": saved, "current": str(scanner.storage.base_dir / "documents")})
    return jsonify({"path": str(scanner.storage.base_dir / "documents"), "default": True})


@app.route("/api/cloud/usage")
def api_cloud_usage():
    usage = scanner.cloud.get_usage_stats()
    cleaned = {k: v for k, v in usage.items() if v is not None}
    return jsonify(cleaned)


@app.route("/api/ip")
def api_ip():
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    port = request.host.split(":")[1] if ":" in request.host else "80"
    return jsonify({"ip": local_ip, "hostname": hostname, "port": port, "url": f"http://{local_ip}:{port}"})

@app.route("/api/ocr/status")
def api_ocr_status():
    has_tesseract = scanner.ocr.tesseract_available
    has_google_vision = bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or
                             os.environ.get("GOOGLE_VISION_API_KEY"))
    return jsonify({
        "tesseract": has_tesseract,
        "google_vision": has_google_vision,
        "engine": "tesseract" if has_tesseract else ("google_vision" if has_google_vision else "none"),
    })

@app.route("/")
def index():
    data = {"stats": {}, "recent": []}
    if DOCUMENTS_FOLDER.exists():
        allf = [f for f in DOCUMENTS_FOLDER.rglob("*") if f.is_file()]
        data["stats"] = {
            "total": len(allf),
            "types": len(set(f.parent.name for f in allf)),
            "total_size": _fmt_size(sum(os.path.getsize(f) for f in allf)),
        }
        recent = sorted(allf, key=os.path.getmtime, reverse=True)[:6]
        data["recent"] = [_doc_info(f) for f in recent]
    return render_template("index.html", **data)


@app.route("/scan", methods=["POST"])
def scan():
    if "image" not in request.files:
        return jsonify({"error": "No image"}), 400
    file = request.files["image"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    save_path = UPLOAD_FOLDER / f"upload_{ts}.{ext}"
    file.save(str(save_path))

    orig_path = UPLOAD_FOLDER / f"orig_{ts}.{ext}"
    try:
        shutil.copy2(str(save_path), str(orig_path))
    except Exception:
        orig_path = save_path

    auto = request.form.get("auto", "true") == "true"
    if not auto:
        result = scanner.capture_and_process(image_path=str(save_path))
    else:
        img = cv2.imread(str(save_path))
        if img is None:
            return jsonify({"error": "Cannot read image"}), 500
        corners = scanner.edges.find_document_contour(img)
        if corners is not None:
            img = scanner.edges.perspective_correct(img, corners)
        img = scanner.enhancer.enhance_document(img)
        ocr_res = scanner.ocr.extract_text(img)
        text = ocr_res.text
        conf = ocr_res.confidence
        cls = scanner.classifier.classify(text) if text else None
        qrs = scanner.qr.detect(img)
        fname = scanner.namer.generate_name(
            cls.doc_type if cls else "document",
            cls.extracted_data if cls else {},
            text
        )
        fpath = scanner.storage.save_document(img, fname, cls.doc_type if cls else "document", {
            "ocr_text": text, "ocr_confidence": conf,
            "doc_type": cls.doc_type if cls else "document",
            "extracted_data": cls.extracted_data if cls else {},
            "quality": scanner.enhancer.quality_assessment(img),
        })
        result = {
            "original_shape": img.shape,
            "quality": scanner.enhancer.quality_assessment(img),
            "document_detected": corners is not None,
            "enhanced": True,
            "ocr": {"text": text, "confidence": conf},
            "classification": {
                "type": cls.doc_type if cls else "unknown",
                "confidence": cls.confidence if cls else 0,
                "extracted_data": cls.extracted_data if cls else {},
            },
            "qr_codes": [{"data": q.data, "type": q.type} for q in qrs] if qrs else [],
            "filename": fname,
            "saved_path": str(fpath),
        }

    if "error" in result:
        return jsonify({"error": result["error"]}), 500
    result["_orig_url"] = url_for("serve_image", subpath=f"orig_{ts}.{ext}")
    return jsonify(_serialize_result(result))


@app.route("/scan/advanced", methods=["POST"])
def scan_advanced():
    if "image" not in request.files:
        return jsonify({"error": "No image"}), 400
    file = request.files["image"]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    save_path = UPLOAD_FOLDER / f"upload_{ts}.{ext}"
    file.save(str(save_path))
    img = cv2.imread(str(save_path))
    if img is None:
        return jsonify({"error": "Cannot read image"}), 500

    auto_crop = request.form.get("auto_crop", "true") == "true"
    shadow_removal = request.form.get("shadow_removal", "true") == "true"
    enhance = request.form.get("enhance", "true") == "true"
    effect = request.form.get("effect", "none")
    use_google_vision = request.form.get("use_google_vision", "false") == "true"

    edges = scanner.edges
    enhancer = scanner.enhancer

    result = {"original_shape": img.shape}

    if auto_crop:
        corners = edges.find_document_contour(img)
        if corners is not None:
            result["document_detected"] = True
            img = edges.perspective_correct(img, corners)
        else:
            result["document_detected"] = False
    else:
        result["document_detected"] = False

    if shadow_removal and hasattr(enhancer, 'remove_shadows'):
        try:
            img = enhancer.remove_shadows(img)
        except Exception:
            pass

    if enhance:
        img = enhancer.enhance_document(img)

    if effect == "grayscale":
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif effect == "binarize":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, img = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif effect == "sharpen":
        k = np.array([[0,-1,0],[-1,5,-1],[0,-1,0]])
        img = cv2.filter2D(img, -1, k)
    elif effect == "invert":
        img = cv2.bitwise_not(img)

    quality = enhancer.quality_assessment(img)
    result["quality"] = quality
    result["enhanced"] = enhance or effect != "none"

    orig_path = UPLOAD_FOLDER / f"orig_{ts}.{ext}"
    shutil.copy2(str(save_path), str(orig_path))
    result["_orig_url"] = url_for("serve_image", subpath=f"orig_{ts}.{ext}")

    if use_google_vision:
        scanner.ocr.use_google_vision = True
    ocr_res = scanner.ocr.extract_text(img)
    scanner.ocr.use_google_vision = False
    text = ocr_res.text
    conf = ocr_res.confidence
    result["ocr"] = {"text": text, "confidence": conf}

    if text:
        cls = scanner.classifier.classify(text)
        result["classification"] = {
            "type": cls.doc_type, "confidence": cls.confidence,
            "extracted_data": cls.extracted_data,
        }
        qrs = scanner.qr.detect(img)
        result["qr_codes"] = [{"data": q.data, "type": q.type} for q in qrs] if qrs else []
        fname = scanner.namer.generate_name(cls.doc_type, cls.extracted_data, text)
    else:
        result["classification"] = {"type": "unknown", "confidence": 0, "extracted_data": {}}
        result["qr_codes"] = []
        fname = f"document_{ts}"

    result["filename"] = fname
    fpath = scanner.storage.save_document(img, fname, result["classification"]["type"], {
        "ocr_text": text, "ocr_confidence": conf,
        "doc_type": result["classification"]["type"],
        "extracted_data": result["classification"]["extracted_data"],
        "quality": quality,
    })
    result["saved_path"] = str(fpath)
    return jsonify(_serialize_result(result))


@app.route("/effects/preview", methods=["POST"])
def effects_preview():
    if "image" not in request.files:
        return jsonify({"error": "No image"}), 400
    file = request.files["image"]
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    nparr = np.frombuffer(file.read(), np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return jsonify({"error": "Bad image"}), 400

    effect = request.form.get("effect", "none")
    shadow_removal = request.form.get("shadow_removal", "false") == "true"
    auto_crop = request.form.get("auto_crop", "false") == "true"

    if auto_crop:
        corners = scanner.edges.find_document_contour(img)
        if corners is not None:
            img = scanner.edges.perspective_correct(img, corners)

    if shadow_removal and hasattr(scanner.enhancer, 'remove_shadows'):
        try:
            img = scanner.enhancer.remove_shadows(img)
        except Exception:
            pass

    if effect == "grayscale":
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif effect == "binarize":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, img = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif effect == "sharpen":
        k = np.array([[0,-1,0],[-1,5,-1],[0,-1,0]])
        img = cv2.filter2D(img, -1, k)
    elif effect == "invert":
        img = cv2.bitwise_not(img)
    elif effect == "enhance":
        img = scanner.enhancer.enhance_document(img)

    _, buf = cv2.imencode(f".{ext}", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return Response(buf.tobytes(), mimetype=f"image/{ext}")


# ---------------------------------------------------------------------------
#  AI Auto-Detect (for AI auto-capture mode)
# ---------------------------------------------------------------------------

@app.route("/api/auto-detect", methods=["POST"])
def api_auto_detect():
    file = request.files.get("image")
    if not file:
        return jsonify({"error": "No image"}), 400
    img_array = np.frombuffer(file.read(), np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    if img is None:
        return jsonify({"error": "Invalid image"}), 400

    h, w = img.shape[:2]
    corners = scanner.edges.find_document_contour(img)
    quality = scanner.enhancer.quality_assessment(img)

    result = {
        "document_detected": corners is not None,
        "quality_pass": bool(quality.get("quality_pass", False)),
        "blur_score": round(float(quality.get("blur_score", 0)), 2),
        "brightness": round(float(quality.get("brightness", 0)), 2),
        "good_lighting": bool(quality.get("good_lighting", False)),
        "width": w,
        "height": h,
    }

    if corners is not None:
        area = cv2.contourArea(corners)
        frame_area = w * h
        result["fill_ratio"] = round(float(area / frame_area), 3)

    return jsonify(result)


@app.route("/history")
def history():
    docs = []
    if DOCUMENTS_FOLDER.exists():
        for f in sorted(DOCUMENTS_FOLDER.rglob("*"), key=os.path.getmtime, reverse=True)[:100]:
            if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".pdf"):
                docs.append(_doc_info(f))
    return jsonify(docs)


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    results = []
    if DOCUMENTS_FOLDER.exists():
        ocr_dir = scanner.storage.base_dir / "metadata"
        for f in DOCUMENTS_FOLDER.rglob("*"):
            if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg"):
                meta_path = ocr_dir / f"{f.stem}.json"
                text = ""
                if meta_path.exists():
                    try:
                        meta = json.loads(meta_path.read_text())
                        text = meta.get("ocr_text", "")
                    except Exception:
                        pass
                if q.lower() in text.lower() or q.lower() in f.stem.lower() or q.lower() in f.parent.name.lower():
                    results.append(_doc_info(f))
        results = sorted(results, key=lambda x: x["date"], reverse=True)[:30]
    return jsonify(results)


@app.route("/stats")
def stats():
    total, total_size = 0, 0
    type_counts = {}
    if DOCUMENTS_FOLDER.exists():
        for f in DOCUMENTS_FOLDER.rglob("*"):
            if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".pdf"):
                total += 1
                total_size += os.path.getsize(f)
                p = f.parent.name
                type_counts[p] = type_counts.get(p, 0) + 1
    return jsonify({
        "total": total,
        "total_size": _fmt_size(total_size),
        "type_counts": type_counts,
        "types": len(type_counts),
    })


@app.route("/pdf/merge", methods=["POST"])
def pdf_merge():
    paths = request.json.get("paths", [])
    if not paths:
        return jsonify({"error": "No paths provided"}), 400

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Image as RLImage, Spacer, PageBreak
        from reportlab.lib.units import inch
    except ImportError:
        return jsonify({"error": "reportlab not installed. Run: pip install reportlab"}), 500

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_name = f"merged_{ts}.pdf"
    out_path = scanner.storage.base_dir / "documents" / "merged" / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(str(out_path), pagesize=letter,
                            topMargin=0.5*inch, bottomMargin=0.5*inch,
                            leftMargin=0.5*inch, rightMargin=0.5*inch)
    elements = []
    for i, p in enumerate(paths):
        full = DOCUMENTS_FOLDER / p
        if full.exists() and full.suffix.lower() in (".png", ".jpg", ".jpeg"):
            try:
                from PIL import Image as PILImage
                with PILImage.open(str(full)) as pil_img:
                    w, h = pil_img.size
                aspect = h / w
                dw = 7 * inch
                dh = dw * aspect
                if dh > 9.5 * inch:
                    dh = 9.5 * inch
                    dw = dh / aspect
                img = RLImage(str(full), width=dw, height=dh)
                elements.append(img)
                if i < len(paths) - 1:
                    elements.append(PageBreak())
            except Exception:
                pass
    doc.build(elements)

    rel = os.path.relpath(str(out_path), str(DOCUMENTS_FOLDER))
    return jsonify({
        "url": url_for("serve_image", subpath=rel.replace("\\", "/")),
        "name": out_name,
        "size": _fmt_size(os.path.getsize(out_path)),
    })


@app.route("/documents/<path:subpath>", methods=["DELETE"])
def delete_doc(subpath):
    full = DOCUMENTS_FOLDER / subpath
    if full.exists() and full.is_file():
        full.unlink()
        meta = scanner.storage.base_dir / "metadata" / f"{full.stem}.json"
        if meta.exists():
            meta.unlink()
        return jsonify({"deleted": True})
    return jsonify({"error": "Not found"}), 404


@app.route("/documents/<path:subpath>/info")
def doc_info_route(subpath):
    full = DOCUMENTS_FOLDER / subpath
    if not full.exists():
        return jsonify({"error": "Not found"}), 404
    info = _doc_info(full)
    meta_path = scanner.storage.base_dir / "metadata" / f"{full.stem}.json"
    if meta_path.exists():
        try:
            info["metadata"] = json.loads(meta_path.read_text())
        except Exception:
            info["metadata"] = {}
    return jsonify(info)


@app.route("/activity")
def activity():
    entries = []
    if DOCUMENTS_FOLDER.exists():
        for f in sorted(DOCUMENTS_FOLDER.rglob("*"), key=os.path.getmtime, reverse=True)[:20]:
            if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".pdf"):
                mtime = datetime.fromtimestamp(os.path.getmtime(f))
                ago = _time_ago(mtime)
                action = "Scanned" if f.suffix.lower() != ".pdf" else "Merged into PDF"
                entries.append({
                    "action": action,
                    "file": f.name,
                    "folder": f.parent.name,
                    "time": ago,
                    "timestamp": mtime.strftime("%H:%M"),
                })
    return jsonify(entries)

def _time_ago(dt):
    diff = datetime.now() - dt
    if diff.days > 0: return f"{diff.days}d ago"
    if diff.seconds >= 3600: return f"{diff.seconds//3600}h ago"
    if diff.seconds >= 60: return f"{diff.seconds//60}m ago"
    return "Just now"

@app.route("/documents/<path:subpath>/rename", methods=["POST"])
def rename_doc(subpath):
    data = request.json or {}
    new_name = data.get("name", "")
    if not new_name:
        return jsonify({"error": "No name provided"}), 400
    full = DOCUMENTS_FOLDER / subpath
    if not full.exists():
        return jsonify({"error": "Not found"}), 404
    new_path = full.parent / new_name
    full.rename(new_path)
    meta_old = scanner.storage.base_dir / "metadata" / f"{full.stem}.json"
    meta_new = scanner.storage.base_dir / "metadata" / f"{new_path.stem}.json"
    if meta_old.exists():
        shutil.move(str(meta_old), str(meta_new))
    return jsonify({"renamed": True, "new_path": str(new_path)})


@app.route("/images/<path:subpath>")
def serve_image(subpath):
    full_path = DOCUMENTS_FOLDER / subpath
    if not full_path.exists():
        full_path = UPLOAD_FOLDER / subpath
    if not full_path.exists():
        return "Not found", 404
    mime = mimetypes.guess_type(str(full_path))[0]
    if mime:
        return send_file(str(full_path), mimetype=mime)
    return send_file(str(full_path))


# ---------------------------------------------------------------------------
#  Cloud Sync
# ---------------------------------------------------------------------------

@app.route("/cloud/status")
def cloud_status():
    return jsonify({"providers": scanner.cloud.status()})


@app.route("/cloud/auth/<provider>")
def cloud_auth(provider):
    redirect_uri = request.args.get("redirect_uri", request.host_url.rstrip("/") + "/cloud/callback/" + provider)
    auth_url = None
    if provider == "google_drive":
        auth_url = scanner.cloud.get_google_drive_auth_url(redirect_uri)
    elif provider == "dropbox":
        auth_url = scanner.cloud.get_dropbox_auth_url(redirect_uri)
    elif provider == "onedrive":
        auth_url = scanner.cloud.get_onedrive_auth_url(redirect_uri)

    if auth_url:
        return jsonify({"auth_url": auth_url})
    return jsonify({"error": "Provider not configured or not supported"}), 400


@app.route("/cloud/callback/<provider>")
def cloud_callback(provider):
    auth_code = request.args.get("code", "")
    if not auth_code:
        return jsonify({"error": "No auth code"}), 400

    success = False
    if provider == "google_drive":
        redirect_uri = request.host_url.rstrip("/") + "/cloud/callback/google_drive"
        success = scanner.cloud.handle_google_drive_callback(auth_code, redirect_uri)
    elif provider == "dropbox":
        success = scanner.cloud.handle_dropbox_callback(auth_code)
    elif provider == "onedrive":
        success = scanner.cloud.handle_onedrive_callback(auth_code)

    if success:
        return "", 200
    return jsonify({"error": "Auth failed"}), 400


@app.route("/cloud/connect/<provider>", methods=["POST"])
def cloud_connect(provider):
    if provider == "dropbox":
        token = (request.json or {}).get("access_token", "")
        if token:
            os.environ["DROPBOX_ACCESS_TOKEN"] = token
    success = scanner.cloud.setup_dropbox() if provider == "dropbox" else False
    if success:
        return jsonify({"connected": True})
    return jsonify({"error": "Connection failed"}), 400


@app.route("/cloud/disconnect/<provider>", methods=["POST"])
def cloud_disconnect(provider):
    if provider == "google_drive":
        scanner.cloud.drive_service = None
    elif provider == "dropbox":
        scanner.cloud.dropbox_client = None
    elif provider == "onedrive":
        scanner.cloud.onedrive_client = None
        scanner.cloud.onedrive_token = None
    return jsonify({"disconnected": True})


@app.route("/cloud/upload/<path:subpath>", methods=["POST"])
def cloud_upload(subpath):
    full = DOCUMENTS_FOLDER / subpath
    if not full.exists() or not full.is_file():
        return jsonify({"error": "Document not found"}), 404

    providers = (request.json or {}).get("providers", ["google_drive", "dropbox", "onedrive"])
    filename = request.json.get("filename") if request.json else None
    results = scanner.cloud.upload_to_providers(str(full), providers, filename)
    return jsonify({"results": results})


# ---------------------------------------------------------------------------
#  Entry Point
# ---------------------------------------------------------------------------

def main():
    import argparse, socket as _socket
    parser = argparse.ArgumentParser(description="AI Scanner Web Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5000)))
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--ngrok", action="store_true", help="Expose via ngrok (requires ngrok installed)")
    args = parser.parse_args()
    local_ip = _socket.gethostbyname(_socket.gethostname())
    print(f"\n  {'='*45}")
    print(f"  ◈ AI SCANNER // NEXUS-OS v3.0")
    print(f"  {'='*45}")
    print(f"  Local:   http://localhost:{args.port}")
    print(f"  Network: http://{local_ip}:{args.port}")
    print(f"  {'='*45}")
    print(f"  {'='*45}\n")
    if args.ngrok:
        try:
            from pyngrok import ngrok as _ngrok
            public_url = _ngrok.connect(args.port).public_url
            print(f"  🌐 ngrok URL: {public_url}")
            print(f"  Share this URL to access from anywhere\n")
        except ImportError:
            print(f"  ⚠ ngrok requested but pyngrok not installed.")
            print(f"  Install: pip install pyngrok\n")
    app.run(host=args.host, port=args.port, debug=args.debug)

if __name__ == "__main__":
    main()
