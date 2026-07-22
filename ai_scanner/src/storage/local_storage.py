import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
import numpy as np


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


class LocalStorage:
    def __init__(self, base_dir: str = None):
        if base_dir is None:
            base_dir = Path(__file__).resolve().parent.parent.parent / "data"
        self.base_dir = Path(base_dir)
        self._ensure_dirs()

    def _ensure_dirs(self):
        for folder in ["documents", "temp", "metadata"]:
            (self.base_dir / folder).mkdir(parents=True, exist_ok=True)

    def _type_folder(self, doc_type: str) -> str:
        return self.base_dir / "documents" / doc_type.lower()

    def save_document(self, image_array, filename: str, doc_type: str = "document",
                      metadata: dict = None) -> str:
        import cv2
        folder = self._type_folder(doc_type)
        folder.mkdir(parents=True, exist_ok=True)

        filepath = str(folder / f"{filename}.png")
        cv2.imwrite(filepath, image_array)

        if metadata:
            self._save_metadata(filename, doc_type, metadata)

        return filepath

    def save_as_pdf(self, image_paths: list, filename: str, doc_type: str = "document") -> str:
        try:
            from img2pdf import convert
            folder = self._type_folder(doc_type)
            folder.mkdir(parents=True, exist_ok=True)
            pdf_path = str(folder / f"{filename}.pdf")

            with open(image_paths[0], "rb") as f:
                header = f.read(4)
            is_png = header == b'\x89PNG'

            with open(pdf_path, "wb") as f:
                f.write(convert(image_paths))

            return pdf_path
        except Exception:
            return ""

    def _save_metadata(self, filename: str, doc_type: str, metadata: dict):
        meta_path = self.base_dir / "metadata" / f"{filename}.json"
        metadata.update({
            "filename": filename,
            "type": doc_type,
            "saved_at": datetime.now().isoformat(),
        })
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2, cls=NumpyEncoder)

    def get_metadata(self, filename: str) -> Optional[dict]:
        meta_path = self.base_dir / "metadata" / f"{filename}.json"
        if meta_path.exists():
            with open(meta_path) as f:
                return json.load(f)
        return None

    def list_documents(self, doc_type: str = None) -> list:
        if doc_type:
            folder = self._type_folder(doc_type)
            if not folder.exists():
                return []
            return [str(p) for p in folder.iterdir() if p.is_file()]

        all_files = []
        docs_dir = self.base_dir / "documents"
        if docs_dir.exists():
            for sub in docs_dir.iterdir():
                if sub.is_dir():
                    all_files.extend([str(p) for p in sub.iterdir() if p.is_file()])
        return all_files
