import re
import numpy as np
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class OCRResult:
    text: str
    confidence: float
    engine: str
    words: List[dict] = None


class OCREngine:
    def __init__(self, use_google_vision: bool = False, tesseract_cmd: str = None):
        self.use_google_vision = use_google_vision
        self.tesseract_available = False
        self.vision_client = None
        self.easyocr_reader = None

        if tesseract_cmd:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            self.tesseract_available = True
        except Exception:
            pass

    def _tesseract_ocr(self, image: np.ndarray) -> OCRResult:
        import pytesseract
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        text = " ".join([w for w in data["text"] if w.strip()])
        confs = [c for c in data["conf"] if c != -1]
        avg_conf = sum(confs) / len(confs) if confs else 0.0

        words = [
            {"text": data["text"][i], "conf": data["conf"][i],
             "x": data["left"][i], "y": data["top"][i],
             "w": data["width"][i], "h": data["height"][i]}
            for i in range(len(data["text"])) if data["text"][i].strip()
        ]

        return OCRResult(text=text.strip(), confidence=avg_conf / 100.0,
                         engine="tesseract", words=words)

    def _google_vision_ocr(self, image: np.ndarray) -> OCRResult:
        try:
            from google.cloud import vision
            if self.vision_client is None:
                self.vision_client = vision.ImageAnnotatorClient()

            success, encoded = cv2.imencode(".png", image)
            content = encoded.tobytes()
            vision_image = vision.Image(content=content)
            response = self.vision_client.document_text_detection(image=vision_image)

            if response.error.message:
                raise RuntimeError(response.error.message)

            text = response.full_text_annotation.text
            confidence = 0.0
            words = []

            for page in response.full_text_annotation.pages:
                for block in page.blocks:
                    for paragraph in block.paragraphs:
                        for word in paragraph.words:
                            word_text = "".join([s.text for s in word.symbols])
                            if word_text.strip():
                                words.append({
                                    "text": word_text,
                                    "conf": word.confidence,
                                })
                                confidence += word.confidence

            confidence = confidence / len(words) if words else 0.0
            return OCRResult(text=text.strip(), confidence=confidence,
                             engine="google_vision", words=words)

        except Exception:
            return OCRResult(text="", confidence=0.0, engine="google_vision")

    def _handwriting_ocr(self, image: np.ndarray) -> OCRResult:
        try:
            import easyocr
            if self.easyocr_reader is None:
                self.easyocr_reader = easyocr.Reader(["en"])
            results = self.easyocr_reader.readtext(image)
            text = " ".join([r[1] for r in results])
            confs = [r[2] for r in results]
            avg_conf = sum(confs) / len(confs) if confs else 0.0

            words = [
                {"text": r[1], "conf": r[2], "bbox": r[0]}
                for r in results
            ]
            return OCRResult(text=text.strip(), confidence=avg_conf,
                             engine="easyocr", words=words)
        except Exception:
            return OCRResult(text="", confidence=0.0, engine="easyocr")

    def extract_text(self, image: np.ndarray, use_handwriting: bool = False) -> OCRResult:
        if self.use_google_vision:
            result = self._google_vision_ocr(image)
            if result.text:
                return result

        if self.tesseract_available:
            result = self._tesseract_ocr(image)
            if result.text:
                return result

        if use_handwriting:
            result = self._handwriting_ocr(image)
            if result.text:
                return result

        return OCRResult(text="", confidence=0.0, engine="none")

    def is_handwritten(self, image: np.ndarray) -> bool:
        if self.tesseract_available:
            import pytesseract
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            text = " ".join([w for w in data["text"] if w.strip()])
            if len(text) > 10:
                return False
        return True
