import numpy as np
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class CodeResult:
    data: str
    type: str
    rect: list = None


class QRDetector:
    def __init__(self):
        self.qr_detector = None

    def detect(self, image: np.ndarray) -> List[CodeResult]:
        results = []

        try:
            from pyzbar import pyzbar
            decoded = pyzbar.decode(image)
            for code in decoded:
                results.append(CodeResult(
                    data=code.data.decode("utf-8", errors="replace"),
                    type=code.type,
                    rect=code.rect,
                ))
        except Exception:
            pass

        try:
            import cv2
            if self.qr_detector is None:
                self.qr_detector = cv2.QRCodeDetector()
            data, points, _ = self.qr_detector.detectAndDecode(image)
            if data:
                already = any(r.data == data for r in results)
                if not already:
                    results.append(CodeResult(
                        data=data,
                        type="QRCODE",
                        rect=points.tolist() if points is not None else None,
                    ))
        except Exception:
            pass

        return results

    def decode_data(self, results: List[CodeResult]) -> dict:
        info = {}
        for r in results:
            data = r.data
            if r.type in ("QRCODE", "AZTEC"):
                if "://" in data or data.startswith("mailto:"):
                    info["url"] = data
                elif data.startswith("BEGIN:"):
                    parts = data.split("\n")
                    for part in parts:
                        if ":" in part:
                            key, val = part.split(":", 1)
                            info[key.strip().lower()] = val.strip()
                else:
                    info["text"] = data
            elif r.type in ("CODE128", "CODE39", "EAN13", "UPC_A", "UPC_E"):
                info["barcode"] = data
            else:
                info[r.type.lower()] = data
        return info
