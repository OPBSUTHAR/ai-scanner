import cv2
import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class CaptureResult:
    frame: np.ndarray
    success: bool
    document_contour: Optional[np.ndarray] = None
    corners: Optional[np.ndarray] = None


class CameraCapture:
    def __init__(self, camera_id: int = 0, width: int = 1920, height: int = 1080):
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self.cap: Optional[cv2.VideoCapture] = None

    def open(self) -> bool:
        self.cap = cv2.VideoCapture(self.camera_id)
        if not self.cap.isOpened():
            return False
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        return True

    def capture_frame(self) -> Optional[np.ndarray]:
        if self.cap is None:
            return None
        ret, frame = self.cap.read()
        return frame if ret else None

    def auto_detect_document(self, frame: np.ndarray) -> CaptureResult:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 75, 200)

        contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

        document_contour = None
        corners = None

        for contour in contours:
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
            if len(approx) == 4:
                document_contour = approx
                corners = self._order_corners(approx)
                break

        return CaptureResult(
            frame=frame,
            success=True,
            document_contour=document_contour,
            corners=corners,
        )

    def _order_corners(self, pts: np.ndarray) -> np.ndarray:
        rect = np.zeros((4, 2), dtype=np.float32)
        s = pts.sum(axis=2).flatten()
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]

        diff = np.diff(pts, axis=2).flatten()
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        return rect

    def draw_detection(self, frame: np.ndarray, corners: np.ndarray) -> np.ndarray:
        result = frame.copy()
        if corners is not None:
            pts = corners.reshape((-1, 1, 2)).astype(np.int32)
            cv2.polylines(result, [pts], True, (0, 255, 0), 3)
            for pt in corners:
                cv2.circle(result, tuple(pt.astype(int)), 8, (0, 0, 255), -1)
        return result

    def preview(self):
        if not self.open():
            print("Cannot open camera")
            return

        print("Press SPACE to capture, ESC to exit")
        while True:
            frame = self.capture_frame()
            if frame is None:
                break

            result = self.auto_detect_document(frame)
            display = self.draw_detection(result.frame, result.corners)
            cv2.imshow("AI Scanner - Document Capture", display)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                break
            elif key == 32:
                return result

        self.release()
        return None

    def release(self):
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()
