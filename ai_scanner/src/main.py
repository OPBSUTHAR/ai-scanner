import os
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.camera.capture import CameraCapture
from src.edge_detection.detector import EdgeDetector
from src.enhancement.enhancer import ImageEnhancer
from src.ocr.ocr_engine import OCREngine
from src.classification.classifier import DocumentClassifier
from src.storage.local_storage import LocalStorage
from src.storage.cloud_sync import CloudSync
from src.utils.auto_naming import AutoNamer
from src.utils.qr_detection import QRDetector
from src.utils.search import DocumentSearch


class AIScanner:
    def __init__(self):
        self.camera = CameraCapture()
        self.edges = EdgeDetector()
        self.enhancer = ImageEnhancer()
        self.ocr = OCREngine()
        self.classifier = DocumentClassifier()
        self.storage = LocalStorage()
        self.cloud = CloudSync()
        self.namer = AutoNamer()
        self.qr = QRDetector()
        self.searcher = DocumentSearch()

    def capture_and_process(self, image_path: str = None) -> dict:
        if image_path:
            import cv2
            image = cv2.imread(image_path)
            if image is None:
                return {"error": f"Cannot read image: {image_path}"}
        else:
            if not self.camera.open():
                return {"error": "Cannot open camera"}
            result = self.camera.capture_frame()
            if result is None:
                return {"error": "Failed to capture frame"}
            image = result
            self.camera.release()

        result = {"original_shape": image.shape}

        quality = self.enhancer.quality_assessment(image)
        result["quality"] = quality

        if quality["is_blurry"]:
            print("Blur detected, skipping...")
            result["warning"] = "Blurry image"
            return result

        corners = self.edges.find_document_contour(image)
        if corners is not None:
            result["document_detected"] = True
            corrected = self.edges.perspective_correct(image, corners)
        else:
            result["document_detected"] = False
            corrected = image

        enhanced = self.enhancer.enhance_document(corrected)
        result["enhanced"] = True

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

        return result

    def process_file(self, image_path: str):
        print(f"\nProcessing: {image_path}")
        result = self.capture_and_process(image_path=image_path)
        self._print_result(result)
        return result

    def process_camera(self):
        print("\nStarting camera capture...")
        if not self.camera.open():
            print("Cannot open camera")
            return

        print("Press SPACE to capture, ESC to exit")
        import cv2
        while True:
            frame = self.camera.capture_frame()
            if frame is None:
                break

            result = self.camera.auto_detect_document(frame)
            display = self.camera.draw_detection(result.frame, result.corners)
            cv2.imshow("AI Scanner - Press SPACE to capture", display)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                break
            elif key == 32:
                self.camera.release()
                processed = self.capture_and_process()
                self._print_result(processed)
                return processed

        self.camera.release()

    def _print_result(self, result: dict):
        print("\n=== Scan Result ===")
        if "error" in result:
            print(f"ERROR: {result['error']}")
            return

        print(f"Quality: {'PASS' if result['quality']['quality_pass'] else 'FAIL'}")
        print(f"  Blur: {result['quality']['blur_score']}")
        print(f"  Brightness: {result['quality']['brightness']}")

        print(f"Document Detected: {result.get('document_detected', False)}")
        print(f"OCR Text: {result['ocr']['text'][:200] if result['ocr']['text'] else 'None'}")
        print(f"OCR Confidence: {result['ocr']['confidence']:.2f}")

        cls = result.get("classification", {})
        print(f"Document Type: {cls.get('type', 'N/A')} ({cls.get('confidence', 0):.2f})")
        if cls.get("extracted_data"):
            print(f"Extracted: {cls['extracted_data']}")

        qr = result.get("qr_codes", [])
        if qr:
            for q in qr:
                print(f"QR/Barcode: {q['type']} -> {q['data'][:80]}")

        print(f"Saved: {result.get('saved_path', 'N/A')}")
        print(f"Filename: {result.get('filename', 'N/A')}")
        print("===================\n")


def main():
    parser = argparse.ArgumentParser(description="AI Document Scanner")
    parser.add_argument("--image", "-i", help="Process an image file")
    parser.add_argument("--camera", "-c", action="store_true", help="Capture from camera")
    parser.add_argument("--preview", "-p", action="store_true", help="Preview camera with edge detection")
    args = parser.parse_args()

    scanner = AIScanner()

    if args.image:
        scanner.process_file(args.image)
    elif args.preview:
        cam = CameraCapture()
        cam.preview()
    elif args.camera:
        scanner.process_camera()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
