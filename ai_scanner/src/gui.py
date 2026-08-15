import sys
import os
import threading
import asyncio
from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import customtkinter as ctk
import cv2
import numpy as np
from PIL import Image, ImageTk

from src.camera.capture import CameraCapture
from src.camera.bluetooth_camera import (
    BluetoothCameraManager,
    BluetoothDevice,
    BluetoothCameraConfig,
    create_bluetooth_camera_capture,
    generate_pairing_qr_code_base64,
    scan_bluetooth_cameras,
    BLEAK_AVAILABLE
)
from src.edge_detection.detector import EdgeDetector
from src.enhancement.enhancer import ImageEnhancer
from src.ocr.ocr_engine import OCREngine
from src.classification.classifier import DocumentClassifier
from src.storage.local_storage import LocalStorage
from src.storage.cloud_sync import CloudSync
from src.utils.auto_naming import AutoNamer
from src.utils.qr_detection import QRDetector
from src.utils.bluetooth_qr import create_bluetooth_qr_for_device

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

FONT_LARGE = ("Segoe UI", 20, "bold")
FONT_MEDIUM = ("Segoe UI", 15)
FONT_SMALL = ("Segoe UI", 12)


class AIScannerGUI:
    def __init__(self):
        self.scanner = None
        self.camera = None
        self.captured_frame = None
        self.processed_result = None
        self.camera_running = False
        self.preview_after_id = None
        self.bluetooth_camera = None
        self.bluetooth_manager = None
        self.bluetooth_device = None
        self.bluetooth_streaming = False

        self._init_scanner()
        self._build_ui()

    def _init_scanner(self):
        self.edges = EdgeDetector()
        self.enhancer = ImageEnhancer()
        self.ocr = OCREngine()
        self.classifier = DocumentClassifier()
        self.storage = LocalStorage()
        self.cloud = CloudSync()
        self.namer = AutoNamer()
        self.qr = QRDetector()
        
        if BLEAK_AVAILABLE:
            self.bluetooth_manager = BluetoothCameraManager()

    def _build_ui(self):
        self.window = ctk.CTk()
        self.window.title("AI Document Scanner")
        self.window.geometry("1100x720")
        self.window.minsize(900, 600)

        self.window.grid_columnconfigure(0, weight=0, minsize=180)
        self.window.grid_columnconfigure(1, weight=1)
        self.window.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_area()

        self.show_tab("capture")

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self.window, width=180, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(sidebar, text="AI Scanner", font=FONT_LARGE).pack(pady=(20, 5))
        ctk.CTkLabel(sidebar, text="Document Scanner Pro", font=("Segoe UI", 11)).pack(pady=(0, 20))

        self.nav_btns = {}
        nav_items = [
            ("capture", "📷  Capture", 0),
            ("results", "📄  Results", 1),
            ("settings", "⚙  Settings", 2),
        ]
        for name, text, row in nav_items:
            btn = ctk.CTkButton(sidebar, text=text, font=FONT_MEDIUM,
                                anchor="w", command=lambda n=name: self.show_tab(n))
            btn.pack(pady=4, padx=10, fill="x")
            self.nav_btns[name] = btn

        ctk.CTkLabel(sidebar, text="", font=FONT_SMALL).pack(expand=True, fill="both")
        ver = ctk.CTkLabel(sidebar, text="v1.0.0", font=("Segoe UI", 10), text_color="gray")
        ver.pack(pady=10)

    def _build_main_area(self):
        self.main = ctk.CTkFrame(self.window, corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(0, weight=1)

        self.tabs = {}
        self._build_capture_tab()
        self._build_results_tab()
        self._build_settings_tab()

    def show_tab(self, name):
        for n, frame in self.tabs.items():
            frame.grid_remove()
        self.tabs[name].grid(row=0, column=0, sticky="nsew")
        for btn_name, btn in self.nav_btns.items():
            btn.configure(fg_color="#1f538d" if btn_name == name else "transparent")

    # ---- Capture Tab ----
    def _build_capture_tab(self):
        tab = ctk.CTkFrame(self.main)
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        self.tabs["capture"] = tab

        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.grid(row=0, column=0, pady=(10, 5), padx=15, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Document Capture", font=FONT_LARGE, anchor="w").pack(side="left")

        self.capture_status = ctk.CTkLabel(header, text="Ready", font=FONT_SMALL, text_color="gray")
        self.capture_status.pack(side="right", padx=10)

        preview_frame = ctk.CTkFrame(tab, corner_radius=10)
        preview_frame.grid(row=1, column=0, padx=15, pady=5, sticky="nsew")
        preview_frame.grid_columnconfigure(0, weight=1)
        preview_frame.grid_rowconfigure(0, weight=1)

        self.camera_label = ctk.CTkLabel(preview_frame, text="No camera feed\n\nOpen camera or load an image",
                                          font=FONT_MEDIUM)
        self.camera_label.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        quality_frame = ctk.CTkFrame(tab, fg_color="transparent")
        quality_frame.grid(row=2, column=0, pady=5, padx=15, sticky="ew")
        quality_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.quality_indicators = {}
        for i, (label, key) in enumerate([
            ("Blur", "blur"), ("Brightness", "brightness"),
            ("Quality", "quality_pass"), ("Document", "document")
        ]):
            f = ctk.CTkFrame(quality_frame)
            f.grid(row=0, column=i, padx=5, sticky="ew")
            ctk.CTkLabel(f, text=label, font=("Segoe UI", 10), text_color="gray").pack()
            val = ctk.CTkLabel(f, text="--", font=("Segoe UI", 14, "bold"))
            val.pack()
            self.quality_indicators[key] = val

        action_frame = ctk.CTkFrame(tab, fg_color="transparent")
        action_frame.grid(row=3, column=0, pady=(5, 15), padx=15, sticky="ew")
        action_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.btn_open = ctk.CTkButton(action_frame, text="📷  Open Camera", command=self.toggle_camera)
        self.btn_open.grid(row=0, column=0, padx=5)

        self.btn_capture = ctk.CTkButton(action_frame, text="🖼  Capture", command=self.capture_from_camera,
                                          state="disabled")
        self.btn_capture.grid(row=0, column=1, padx=5)

        self.btn_load = ctk.CTkButton(action_frame, text="📂  Load Image", command=self.load_image)
        self.btn_load.grid(row=0, column=2, padx=5)

        self.btn_bluetooth = ctk.CTkButton(action_frame, text="📱  Bluetooth", command=self.open_bluetooth_dialog,
                                           fg_color="#0066cc", hover_color="#0052a3")
        self.btn_bluetooth.grid(row=0, column=3, padx=5)

        self.btn_process = ctk.CTkButton(action_frame, text="⚡  Process", command=self.process_current,
                                          fg_color="#2d8a4e", hover_color="#236b3d")
        self.btn_process.grid(row=0, column=4, padx=5)

        self.btn_open_folder = ctk.CTkButton(action_frame, text="📁  Open Folder",
                                              command=lambda: os.startfile(
                                                  os.path.abspath(self.storage.base_dir / "documents")),
                                              fg_color="gray", hover_color="#666666")
        self.btn_open_folder.grid(row=0, column=5, padx=5)

    def _update_quality_indicators(self, result: dict):
        q = result.get("quality", {})
        self.quality_indicators["blur"].configure(
            text=f"{q.get('blur_score', 0):.0f}",
            text_color="#2d8a4e" if not q.get("is_blurry") else "#d32f2f"
        )
        self.quality_indicators["brightness"].configure(
            text=f"{q.get('brightness', 0):.0f}",
            text_color="#2d8a4e" if q.get("good_lighting") else "#d32f2f"
        )
        passed = q.get("quality_pass", False)
        self.quality_indicators["quality_pass"].configure(
            text="✅ PASS" if passed else "❌ FAIL",
            text_color="#2d8a4e" if passed else "#d32f2f"
        )
        detected = result.get("document_detected", False)
        self.quality_indicators["document"].configure(
            text="✅ Yes" if detected else "❌ No",
            text_color="#2d8a4e" if detected else "#d32f2f"
        )

    def _display_frame(self, frame):
        if frame is None:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        max_w, max_h = 620, 420
        scale = min(max_w / w, max_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        rgb = cv2.resize(rgb, (new_w, new_h))
        img = Image.fromarray(rgb)
        tk_img = ctk.CTkImage(img, size=(new_w, new_h))
        self.camera_label.configure(image=tk_img, text="")
        self.camera_label.image = tk_img

    def toggle_camera(self):
        if self.camera_running:
            self._stop_camera()
        else:
            self._start_camera()

    def _start_camera(self):
        if self.camera is None:
            self.camera = CameraCapture()
        if not self.camera.open():
            self.capture_status.configure(text="Camera failed", text_color="#d32f2f")
            return
        self.camera_running = True
        self.btn_open.configure(text="📷  Close Camera", fg_color="#d32f2f")
        self.btn_capture.configure(state="normal")
        self.capture_status.configure(text="Camera active", text_color="#2d8a4e")
        self._update_camera_preview()

    def _stop_camera(self):
        self.camera_running = False
        if self.preview_after_id:
            self.window.after_cancel(self.preview_after_id)
            self.preview_after_id = None
        if self.camera:
            self.camera.release()
        self.btn_open.configure(text="📷  Open Camera", fg_color="#1f538d")
        self.btn_capture.configure(state="disabled")
        self.capture_status.configure(text="Camera closed", text_color="gray")
        self.camera_label.configure(image="", text="No camera feed\n\nOpen camera or load an image")

    def _update_camera_preview(self):
        if not self.camera_running:
            return
        frame = self.camera.capture_frame()
        if frame is not None:
            result = self.camera.auto_detect_document(frame)
            display = self.camera.draw_detection(result.frame, result.corners)
            self._display_frame(display)
            self.captured_frame = frame
        self.preview_after_id = self.window.after(30, self._update_camera_preview)

    def capture_from_camera(self):
        if self.captured_frame is None:
            return
        self._stop_camera()
        self._display_frame(self.captured_frame)
        self.capture_status.configure(text="Captured - ready to process", text_color="#2d8a4e")
        messagebox.showinfo("Captured", "Frame captured! Click 'Process' to analyze.")

    def load_image(self):
        path = filedialog.askopenfilename(
            title="Select Document Image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.tiff *.bmp"), ("All Files", "*.*")]
        )
        if not path:
            return
        self.captured_frame = cv2.imread(path)
        if self.captured_frame is None:
            messagebox.showerror("Error", "Could not read image file")
            return
        self._display_frame(self.captured_frame)
        self.capture_status.configure(text=f"Loaded: {os.path.basename(path)}", text_color="#2d8a4e")

    def process_current(self):
        if self.captured_frame is None:
            messagebox.showwarning("No Image", "Capture or load an image first")
            return
        self.capture_status.configure(text="Processing...", text_color="#ff9800")
        self.btn_process.configure(state="disabled")
        threading.Thread(target=self._do_process, daemon=True).start()

    def _do_process(self):
        try:
            image = self.captured_frame.copy()
            result = {"original_shape": image.shape}

            quality = self.enhancer.quality_assessment(image)
            result["quality"] = quality

            corners = self.edges.find_document_contour(image)
            if corners is not None:
                result["document_detected"] = True
                corrected = self.edges.perspective_correct(image, corners)
            else:
                result["document_detected"] = False
                corrected = image

            enhanced = self.enhancer.enhance_document(corrected)
            result["enhanced"] = True
            result["enhanced_image"] = enhanced
            result["original_image"] = image

            ocr_result = self.ocr.extract_text(enhanced)
            result["ocr"] = {"text": ocr_result.text, "confidence": ocr_result.confidence}

            if ocr_result.text:
                classification = self.classifier.classify(ocr_result.text)
                result["classification"] = {
                    "type": classification.doc_type,
                    "confidence": classification.confidence,
                    "extracted_data": classification.extracted_data,
                }
                doc_type = classification.doc_type
                extracted = classification.extracted_data
            else:
                result["classification"] = {"type": "unknown", "confidence": 0}
                doc_type = "document"
                extracted = {}

            qr_results = self.qr.detect(enhanced)
            if qr_results:
                result["qr_codes"] = [{"data": r.data, "type": r.type} for r in qr_results]

            filename = self.namer.generate_name(doc_type, extracted, ocr_result.text)
            result["filename"] = filename

            filepath = self.storage.save_document(enhanced, filename, doc_type, {
                "ocr_text": ocr_result.text,
                "ocr_confidence": ocr_result.confidence,
                "doc_type": doc_type,
                "extracted_data": extracted,
                "quality": quality,
            })
            result["saved_path"] = filepath

            self.processed_result = result
            self.window.after(0, self._show_results)

        except Exception as e:
            self.window.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.window.after(0, lambda: self.btn_process.configure(state="normal"))
            self.window.after(0, lambda: self.capture_status.configure(text="Done"))

    # ---- Results Tab ----
    def _build_results_tab(self):
        tab = ctk.CTkFrame(self.main)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        self.tabs["results"] = tab

        left = ctk.CTkScrollableFrame(tab, width=340)
        left.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(10, 5), pady=10)
        left.grid_columnconfigure(0, weight=1)

        right = ctk.CTkScrollableFrame(tab)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=(10, 5))
        right.grid_columnconfigure(0, weight=1)

        # Left panel - images
        ctk.CTkLabel(left, text="Original", font=FONT_MEDIUM).pack(pady=(0, 5))
        self.result_orig = ctk.CTkLabel(left, text="--", font=FONT_SMALL)
        self.result_orig.pack(pady=(0, 10))

        ctk.CTkLabel(left, text="Enhanced", font=FONT_MEDIUM).pack(pady=(0, 5))
        self.result_enhanced = ctk.CTkLabel(left, text="--", font=FONT_SMALL)
        self.result_enhanced.pack(pady=(0, 10))

        # Photo Properties in left panel
        props_frame = ctk.CTkFrame(left)
        props_frame.pack(fill="x", pady=(5, 0))
        ctk.CTkLabel(props_frame, text="📋 Photo Properties", font=FONT_MEDIUM).pack(anchor="w", padx=10, pady=(8, 5))

        self.props_widgets = {}
        for prop_id, prop_label in [
            ("dimensions", "Dimensions"),
            ("file_size", "File Size"),
            ("saved_date", "Saved Date"),
            ("ocr_chars", "Text Length"),
        ]:
            row = ctk.CTkFrame(props_frame, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=2)
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row, text=prop_label, font=("Segoe UI", 11), text_color="gray",
                         width=90, anchor="w").grid(row=0, column=0, sticky="w")
            val = ctk.CTkLabel(row, text="--", font=("Segoe UI", 12), anchor="w")
            val.grid(row=0, column=1, sticky="ew", padx=(5, 0))
            self.props_widgets[prop_id] = val

        # Bottom action bar
        action_bar = ctk.CTkFrame(tab, fg_color="transparent", height=50)
        action_bar.grid(row=1, column=1, sticky="ew", padx=10, pady=(0, 10))
        action_bar.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkButton(action_bar, text="📂  Open Folder",
                       command=lambda: os.startfile(
                           os.path.abspath(self.storage.base_dir / "documents")),
                       fg_color="gray", hover_color="#666666"
                       ).grid(row=0, column=0, padx=5)

        self.btn_retake = ctk.CTkButton(action_bar, text="🔄  Retake Photo",
                                         command=self.retake_photo,
                                         fg_color="#ff9800", hover_color="#e68900")
        self.btn_retake.grid(row=0, column=1, padx=5)

        self.btn_close = ctk.CTkButton(action_bar, text="✖  Close Analysis",
                                        command=self.close_analysis,
                                        fg_color="#d32f2f", hover_color="#b71c1c")
        self.btn_close.grid(row=0, column=2, padx=5)

        # Right panel - data
        self.result_widgets = {}

        sections = [
            ("document", "📄 Document Info", [
                ("type", "Type"),
                ("confidence", "Confidence"),
                ("filename", "Filename"),
                ("saved", "Saved To"),
            ]),
            ("quality", "✅ Quality Assessment", [
                ("blur", "Blur Score"),
                ("brightness", "Brightness"),
                ("lighting", "Lighting"),
                ("status", "Status"),
            ]),
            ("ocr", "📝 OCR Text", [
                ("text", "Extracted Text"),
                ("ocr_conf", "Confidence"),
            ]),
            ("extracted", "🔍 Extracted Data", [
                ("amounts", "Amounts"),
                ("dates", "Dates"),
                ("entities", "Entities"),
            ]),
            ("qr", "📱 QR / Barcodes", [
                ("qr_data", "Detected Codes"),
            ]),
        ]

        for sec_id, sec_title, fields in sections:
            frame = ctk.CTkFrame(right)
            frame.pack(fill="x", pady=(0, 10))
            frame.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(frame, text=sec_title, font=FONT_MEDIUM).pack(anchor="w", padx=10, pady=(8, 5))

            for field_id, field_label in fields:
                row = ctk.CTkFrame(frame, fg_color="transparent")
                row.pack(fill="x", padx=10, pady=2)
                row.grid_columnconfigure(1, weight=1)
                ctk.CTkLabel(row, text=field_label, font=("Segoe UI", 11), text_color="gray",
                             width=100, anchor="w").grid(row=0, column=0, sticky="w")
                val = ctk.CTkLabel(row, text="--", font=("Segoe UI", 12), anchor="w", wraplength=350)
                val.grid(row=0, column=1, sticky="ew", padx=(5, 0))
                self.result_widgets[f"{sec_id}_{field_id}"] = val

            self.result_widgets[f"{sec_id}_sep"] = None

    def _show_results(self):
        self.show_tab("results")
        r = self.processed_result
        if r is None:
            return

        def set_img(label, img, max_w=260, max_h=200):
            if img is None:
                label.configure(text="No image")
                return
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            scale = min(max_w / w, max_h / h)
            nw, nh = int(w * scale), int(h * scale)
            rgb = cv2.resize(rgb, (nw, nh))
            tk_img = ctk.CTkImage(Image.fromarray(rgb), size=(nw, nh))
            label.configure(image=tk_img, text="")
            label.image = tk_img

        set_img(self.result_orig, r.get("original_image"))
        set_img(self.result_enhanced, r.get("enhanced_image"))

        quality = r.get("quality", {})
        self.result_widgets["quality_blur"].configure(
            text=f"{quality.get('blur_score', 0):.1f}",
            text_color="#2d8a4e" if not quality.get("is_blurry") else "#d32f2f"
        )
        self.result_widgets["quality_brightness"].configure(
            text=f"{quality.get('brightness', 0):.0f}",
            text_color="#2d8a4e" if quality.get("good_lighting") else "#d32f2f"
        )
        self.result_widgets["quality_lighting"].configure(
            text="✅ Good" if quality.get("good_lighting") else "❌ Poor"
        )
        passed = quality.get("quality_pass", False)
        self.result_widgets["quality_status"].configure(
            text="✅ PASS" if passed else "❌ FAIL",
            text_color="#2d8a4e" if passed else "#d32f2f"
        )

        cls = r.get("classification", {})
        doc_type = cls.get("type", "Unknown").capitalize()
        conf = cls.get("confidence", 0)
        self.result_widgets["document_type"].configure(text=doc_type)
        self.result_widgets["document_confidence"].configure(
            text=f"{conf:.0%}",
            text_color="#2d8a4e" if conf > 0.5 else "#ff9800"
        )
        self.result_widgets["document_filename"].configure(text=r.get("filename", "--"))
        self.result_widgets["document_saved"].configure(text=r.get("saved_path", "--"))

        ocr_text = r.get("ocr", {}).get("text", "")
        ocr_conf = r.get("ocr", {}).get("confidence", 0)
        self.result_widgets["ocr_text"].configure(
            text=ocr_text if ocr_text else "No text detected",
            text_color="gray" if not ocr_text else None
        )
        self.result_widgets["ocr_ocr_conf"].configure(text=f"{ocr_conf:.0%}")

        extracted = cls.get("extracted_data", {})
        dates = self.classifier.extract_dates(ocr_text) if ocr_text else []
        amounts = self.classifier.extract_amounts(ocr_text) if ocr_text else []

        self.result_widgets["extracted_amounts"].configure(
            text=", ".join([f"${a['value']:.2f}" for a in amounts]) if amounts else "--"
        )
        self.result_widgets["extracted_dates"].configure(
            text=", ".join(dates) if dates else "--"
        )
        self.result_widgets["extracted_entities"].configure(
            text=str(extracted) if extracted else "--"
        )

        qr_codes = r.get("qr_codes", [])
        self.result_widgets["qr_qr_data"].configure(
            text="\n".join([f"{q['type']}: {q['data'][:50]}" for q in qr_codes]) if qr_codes else "None detected"
        )

        # Photo Properties
        orig = r.get("original_image")
        if orig is not None:
            h, w = orig.shape[:2]
            self.props_widgets["dimensions"].configure(text=f"{w} × {h} px")
        saved = r.get("saved_path")
        if saved and os.path.exists(saved):
            size_bytes = os.path.getsize(saved)
            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            else:
                size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
            self.props_widgets["file_size"].configure(text=size_str)
            mtime = os.path.getmtime(saved)
            from datetime import datetime
            self.props_widgets["saved_date"].configure(
                text=datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"))
        ocr_text = r.get("ocr", {}).get("text", "")
        self.props_widgets["ocr_chars"].configure(text=f"{len(ocr_text)} chars")

    def close_analysis(self):
        self.processed_result = None
        self.captured_frame = None
        for w in list(self.result_widgets.values()):
            if w is not None:
                w.configure(text="--")
        for w in self.props_widgets.values():
            w.configure(text="--")
        self.result_orig.configure(image="", text="--")
        self.result_enhanced.configure(image="", text="--")
        self.capture_status.configure(text="Ready")
        self.show_tab("capture")

    def retake_photo(self):
        self.close_analysis()
        self.start_camera()

    # ---- Settings Tab ----
    def _build_settings_tab(self):
        tab = ctk.CTkFrame(self.main)
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        self.tabs["settings"] = tab

        scroll = ctk.CTkScrollableFrame(tab)
        scroll.grid(row=0, column=0, sticky="nsew", padx=20, pady=15)
        scroll.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(scroll, text="Settings", font=FONT_LARGE).grid(row=0, column=0, columnspan=2, pady=(0, 15), sticky="w")

        # Theme
        ctk.CTkLabel(scroll, text="Theme", font=FONT_MEDIUM).grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 5))
        theme_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        theme_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        ctk.CTkButton(theme_frame, text="🌙 Dark", command=lambda: self._set_theme("Dark")).pack(side="left", padx=5)
        ctk.CTkButton(theme_frame, text="☀️ Light", command=lambda: self._set_theme("Light")).pack(side="left", padx=5)
        ctk.CTkButton(theme_frame, text="🔄 System", command=lambda: self._set_theme("System")).pack(side="left", padx=5)

        # Storage
        ctk.CTkLabel(scroll, text="Storage", font=FONT_MEDIUM).grid(row=3, column=0, columnspan=2, sticky="w", pady=(15, 5))
        ctk.CTkLabel(scroll, text="Save Location", font=FONT_SMALL).grid(row=4, column=0, sticky="w", pady=3)
        self.settings_path = ctk.CTkEntry(scroll, placeholder_text="Default: data/")
        self.settings_path.grid(row=4, column=1, sticky="ew", pady=3)
        self.settings_path.insert(0, str(self.storage.base_dir))

        ctk.CTkButton(scroll, text="💾  Save Settings",
                       command=self._save_settings,
                       fg_color="#2d8a4e", hover_color="#236b3d"
                       ).grid(row=5, column=0, columnspan=2, pady=20)

    def _set_theme(self, mode):
        ctk.set_appearance_mode(mode)

    def _save_settings(self):
        new_path = self.settings_path.get().strip()
        if new_path and new_path != str(self.storage.base_dir):
            self.storage = LocalStorage(base_dir=new_path)

        messagebox.showinfo("Saved", "Settings saved successfully!")

    # ---- Bluetooth Camera Methods ----
    def open_bluetooth_dialog(self):
        if not BLEAK_AVAILABLE:
            messagebox.showerror("Bluetooth Unavailable", 
                "Bluetooth support not installed.\nRun: pip install bleak")
            return
            
        dialog = ctk.CTkToplevel(self.window)
        dialog.title("Bluetooth Camera")
        dialog.geometry("500x600")
        dialog.transient(self.window)
        dialog.grab_set()
        
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(2, weight=1)
        
        # Header
        header = ctk.CTkFrame(dialog, fg_color="transparent")
        header.grid(row=0, column=0, pady=10, padx=15, sticky="ew")
        ctk.CTkLabel(header, text="📱 Bluetooth Camera", font=FONT_LARGE).pack(side="left")
        ctk.CTkButton(header, text="✕", width=30, command=dialog.destroy,
                      fg_color="gray", hover_color="#666666").pack(side="right")
        
        # Status
        self.bt_status_label = ctk.CTkLabel(dialog, text="Ready to scan for Bluetooth cameras",
                                             font=FONT_SMALL, text_color="gray")
        self.bt_status_label.grid(row=1, column=0, pady=5, padx=15, sticky="ew")
        
        # Device list
        self.bt_device_frame = ctk.CTkScrollableFrame(dialog)
        self.bt_device_frame.grid(row=2, column=0, pady=5, padx=15, sticky="nsew")
        self.bt_device_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self.bt_device_frame, text="No devices found — click Scan",
                      font=FONT_SMALL, text_color="gray").pack(pady=20)
        
        # Buttons
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.grid(row=3, column=0, pady=10, padx=15, sticky="ew")
        btn_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        self.btn_bt_scan = ctk.CTkButton(btn_frame, text="🔍 Scan Devices", 
                                          command=lambda: self._scan_bluetooth_devices(dialog))
        self.btn_bt_scan.grid(row=0, column=0, padx=5)
        
        self.btn_bt_connect = ctk.CTkButton(btn_frame, text="🔗 Connect", 
                                             command=lambda: self._connect_bluetooth_device(dialog),
                                             state="disabled", fg_color="#2d8a4e")
        self.btn_bt_connect.grid(row=0, column=1, padx=5)
        
        self.btn_bt_qr = ctk.CTkButton(btn_frame, text="📱 QR Code", 
                                        command=self._show_bluetooth_qr,
                                        state="disabled", fg_color="#ff9800")
        self.btn_bt_qr.grid(row=0, column=2, padx=5)
        
        # Connected device controls (initially hidden)
        self.bt_connected_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        self.bt_connected_frame.grid(row=4, column=0, pady=5, padx=15, sticky="ew")
        self.bt_connected_frame.grid_columnconfigure((0, 1, 2), weight=1)
        self.bt_connected_frame.grid_remove()
        
        ctk.CTkButton(self.bt_connected_frame, text="📷 Capture", 
                       command=self._capture_bluetooth_frame).grid(row=0, column=0, padx=5)
        ctk.CTkButton(self.bt_connected_frame, text="▶ Stream", 
                       command=self._start_bluetooth_stream).grid(row=0, column=1, padx=5)
        ctk.CTkButton(self.bt_connected_frame, text="⏹ Stop", 
                       command=self._stop_bluetooth_stream).grid(row=0, column=2, padx=5)
        ctk.CTkButton(self.bt_connected_frame, text="📱 QR Code", 
                       command=self._show_bluetooth_qr).grid(row=1, column=0, padx=5, pady=5)
        ctk.CTkButton(self.bt_connected_frame, text="🔌 Disconnect", 
                       command=lambda: self._disconnect_bluetooth(dialog),
                       fg_color="#d32f2f", hover_color="#b71c1c").grid(row=1, column=1, padx=5, pady=5)
        
        self.selected_bt_device = None
        self.bt_device_widgets = {}

    def _scan_bluetooth_devices(self, dialog):
        self.btn_bt_scan.configure(state="disabled", text="🔍 Scanning...")
        self.bt_status_label.configure(text="Scanning for Bluetooth cameras...", text_color="#ff9800")
        
        # Clear device list
        for widget in self.bt_device_frame.winfo_children():
            widget.destroy()
        
        ctk.CTkLabel(self.bt_device_frame, text="Scanning...",
                      font=FONT_SMALL, text_color="gray").pack(pady=20)
        
        def scan_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                devices = loop.run_until_complete(
                    scan_bluetooth_cameras(duration=10.0)
                )
                loop.close()
                
                self.window.after(0, lambda: self._update_bt_device_list(devices, dialog))
            except Exception as e:
                self.window.after(0, lambda: self._bt_scan_error(str(e)))
        
        threading.Thread(target=scan_thread, daemon=True).start()
    
    def _update_bt_device_list(self, devices, dialog):
        self.btn_bt_scan.configure(state="normal", text="🔍 Scan Devices")
        
        for widget in self.bt_device_frame.winfo_children():
            widget.destroy()
        
        if not devices:
            self.bt_status_label.configure(text="No Bluetooth cameras found", text_color="#d32f2f")
            ctk.CTkLabel(self.bt_device_frame, text="No devices found",
                          font=FONT_SMALL, text_color="gray").pack(pady=20)
            return
        
        self.bt_status_label.configure(text=f"Found {len(devices)} device(s)", text_color="#2d8a4e")
        
        self.bt_device_widgets = {}
        for i, device in enumerate(devices):
            frame = ctk.CTkFrame(self.bt_device_frame)
            frame.pack(fill="x", pady=3, padx=5)
            frame.grid_columnconfigure(1, weight=1)
            
            # Radio button for selection
            rb = ctk.CTkRadioButton(frame, text="", value=device.address,
                                     command=lambda d=device: self._on_bt_device_selected(d))
            rb.grid(row=0, column=0, padx=10, pady=5)
            
            info = ctk.CTkFrame(frame, fg_color="transparent")
            info.grid(row=0, column=1, sticky="ew", padx=5)
            info.grid_columnconfigure(0, weight=1)
            
            ctk.CTkLabel(info, text=device.name, font=FONT_MEDIUM, anchor="w").grid(row=0, column=0, sticky="w")
            
            details = f"{device.address} | RSSI: {device.rssi}dBm"
            if device.battery_level is not None:
                details += f" | Battery: {device.battery_level}%"
            ctk.CTkLabel(info, text=details, font=("Segoe UI", 10), text_color="gray", anchor="w").grid(row=1, column=0, sticky="w")
            
            badge_text = "📷 CAMERA" if device.is_camera else "📱 DEVICE"
            badge_color = "#2d8a4e" if device.is_camera else "#666666"
            ctk.CTkLabel(info, text=badge_text, font=("Segoe UI", 9, "bold"), 
                          text_color=badge_color, anchor="w").grid(row=0, column=1, rowspan=2, padx=10)
            
            self.bt_device_widgets[device.address] = (rb, frame)
        
        # Select first camera device by default
        for device in devices:
            if device.is_camera:
                self._on_bt_device_selected(device)
                break
    
    def _on_bt_device_selected(self, device):
        self.selected_bt_device = device
        self.btn_bt_connect.configure(state="normal")
        
        # Update radio button selection
        for addr, (rb, frame) in self.bt_device_widgets.items():
            if addr == device.address:
                rb.select()
            else:
                rb.deselect()
    
    def _bt_scan_error(self, error):
        self.btn_bt_scan.configure(state="normal", text="🔍 Scan Devices")
        self.bt_status_label.configure(text=f"Scan error: {error}", text_color="#d32f2f")
    
    def _connect_bluetooth_device(self, dialog):
        if not self.selected_bt_device:
            return
            
        self.btn_bt_connect.configure(state="disabled", text="🔗 Connecting...")
        self.bt_status_label.configure(text=f"Connecting to {self.selected_bt_device.name}...", text_color="#ff9800")
        
        def connect_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                device = BluetoothDevice(
                    address=self.selected_bt_device.address,
                    name=self.selected_bt_device.name,
                    is_camera=True
                )
                
                connected = loop.run_until_complete(self.bluetooth_manager.connect(device))
                
                if connected:
                    config = BluetoothCameraConfig(
                        device_address=device.address,
                        device_name=device.name,
                        image_width=640,
                        image_height=480,
                        jpeg_quality=85,
                        auto_capture=True,
                        capture_interval=2.0
                    )
                    configured = loop.run_until_complete(
                        self.bluetooth_manager.configure_camera(config)
                    )
                    
                    if configured:
                        self.bluetooth_device = device
                        self.window.after(0, lambda: self._on_bt_connected(dialog))
                    else:
                        self.window.after(0, lambda: self._bt_connect_error("Failed to configure camera"))
                else:
                    self.window.after(0, lambda: self._bt_connect_error("Failed to connect"))
                    
                loop.close()
            except Exception as e:
                self.window.after(0, lambda: self._bt_connect_error(str(e)))
        
        threading.Thread(target=connect_thread, daemon=True).start()
    
    def _on_bt_connected(self, dialog):
        self.btn_bt_connect.configure(state="disabled", text="✅ Connected")
        self.btn_bt_qr.configure(state="normal")
        self.bt_status_label.configure(text=f"Connected to {self.bluetooth_device.name}", text_color="#2d8a4e")
        
        # Show connected controls
        self.bt_connected_frame.grid()
        
        # Hide device list
        self.bt_device_frame.grid_remove()
        
        # Start streaming automatically
        self._start_bluetooth_stream()
    
    def _bt_connect_error(self, error):
        self.btn_bt_connect.configure(state="normal", text="🔗 Connect")
        self.bt_status_label.configure(text=f"Connection error: {error}", text_color="#d32f2f")
    
    def _disconnect_bluetooth(self, dialog):
        if self.bluetooth_manager:
            def disconnect_thread():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.bluetooth_manager.disconnect())
                    loop.close()
                except Exception:
                    pass
            
            threading.Thread(target=disconnect_thread, daemon=True).start()
        
        self.bluetooth_device = None
        self.bluetooth_camera = None
        self.bluetooth_streaming = False
        
        self.bt_connected_frame.grid_remove()
        self.bt_device_frame.grid()
        self.btn_bt_connect.configure(state="disabled", text="🔗 Connect")
        self.btn_bt_qr.configure(state="disabled")
        self.bt_status_label.configure(text="Disconnected. Ready to scan.", text_color="gray")
        
        self.selected_bt_device = None
    
    def _capture_bluetooth_frame(self):
        if not self.bluetooth_manager or not self.bluetooth_device:
            return
            
        self.capture_status.configure(text="Capturing from Bluetooth...", text_color="#ff9800")
        
        def capture_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                frame = loop.run_until_complete(self.bluetooth_manager.capture_single())
                loop.close()
                
                if frame is not None:
                    self.window.after(0, lambda: self._on_bt_frame_captured(frame))
                else:
                    self.window.after(0, lambda: self.capture_status.configure(
                        text="Capture failed", text_color="#d32f2f"))
            except Exception as e:
                self.window.after(0, lambda: self.capture_status.configure(
                    text=f"Error: {e}", text_color="#d32f2f"))
        
        threading.Thread(target=capture_thread, daemon=True).start()
    
    def _on_bt_frame_captured(self, frame):
        self.captured_frame = frame
        self._display_frame(frame)
        self.capture_status.configure(text="Captured from Bluetooth - ready to process", text_color="#2d8a4e")
        self.btn_capture.configure(state="normal")
        messagebox.showinfo("Captured", "Frame captured from Bluetooth camera!\nClick 'Process' to analyze.")
    
    def _start_bluetooth_stream(self):
        if not self.bluetooth_manager or self.bluetooth_streaming:
            return
            
        self.bluetooth_streaming = True
        self.capture_status.configure(text="Bluetooth streaming...", text_color="#2d8a4e")
        
        def stream_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                def frame_callback(frame):
                    self.window.after(0, lambda: self._on_bt_stream_frame(frame))
                
                loop.run_until_complete(self.bluetooth_manager.start_streaming(frame_callback))
                loop.close()
            except Exception as e:
                self.window.after(0, lambda: self.capture_status.configure(
                    text=f"Stream error: {e}", text_color="#d32f2f"))
                self.bluetooth_streaming = False
        
        threading.Thread(target=stream_thread, daemon=True).start()
    
    def _on_bt_stream_frame(self, frame):
        if not self.bluetooth_streaming:
            return
        self._display_frame(frame)
        self.captured_frame = frame.copy()
    
    def _stop_bluetooth_stream(self):
        self.bluetooth_streaming = False
        if self.bluetooth_manager:
            def stop_thread():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.bluetooth_manager.stop_streaming())
                    loop.close()
                except Exception:
                    pass
            
            threading.Thread(target=stop_thread, daemon=True).start()
        
        self.capture_status.configure(text="Bluetooth stream stopped", text_color="gray")
    
    def _show_bluetooth_qr(self):
        if not self.bluetooth_device:
            return
            
        qr_base64 = create_bluetooth_qr_for_device(
            device_id=self.bluetooth_device.address.replace(":", ""),
            device_name=self.bluetooth_device.name,
            device_address=self.bluetooth_device.address
        )
        
        # Show QR code in a dialog
        qr_dialog = ctk.CTkToplevel(self.window)
        qr_dialog.title("Bluetooth Pairing QR Code")
        qr_dialog.geometry("350x450")
        qr_dialog.transient(self.window)
        qr_dialog.grab_set()
        
        ctk.CTkLabel(qr_dialog, text="Scan with Bluetooth Camera App", font=FONT_MEDIUM).pack(pady=10)
        
        # Decode and display QR code
        import base64
        from io import BytesIO
        
        img_data = base64.b64decode(qr_base64.split(",")[1])
        img = Image.open(BytesIO(img_data))
        img = img.resize((280, 280), Image.Resampling.LANCZOS)
        tk_img = ctk.CTkImage(img, size=(280, 280))
        
        qr_label = ctk.CTkLabel(qr_dialog, image=tk_img, text="")
        qr_label.pack(pady=10)
        qr_label.image = tk_img
        
        ctk.CTkLabel(qr_dialog, text=f"Device: {self.bluetooth_device.name}", 
                      font=FONT_SMALL, text_color="gray").pack()
        ctk.CTkLabel(qr_dialog, text=f"Address: {self.bluetooth_device.address}", 
                      font=("Segoe UI", 9), text_color="gray").pack(pady=5)
        
        ctk.CTkButton(qr_dialog, text="Close", command=qr_dialog.destroy,
                       fg_color="#2d8a4e").pack(pady=15)

    def run(self):
        self.window.mainloop()


if __name__ == "__main__":
    app = AIScannerGUI()
    app.run()
