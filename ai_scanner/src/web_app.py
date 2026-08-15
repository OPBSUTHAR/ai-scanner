import os, sys, json, mimetypes, shutil, re, socket, uuid, secrets, string, asyncio, time
from pathlib import Path
from datetime import datetime
from io import BytesIO
from typing import Optional, List, Dict, Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from flask import (
    Flask, request, jsonify, render_template,
    send_file, url_for, Response, redirect, make_response
)
import cv2
import numpy as np
from PIL import Image

from src.main import AIScanner
from src.storage.local_storage import LocalStorage
from src.utils.search import DocumentSearch
from src.utils.key_manager import KeyManager
from src.utils.doc_converter import is_office_file, convert_to_pdf, merge_pdfs
from src.camera.bluetooth_camera import (
    BluetoothCameraManager,
    BluetoothDevice,
    BluetoothCameraConfig,
    ConnectionState,
    generate_pairing_qr_code_base64,
    scan_bluetooth_cameras,
    BLEAK_AVAILABLE
)
from src.utils.bluetooth_qr import create_bluetooth_qr_for_device, create_url_qr_base64

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


@app.before_request
def _bind_cloud_user():
    user = request.cookies.get(SESSION_COOKIE, "").strip()
    scanner.cloud.activate_user(user or "default")

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
    try:
        from dotenv import dotenv_values
        env_file = dotenv_values(Path(__file__).resolve().parent.parent / ".env")
    except Exception:
        env_file = {}
    stored = key_manager.get_all()
    for name in KEY_META:
        env_name = name.upper()
        if name in stored:
            os.environ[env_name] = stored[name]
        elif env_file.get(env_name):
            os.environ[env_name] = env_file[env_name]
        else:
            os.environ.pop(env_name, None)


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
        "fusion": r.get("fusion", None),
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
        "kind": "pdf" if fpath.suffix.lower() == ".pdf" else "image",
        "image_url": url_for("serve_image", subpath=rel.replace("\\", "/")),
    }

# ---------------------------------------------------------------------------
#  API Key Management
# ---------------------------------------------------------------------------

KEY_META = {
    "google_drive_client_id": {"label": "Google Drive OAuth Client ID", "service": "google_drive"},
    "google_drive_client_secret": {"label": "Google Drive OAuth Secret (NOT an API key)", "service": "google_drive", "secret": True},
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

_sync_keys_to_env()


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

# ---------------------------------------------------------------------------
#  Quick Login / Register / Guest (preferred name, no password)
# ---------------------------------------------------------------------------

SESSION_COOKIE = "user_name"
AUTH_COOKIE = "user_mode"
SESSION_DAYS = 30
GUEST_PREFIX = "GUEST"
GUEST_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _gen_guest_id():
    # Unique random ID per user — placeholder identity until real auth exists.
    return f"{GUEST_PREFIX}-" + "".join(
        secrets.choice(GUEST_ALPHABET) for _ in range(8)
    )


@app.route("/login")
def login():
    if request.cookies.get(SESSION_COOKIE, "").strip():
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.json or {}
    name = re.sub(r"\s+", " ", data.get("name", "")).strip()
    if not name:
        return jsonify({"error": "Name required"}), 400
    name = name[:40]
    mode = "register" if data.get("mode") == "register" else "login"
    resp = make_response(jsonify({"ok": True, "name": name, "mode": mode}))
    resp.set_cookie(SESSION_COOKIE, name, max_age=SESSION_DAYS * 24 * 3600,
                    samesite="Lax")
    resp.set_cookie(AUTH_COOKIE, mode, max_age=SESSION_DAYS * 24 * 3600,
                    samesite="Lax")
    return resp


@app.route("/api/guest", methods=["POST"])
def api_guest():
    guest_id = _gen_guest_id()
    resp = make_response(jsonify({"ok": True, "name": guest_id, "mode": "guest"}))
    resp.set_cookie(SESSION_COOKIE, guest_id, max_age=SESSION_DAYS * 24 * 3600,
                    samesite="Lax")
    resp.set_cookie(AUTH_COOKIE, "guest", max_age=SESSION_DAYS * 24 * 3600,
                    samesite="Lax")
    return resp


@app.route("/api/session", methods=["GET"])
def api_session():
    return jsonify({
        "name": request.cookies.get(SESSION_COOKIE, ""),
        "mode": request.cookies.get(AUTH_COOKIE, ""),
    })


@app.route("/api/logout", methods=["POST"])
def api_logout():
    resp = make_response(jsonify({"ok": True}))
    resp.delete_cookie(SESSION_COOKIE)
    resp.delete_cookie(AUTH_COOKIE)
    return resp


PROFILE_DIR = scanner.storage.base_dir / "profiles"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)
AVATAR_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


@app.route("/api/profile/avatar", methods=["POST"])
def api_upload_avatar():
    name = request.cookies.get(SESSION_COOKIE, "").strip() or "default"
    if "avatar" not in request.files:
        return jsonify({"error": "No file"}), 400
    file = request.files["avatar"]
    if not file.filename:
        return jsonify({"error": "Empty file"}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in AVATAR_EXTS:
        ext = ".png"
    for old in PROFILE_DIR.glob(f"{_safe_name(name)}.*"):
        old.unlink(missing_ok=True)
    dest = PROFILE_DIR / f"{_safe_name(name)}{ext}"
    file.save(str(dest))
    return jsonify({"ok": True, "url": f"/api/profile/avatar?t={int(datetime.now().timestamp())}"})


@app.route("/api/profile/avatar")
def api_get_avatar():
    name = request.cookies.get(SESSION_COOKIE, "").strip() or "default"
    matches = sorted(PROFILE_DIR.glob(f"{_safe_name(name)}.*"))
    if not matches:
        return "No profile image", 404
    mime = mimetypes.guess_type(str(matches[0]))[0]
    return send_file(str(matches[0]), mimetype=mime or "application/octet-stream")


@app.route("/")
def index():
    if not request.cookies.get(SESSION_COOKIE, "").strip():
        return redirect(url_for("login"))
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
    use_handwriting = request.form.get("use_handwriting", "false") == "true"
    dewarp = request.form.get("dewarp", "false") == "true"

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

    if dewarp:
        img = edges.dewarp(img)

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
    ocr_res = scanner.ocr.extract_text(img, use_handwriting=use_handwriting)
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


@app.route("/scan/fusion", methods=["POST"])
def scan_fusion():
    files = request.files.getlist("images")
    if len(files) < 1:
        return jsonify({"error": "No images"}), 400

    frames = []
    for file in files:
        nparr = np.frombuffer(file.read(), np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is not None:
            frames.append(img)
    if not frames:
        return jsonify({"error": "Cannot read images"}), 500

    auto_crop = request.form.get("auto_crop", "true") == "true"
    dewarp = request.form.get("dewarp", "false") == "true"
    use_google_vision = request.form.get("use_google_vision", "false") == "true"
    use_handwriting = request.form.get("use_handwriting", "false") == "true"

    edges = scanner.edges
    enhancer = scanner.enhancer

    prepared = []
    detected_any = False
    for img in frames:
        if auto_crop:
            corners = edges.find_document_contour(img)
            if corners is not None:
                detected_any = True
                img = edges.perspective_correct(img, corners)
        if dewarp:
            img = edges.dewarp(img)
        prepared.append(img)

    fused = enhancer.multi_shot_fusion(prepared)
    fused = enhancer.enhance_document(fused)

    quality = enhancer.quality_assessment(fused)
    result = {
        "original_shape": fused.shape,
        "document_detected": detected_any,
        "enhanced": True,
        "quality": quality,
        "fusion": {"shots": len(frames)},
    }

    if use_google_vision:
        scanner.ocr.use_google_vision = True
    ocr_res = scanner.ocr.extract_text(fused, use_handwriting=use_handwriting)
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
        qrs = scanner.qr.detect(fused)
        result["qr_codes"] = [{"data": q.data, "type": q.type} for q in qrs] if qrs else []
        fname = scanner.namer.generate_name(cls.doc_type, cls.extracted_data, text)
    else:
        result["classification"] = {"type": "unknown", "confidence": 0, "extracted_data": {}}
        result["qr_codes"] = []
        fname = f"fused_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    orig_path = UPLOAD_FOLDER / f"orig_{ts}.jpg"
    _, buf = cv2.imencode(".jpg", frames[0], [cv2.IMWRITE_JPEG_QUALITY, 90])
    orig_path.write_bytes(buf.tobytes())
    result["_orig_url"] = url_for("serve_image", subpath=f"orig_{ts}.jpg")

    result["filename"] = fname
    fpath = scanner.storage.save_document(fused, fname, result["classification"]["type"], {
        "ocr_text": text, "ocr_confidence": conf,
        "doc_type": result["classification"]["type"],
        "extracted_data": result["classification"]["extracted_data"],
        "quality": quality,
        "fusion_shots": len(frames),
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
#  Batch Processing (multi-file upload / capture → preview → Done button)
# ---------------------------------------------------------------------------

BATCH_TEMP_DIR = scanner.storage.base_dir / "temp" / "batch"


def _cleanup_old_batches(max_age_hours=6):
    try:
        if BATCH_TEMP_DIR.exists():
            for p in BATCH_TEMP_DIR.iterdir():
                age = (datetime.now() - datetime.fromtimestamp(p.stat().st_mtime)).total_seconds()
                if age > max_age_hours * 3600:
                    shutil.rmtree(str(p), ignore_errors=True)
    except Exception:
        pass


def _apply_image_effect(img, effect):
    if effect == "grayscale":
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif effect == "binarize":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, img = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif effect == "sharpen":
        k = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        img = cv2.filter2D(img, -1, k)
    elif effect == "invert":
        img = cv2.bitwise_not(img)
    return img


@app.route("/api/batch/process", methods=["POST"])
def batch_process():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files received"}), 400

    _cleanup_old_batches()
    job_id = uuid.uuid4().hex[:12]
    job_dir = BATCH_TEMP_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    auto_crop = request.form.get("auto_crop", "true") == "true"
    shadow_removal = request.form.get("shadow_removal", "true") == "true"
    enhance = request.form.get("enhance", "true") == "true"
    effect = request.form.get("effect", "none")
    use_google_vision = request.form.get("use_google_vision", "false") == "true"
    use_handwriting = request.form.get("use_handwriting", "false") == "true"
    dewarp = request.form.get("dewarp", "false") == "true"

    items = []
    errors = []
    for i, f in enumerate(files):
        fname = f.filename or f"file_{i}"
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", Path(fname).name)[:80]
        ext = Path(fname).suffix.lower()
        item_key = f"item{i}"

        if ext and Path(fname).name.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".tif")):
            img = cv2.imdecode(np.frombuffer(f.read(), np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                errors.append(fname)
                continue
            if auto_crop:
                corners = scanner.edges.find_document_contour(img)
                if corners is not None:
                    img = scanner.edges.perspective_correct(img, corners)
            if dewarp:
                img = scanner.edges.dewarp(img)
            if shadow_removal and hasattr(scanner.enhancer, "remove_shadows"):
                try:
                    img = scanner.enhancer.remove_shadows(img)
                except Exception:
                    pass
            if enhance:
                img = scanner.enhancer.enhance_document(img)
            img = _apply_image_effect(img, effect)

            if use_google_vision:
                scanner.ocr.use_google_vision = True
            ocr_res = scanner.ocr.extract_text(img, use_handwriting=use_handwriting)
            scanner.ocr.use_google_vision = False
            text = ocr_res.text
            cls = scanner.classifier.classify(text) if text else None
            title = scanner.namer.generate_name(
                cls.doc_type if cls else "document",
                cls.extracted_data if cls else {},
                text
            ) if cls else f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            out_path = job_dir / f"{item_key}.png"
            out_meta = {
                "index": i, "original": fname, "kind": "image", "title": title,
                "doc_type": cls.doc_type if cls else "document",
                "conf": round(float(cls.confidence), 3) if cls else 0,
                "ocr_text": text,
                "ocr_confidence": round(conf, 3) if (conf := ocr_res.confidence) is not None else 0,
                "metadata": {
                    "ocr_text": text,
                    "doc_type": cls.doc_type if cls else "document",
                    "extracted_data": cls.extracted_data if cls else {},
                    "quality": scanner.enhancer.quality_assessment(img),
                },
            }
            if not cv2.imwrite(str(out_path), img):
                errors.append(fname)
                continue
            (job_dir / f"{item_key}.json").write_text(json.dumps(out_meta))
            items.append({
                "key": item_key, "kind": "image",
                "name": fname, "title": title,
                "url": url_for("serve_batch_temp", job_id=job_id, filename=f"{item_key}.png"),
            })
        elif is_office_file(fname):
            src_path = job_dir / ("src_" + item_key + "_" + safe)
            src_path.write_bytes(f.read())
            pdf_path = convert_to_pdf(str(src_path))
            if not pdf_path or not Path(pdf_path).exists():
                errors.append(fname)
                continue
            stem = Path(fname).stem or fname
            out_meta = {"index": i, "kind": "pdf", "title": stem,
                        "doc_type": "document", "pdf_src": Path(pdf_path).name}
            dest_pdf = job_dir / f"{item_key}.pdf"
            shutil.copy2(pdf_path, str(dest_pdf))
            (job_dir / f"{item_key}.json").write_text(json.dumps(out_meta))
            items.append({
                "key": item_key, "kind": "pdf",
                "name": fname, "title": stem,
                "url": f"/api/batch/temp/{job_id}/{item_key}.pdf",
            })
        else:
            errors.append(fname)

    return jsonify({"job_id": job_id, "items": items, "errors": errors})


def _safe_name(name):
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)[:60] or "doc"


def _resolve_within(base_dir: Path, subpath: str) -> Path:
    candidate = (base_dir / subpath).resolve()
    base_resolved = base_dir.resolve()
    if candidate != base_resolved and base_resolved not in candidate.parents:
        return None
    return candidate


@app.route("/api/batch/temp/<job_id>/<filename>")
def serve_batch_temp(job_id, filename):
    allowed = _resolve_within(BATCH_TEMP_DIR / job_id, filename)
    if not allowed or not allowed.exists() or not allowed.is_file():
        return "Not found", 404
    mime = mimetypes.guess_type(str(allowed))[0]
    return send_file(str(allowed), mimetype=mime or "application/octet-stream")


@app.route("/api/batch/done", methods=["POST"])
def batch_done():
    data = request.json or {}
    job_id = data.get("job_id", "")
    keys = data.get("keys", []) or []
    as_pdf = bool(data.get("as_pdf", False))
    if not job_id or not keys:
        return jsonify({"error": "job_id and keys required"}), 400
    job_dir = BATCH_TEMP_DIR / job_id
    if not job_dir.exists():
        return jsonify({"error": "Batch session expired — re-upload"}), 410

    saved = []
    images_for_pdf = []
    pdfs_for_pdf = []
    first_title = None
    first_doc_type = "document"

    for key in keys:
        meta_path = job_dir / f"{key}.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text())
        if first_title is None:
            first_title = meta.get("title") or f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            first_doc_type = meta.get("doc_type", "document")
        kind = meta.get("kind", "image")
        title = _safe_name(meta.get("title") or f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        doc_type = meta.get("doc_type", "document")
        if kind == "image":
            src = job_dir / f"{key}.png"
            if not src.exists():
                continue
            if not as_pdf:
                target = scanner.storage._type_folder(doc_type) / f"{title}.png"
                if target.exists():
                    title = f"{title}_{key}"
                fpath = scanner.storage.save_document(
                    cv2.imread(str(src)), title, doc_type, meta.get("metadata", {}))
                rel = os.path.relpath(fpath, str(DOCUMENTS_FOLDER)).replace("\\", "/")
                saved.append({"name": os.path.basename(fpath), "path": rel,
                              "url": url_for("serve_image", subpath=rel),
                              "kind": "image", "type": doc_type})
            else:
                images_for_pdf.append(str(src))
        elif kind == "pdf":
            src = job_dir / f"{key}.pdf"
            if src.exists():
                pdfs_for_pdf.append((key, str(src)))

    pdf_parts = []
    if images_for_pdf:
        import img2pdf
        tmp_pdf = job_dir / "_combined.pdf"
        tmp_pdf.write_bytes(img2pdf.convert(images_for_pdf))
        pdf_parts.append(str(tmp_pdf))
    pdf_parts.extend(p for _, p in sorted(pdfs_for_pdf))

    if as_pdf and pdf_parts:
        target_dir = DOCUMENTS_FOLDER / "documented"
        target_dir.mkdir(parents=True, exist_ok=True)
        out_pdf = target_dir / (_safe_name(first_title) + ".pdf")
        merged = merge_pdfs(pdf_parts, str(out_pdf)) if len(pdf_parts) > 1 else pdf_parts[0]
        if merged != str(out_pdf):
            shutil.copy2(merged, str(out_pdf))
        rel = os.path.relpath(str(out_pdf), str(DOCUMENTS_FOLDER)).replace("\\", "/")
        saved.append({"name": out_pdf.name, "path": rel,
                      "url": url_for("serve_image", subpath=rel),
                      "kind": "pdf", "type": "documented"})
    elif not as_pdf:
        for key, p in sorted(pdfs_for_pdf):
            meta_path = job_dir / f"{key}.json"
            if meta_path.exists():
                meta = json.loads(meta_path.read_text())
                title = _safe_name(meta.get("title") or f"doc_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            else:
                title = Path(p).stem
            target = DOCUMENTS_FOLDER / "documented" / f"{title}.pdf"
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target = target.with_name(f"{title}_{key}.pdf")
            shutil.copy2(p, str(target))
            rel = os.path.relpath(str(target), str(DOCUMENTS_FOLDER)).replace("\\", "/")
            saved.append({"name": target.name, "path": rel,
                          "url": url_for("serve_image", subpath=rel),
                          "kind": "pdf", "type": "documented"})

    shutil.rmtree(str(job_dir), ignore_errors=True)
    return jsonify({"done": True, "saved": saved,
                    "count": len(saved),
                    "pdf_name": next((s["name"] for s in saved if s["kind"] == "pdf"), None)})

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

    rel = os.path.relpath(str(out_path), str(DOCUMENTS_FOLDER)).replace("\\", "/")
    return jsonify({
        "url": url_for("serve_image", subpath=rel),
        "name": out_name,
        "path": rel,
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
    allowed = _resolve_within(DOCUMENTS_FOLDER, subpath)
    if not allowed or not allowed.exists():
        allowed = _resolve_within(UPLOAD_FOLDER, subpath)
    if not allowed or not allowed.exists():
        return "Not found", 404
    mime = mimetypes.guess_type(str(allowed))[0]
    if mime:
        return send_file(str(allowed), mimetype=mime)
    return send_file(str(allowed))


# ---------------------------------------------------------------------------
#  Cloud Sync
# ---------------------------------------------------------------------------

@app.route("/cloud/status")
def cloud_status():
    providers = scanner.cloud.status()
    usage = scanner.cloud.get_usage_stats()
    for prov in providers:
        if providers[prov]["connected"]:
            providers[prov]["usage"] = usage.get(prov) or "0 KB"
        else:
            providers[prov]["usage"] = None
    return jsonify({"providers": providers})


@app.route("/cloud/auth/<provider>")
def cloud_auth(provider):
    explicit = request.args.get("redirect_uri")
    auth_url = None
    redir = None
    if provider == "google_drive":
        auth_url = scanner.cloud.get_google_drive_auth_url(explicit)
    elif provider == "dropbox":
        auth_url = scanner.cloud.get_dropbox_auth_url(explicit)
        redir = scanner.cloud._dropbox_redirect_uri()
    elif provider == "onedrive":
        auth_url = scanner.cloud.get_onedrive_auth_url(explicit)
        redir = scanner.cloud._onedrive_redirect_uri()

    if auth_url:
        if provider == "google_drive":
            cfg = scanner.cloud._google_oauth_config()
            redir = (cfg["redirect_uris"] or [None])[0]
        return jsonify({"auth_url": auth_url, "redirect_uri": redir})
    return jsonify({"error": "Provider not configured or not supported"}), 400


@app.route("/cloud/drive-check")
def cloud_drive_check():
    cfg = scanner.cloud._google_oauth_config()
    status = scanner.cloud.status()
    return jsonify({
        "client_id": cfg["client_id"],
        "redirect_uris": cfg["redirect_uris"],
        "connected": status["google_drive"]["connected"],
    })


@app.route("/cloud/callback/<provider>")
def cloud_callback(provider):
    auth_code = request.args.get("code", "")
    if not auth_code:
        return jsonify({"error": "No auth code"}), 400

    success = False
    if provider == "google_drive":
        success = scanner.cloud.handle_google_drive_callback(auth_code)
    elif provider == "dropbox":
        success = scanner.cloud.handle_dropbox_callback(request.args)
    elif provider == "onedrive":
        success = scanner.cloud.handle_onedrive_callback(auth_code)

    if success:
        return _oauth_result_page(True, provider)
    err = getattr(scanner.cloud, "_dropbox_last_error", None)
    msg = "Auth failed"
    if err:
        msg += f" ({err})"
    return _oauth_result_page(False, provider, msg)


def _oauth_result_page(success: bool, provider: str, msg: str = ""):
    label = provider.replace("_", " ").upper()
    text = f"{label} CONNECTED! You can close this window." if success else \
        (msg or "AUTH FAILED. Close this window and try again.")
    tone = "ok" if success else "err"
    icon = "&#10004;" if success else "&#10007;"
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>AI Scanner</title><style>
body{{font-family:'Segoe UI',Arial,sans-serif;display:flex;align-items:center;justify-content:center;
height:90vh;margin:0;background:#f7f3ea;color:#3b2f22}}
.card{{text-align:center;padding:28px 40px;background:#fff;border:1px solid #c9a96e;border-radius:10px}}
.ok{{color:#3c7a3c}}.err{{color:#a33}}
.icon{{font-size:34px}}</style></head><body><div class="card">
<div class="icon {tone}">{icon}</div>
<div class="{tone}" style="font-weight:600">{text}</div>
<script>setTimeout(function(){{window.close();}},1200);</script>
</div></body></html>"""


@app.route("/auth/google/callback")
def auth_google_callback():
    code = request.args.get("code", "")
    success = False
    if code:
        success = scanner.cloud.handle_google_drive_callback(code)
    msg, tone = ("CONNECTED! You can close this window.", "ok") if success \
        else ("AUTH FAILED. Close this window and try again.", "err")
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>AI Scanner</title><style>
body{{font-family:'Segoe UI',Arial,sans-serif;display:flex;align-items:center;justify-content:center;
height:90vh;margin:0;background:#f7f3ea;color:#3b2f22}}
.card{{text-align:center;padding:28px 40px;background:#fff;border:1px solid #c9a96e;border-radius:10px}}
.ok{{color:#3c7a3c}}.err{{color:#a33}}
.icon{{font-size:34px}}</style></head><body><div class="card">
<div class="icon {tone}">{"&#10004;" if success else "&#10007;"}</div>
<div class="{tone}" style="font-weight:600">{msg}</div>
<script>setTimeout(function(){{window.close();}},1200);</script>
</div></body></html>"""


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
    scanner.cloud.disconnect(provider)
    return jsonify({"disconnected": True})


@app.route("/cloud/folder/<provider>")
def cloud_folder(provider):
    url = scanner.cloud.get_folder_url(provider)
    if not url:
        return jsonify({"error": "Provider not connected"}), 400
    return jsonify({"url": url})


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
#  Bluetooth Camera API
# ---------------------------------------------------------------------------

_bluetooth_manager: Optional[BluetoothCameraManager] = None
_bluetooth_device: Optional[BluetoothDevice] = None
_bluetooth_streaming = False

# QR pairing sessions: token -> {created, expiry, device_name, connected, last_frame}
BT_SESSION_TTL = 900
_bt_sessions: Dict[str, Dict[str, Any]] = {}


def _get_bluetooth_manager() -> BluetoothCameraManager:
    global _bluetooth_manager
    if _bluetooth_manager is None:
        _bluetooth_manager = BluetoothCameraManager()
    return _bluetooth_manager


def _new_bt_token() -> str:
    return secrets.token_hex(8)


def _clean_bt_sessions():
    now = time.time()
    expired = [t for t, s in _bt_sessions.items() if now > s.get("expiry", 0)]
    for t in expired:
        _bt_sessions.pop(t, None)


@app.route("/api/bluetooth/pairing", methods=["POST"])
def bluetooth_create_pairing():
    """QR-first pairing: create a session and return a QR code the user's
    Bluetooth device scans to open the mobile camera page."""
    _clean_bt_sessions()

    token = _new_bt_token()
    pairing_id = "BT-" + token[:6].upper()

    local_ip = socket.gethostbyname(socket.gethostname())
    port = request.host.split(":")[1] if ":" in request.host else "80"
    base_url = f"http://{local_ip}:{port}"

    data = request.get_json(silent=True) or {}
    device_name = data.get("device_name", "Scanner")
    config = {
        "width": int(data.get("width", 640)),
        "height": int(data.get("height", 480)),
        "quality": int(data.get("quality", 85)),
        "auto_capture": bool(data.get("auto_capture", True)),
        "interval": float(data.get("interval", 2.0))
    }

    connect_url = f"{base_url}/bt/cam/{token}"
    qr_code = create_url_qr_base64(connect_url)

    _bt_sessions[token] = {
        "pairing_id": pairing_id,
        "created": time.time(),
        "expiry": time.time() + BT_SESSION_TTL,
        "device_name": None,
        "connected": False,
        "last_frame": None,
        "connect_url": connect_url,
        "config": config,
        "command": None,
    }

    return jsonify({
        "token": token,
        "pairing_id": pairing_id,
        "qr_code": qr_code,
        "connect_url": connect_url,
        "expires_in": BT_SESSION_TTL,
        "config": config,
    })


@app.route("/api/bluetooth/pairing/<token>", methods=["GET"])
def bluetooth_pairing_status(token):
    _clean_bt_sessions()
    session = _bt_sessions.get(token)
    if not session:
        return jsonify({"error": "Pairing session not found or expired"}), 404
    return jsonify({
        "pairing_id": session["pairing_id"],
        "connected": session["connected"],
        "device_name": session["device_name"],
        "expires_in": max(0, int(session["expiry"] - time.time())),
        "command": session.get("command"),
    })


@app.route("/api/bluetooth/pairing/<token>/frame", methods=["POST"])
def bluetooth_pairing_frame(token):
    """Mobile camera page posts JPEG frames here."""
    _clean_bt_sessions()
    session = _bt_sessions.get(token)
    if not session:
        return jsonify({"error": "Pairing session not found or expired"}), 404

    data = request.get_json(silent=True) or {}
    if data.get("image"):
        session["last_frame"] = data["image"]
        session["connected"] = True
        session["command"] = None
        if data.get("device_name"):
            session["device_name"] = data["device_name"]
        session["last_seen"] = time.time()
        return jsonify({"ok": True})

    return jsonify({"error": "No image provided"}), 400


@app.route("/api/bluetooth/pairing/<token>/frame", methods=["GET"])
def bluetooth_pairing_frame_get(token):
    """Scanner UI polls this to preview the live Bluetooth camera feed."""
    _clean_bt_sessions()
    session = _bt_sessions.get(token)
    if not session:
        return jsonify({"error": "Pairing session not found or expired"}), 404
    return jsonify({
        "connected": session["connected"],
        "device_name": session["device_name"],
        "image": session["last_frame"],
    })


@app.route("/api/bluetooth/pairing/<token>/control", methods=["POST"])
def bluetooth_pairing_control(token):
    """Scanner → device control: stop closes the camera app on the paired
    device, start reopens it."""
    _clean_bt_sessions()
    session = _bt_sessions.get(token)
    if not session:
        return jsonify({"error": "Pairing session not found or expired"}), 404

    data = request.get_json(silent=True) or {}
    cmd = data.get("command")
    if cmd not in ("stop", "start"):
        return jsonify({"error": "Invalid command"}), 400

    session["command"] = cmd
    if cmd == "stop":
        session["connected"] = False
    return jsonify({"ok": True, "command": cmd})


@app.route("/api/bluetooth/pairing/<token>/control", methods=["GET"])
def bluetooth_pairing_control_get(token):
    """The device camera page polls this to react to scanner commands."""
    _clean_bt_sessions()
    session = _bt_sessions.get(token)
    if not session:
        return jsonify({"error": "Pairing session not found or expired"}), 404
    return jsonify({
        "command": session.get("command"),
        "connected": session["connected"],
    })


@app.route("/bt/cam/<token>")
def bluetooth_mobile_cam(token):
    """Minimal mobile page that the scanned Bluetooth device opens to access
    its camera and stream frames back to this scanner."""
    _clean_bt_sessions()
    session = _bt_sessions.get(token)
    if not session:
        return "Pairing session expired. Please scan a fresh code.", 410
    return render_template("bt_cam.html", token=token, pairing_id=session["pairing_id"])


@app.route("/api/bluetooth/pairing/<token>", methods=["DELETE"])
def bluetooth_pairing_delete(token):
    _bt_sessions.pop(token, None)
    return jsonify({"ok": True})


@app.route("/api/bluetooth/status")
def bluetooth_status():
    _clean_bt_sessions()
    active_sessions = [
        {
            "token": t,
            "pairing_id": s.get("pairing_id"),
            "device_name": s.get("device_name"),
            "connected": s.get("connected", False),
            "expires_in": max(0, int(s.get("expiry", 0) - time.time())),
        }
        for t, s in _bt_sessions.items()
    ]
    return jsonify({
        "available": BLEAK_AVAILABLE,
        "connected": _bluetooth_device is not None,
        "device": {
            "address": _bluetooth_device.address,
            "name": _bluetooth_device.name,
            "rssi": _bluetooth_device.rssi,
            "battery": _bluetooth_device.battery_level,
            "is_camera": _bluetooth_device.is_camera
        } if _bluetooth_device else None,
        "streaming": _bluetooth_streaming,
        "sessions": active_sessions,
    })


@app.route("/api/bluetooth/scan", methods=["POST"])
def bluetooth_scan():
    if not BLEAK_AVAILABLE:
        return jsonify({"error": "Bluetooth not available (bleak not installed)"}), 503
    
    data = request.json or {}
    duration = float(data.get("duration", 10.0))
    
    async def do_scan():
        manager = _get_bluetooth_manager()
        devices = await manager.scan_for_devices(duration=duration, filter_camera_only=True)
        return devices
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        devices = loop.run_until_complete(do_scan())
        loop.close()
        
        return jsonify({
            "devices": [
                {
                    "address": d.address,
                    "name": d.name,
                    "rssi": d.rssi,
                    "services": d.services,
                    "is_camera": d.is_camera,
                    "battery": d.battery_level
                }
                for d in devices
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bluetooth/connect", methods=["POST"])
def bluetooth_connect():
    if not BLEAK_AVAILABLE:
        return jsonify({"error": "Bluetooth not available (bleak not installed)"}), 503
    
    data = request.json or {}
    address = data.get("address", "").strip()
    name = data.get("name", "").strip()
    
    if not address:
        return jsonify({"error": "Device address required"}), 400
    
    device = BluetoothDevice(address=address, name=name or "Unknown", is_camera=True)
    
    async def do_connect():
        manager = _get_bluetooth_manager()
        connected = await manager.connect(device)
        return connected, manager
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        connected, manager = loop.run_until_complete(do_connect())
        loop.close()
        
        if connected:
            global _bluetooth_device
            _bluetooth_device = device
            return jsonify({
                "connected": True,
                "device": {
                    "address": device.address,
                    "name": device.name
                }
            })
        else:
            return jsonify({"error": "Failed to connect to device"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bluetooth/disconnect", methods=["POST"])
def bluetooth_disconnect():
    global _bluetooth_device, _bluetooth_streaming
    
    if _bluetooth_manager:
        async def do_disconnect():
            await _bluetooth_manager.disconnect()
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(do_disconnect())
            loop.close()
        except Exception:
            pass
    
    _bluetooth_device = None
    _bluetooth_streaming = False
    
    return jsonify({"disconnected": True})


@app.route("/api/bluetooth/configure", methods=["POST"])
def bluetooth_configure():
    if not _bluetooth_manager or not _bluetooth_device:
        return jsonify({"error": "No device connected"}), 400
    
    data = request.json or {}
    config = BluetoothCameraConfig(
        device_address=_bluetooth_device.address,
        device_name=_bluetooth_device.name,
        image_width=int(data.get("width", 640)),
        image_height=int(data.get("height", 480)),
        jpeg_quality=int(data.get("quality", 85)),
        auto_capture=bool(data.get("auto_capture", False)),
        capture_interval=float(data.get("interval", 2.0))
    )
    
    async def do_configure():
        return await _bluetooth_manager.configure_camera(config)
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        configured = loop.run_until_complete(do_configure())
        loop.close()
        
        return jsonify({"configured": configured})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bluetooth/capture", methods=["POST"])
def bluetooth_capture():
    if not _bluetooth_manager or not _bluetooth_device:
        return jsonify({"error": "No device connected"}), 400
    
    async def do_capture():
        return await _bluetooth_manager.capture_single()
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        frame = loop.run_until_complete(do_capture())
        loop.close()
        
        if frame is not None:
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            import base64
            img_base64 = base64.b64encode(buffer).decode()
            return jsonify({
                "captured": True,
                "image": f"data:image/jpeg;base64,{img_base64}",
                "width": frame.shape[1],
                "height": frame.shape[0]
            })
        else:
            return jsonify({"error": "Failed to capture image"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bluetooth/stream/start", methods=["POST"])
def bluetooth_stream_start():
    global _bluetooth_streaming
    
    if not _bluetooth_manager or not _bluetooth_device:
        return jsonify({"error": "No device connected"}), 400
    
    if _bluetooth_streaming:
        return jsonify({"streaming": True})
    
    data = request.json or {}
    interval = float(data.get("interval", 2.0))
    
    async def do_stream():
        global _bluetooth_streaming
        _bluetooth_streaming = True
        
        frames = []
        
        def frame_callback(frame):
            frames.append(frame)
            if len(frames) > 10:
                frames.pop(0)
        
        await _bluetooth_manager.start_streaming(frame_callback)
        await asyncio.sleep(interval * 3)
        await _bluetooth_manager.stop_streaming()
        _bluetooth_streaming = False
        return frames[-1] if frames else None
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        frame = loop.run_until_complete(do_stream())
        loop.close()
        
        if frame is not None:
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            import base64
            img_base64 = base64.b64encode(buffer).decode()
            return jsonify({
                "streaming": True,
                "image": f"data:image/jpeg;base64,{img_base64}",
                "width": frame.shape[1],
                "height": frame.shape[0]
            })
        else:
            _bluetooth_streaming = False
            return jsonify({"error": "Failed to get frame from stream"}), 500
    except Exception as e:
        _bluetooth_streaming = False
        return jsonify({"error": str(e)}), 500


@app.route("/api/bluetooth/stream/stop", methods=["POST"])
def bluetooth_stream_stop():
    global _bluetooth_streaming
    
    if _bluetooth_manager:
        async def do_stop():
            await _bluetooth_manager.stop_streaming()
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(do_stop())
            loop.close()
        except Exception:
            pass
    
    _bluetooth_streaming = False
    return jsonify({"streaming": False})


@app.route("/api/bluetooth/qr/generate", methods=["POST"])
def bluetooth_generate_qr():
    if not _bluetooth_device:
        return jsonify({"error": "No device selected"}), 400
    
    data = request.json or {}
    config = {
        "width": int(data.get("width", 640)),
        "height": int(data.get("height", 480)),
        "quality": int(data.get("quality", 85)),
        "auto_capture": bool(data.get("auto_capture", True)),
        "interval": float(data.get("interval", 2.0))
    }
    
    qr_base64 = create_bluetooth_qr_for_device(
        device_id=_bluetooth_device.address.replace(":", ""),
        device_name=_bluetooth_device.name,
        device_address=_bluetooth_device.address,
        config=config
    )
    
    pairing_data = {
        "type": "bluetooth_camera_pairing",
        "version": "1.0",
        "device": {
            "address": _bluetooth_device.address,
            "name": _bluetooth_device.name,
            "is_camera": True
        },
        "config": config
    }
    
    import json
    qr_data = json.dumps(pairing_data, separators=(',', ':'))
    
    return jsonify({
        "qr_code": qr_base64,
        "qr_data": qr_data,
        "device": {
            "address": _bluetooth_device.address,
            "name": _bluetooth_device.name
        }
    })


@app.route("/api/bluetooth/qr/parse", methods=["POST"])
def bluetooth_parse_qr():
    data = request.json or {}
    qr_data = data.get("qr_data", "").strip()
    
    if not qr_data:
        return jsonify({"error": "QR data required"}), 400
    
    try:
        pairing = json.loads(qr_data)
        if pairing.get("type") != "bluetooth_camera_pairing":
            return jsonify({"error": "Invalid QR code type"}), 400
        
        device_info = pairing.get("device", {})
        config = pairing.get("config", {})
        
        return jsonify({
            "valid": True,
            "device": device_info,
            "config": config
        })
    except Exception as e:
        return jsonify({"error": f"Invalid QR data: {str(e)}"}), 400


# ---------------------------------------------------------------------------
#  Entry Point
# ---------------------------------------------------------------------------

def main():
    import argparse, socket as _socket, ssl, tempfile, atexit
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="AI Scanner Web Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5000)))
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--ngrok", action="store_true", help="Expose via ngrok (requires ngrok installed)")
    parser.add_argument("--ssl", action="store_true", help="Enable HTTPS with auto-generated self-signed cert (for camera access on LAN)")
    parser.add_argument("--cert", help="Path to SSL certificate file (PEM)")
    parser.add_argument("--key", help="Path to SSL private key file (PEM)")
    args = parser.parse_args()
    local_ip = _socket.gethostbyname(_socket.gethostname())

    ssl_context = None
    if args.ssl or args.cert or args.key:
        if args.cert and args.key:
            ssl_context = (args.cert, args.key)
            print(f"  🔒 Using SSL cert: {args.cert}")
        else:
            from cryptography.hazmat.primitives import serialization, hashes
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            import datetime, ipaddress
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AI Scanner"),
            ])
            san_list = [x509.DNSName("localhost")]
            try:
                san_list.append(x509.IPAddress(ipaddress.IPv4Address(local_ip)))
            except Exception:
                pass
            cert = x509.CertificateBuilder().subject_name(subject).issuer_name(issuer).public_key(key.public_key()).serial_number(
                x509.random_serial_number()).not_valid_before(
                datetime.datetime.now(datetime.timezone.utc)).not_valid_after(
                datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365)
            ).add_extension(x509.SubjectAlternativeName(san_list), critical=False).sign(key, hashes.SHA256())
            cert_pem = cert.public_bytes(serialization.Encoding.PEM)
            key_pem = key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            cert_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pem')
            key_file = tempfile.NamedTemporaryFile(delete=False, suffix='.key')
            cert_file.write(cert_pem)
            key_file.write(key_pem)
            cert_file.close()
            key_file.close()
            atexit.register(lambda: os.unlink(cert_file.name))
            atexit.register(lambda: os.unlink(key_file.name))
            ssl_context = (cert_file.name, key_file.name)
            print(f"  🔒 Auto-generated self-signed SSL cert (valid 365 days)")
            print(f"     Accept browser warning to enable camera on LAN")
    print(f"\n  {'='*45}")
    print(f"  ◈ AI SCANNER // NEXUS-OS v3.0")
    print(f"  {'='*45}")
    print(f"  Local:   http://localhost:{args.port}")
    print(f"  Network: http://{local_ip}:{args.port}")
    print(f"  Phone:   Use --ngrok for HTTPS (camera requires HTTPS on mobile)")
    drive_uri = scanner.cloud._google_oauth_config().get("redirect_uris") or [None]
    print(f"  Drive:   callback -> {drive_uri[0]}  (must match Google console)")
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
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True, ssl_context=ssl_context)

if __name__ == "__main__":
    main()
