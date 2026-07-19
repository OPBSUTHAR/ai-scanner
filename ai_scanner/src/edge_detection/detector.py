import cv2
import numpy as np
from typing import Optional, Tuple


class EdgeDetector:
    def __init__(self):
        self.canny_low = 75
        self.canny_high = 200

    def detect_edges(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        return cv2.Canny(blurred, self.canny_low, self.canny_high)

    def find_document_contour(self, image: np.ndarray) -> Optional[np.ndarray]:
        edged = self.detect_edges(image)
        contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

        for contour in contours:
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
            if len(approx) == 4:
                return self._order_corners(approx)
        return None

    def _order_corners(self, pts: np.ndarray) -> np.ndarray:
        rect = np.zeros((4, 2), dtype=np.float32)
        s = pts.sum(axis=2).flatten()
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]

        diff = np.diff(pts, axis=2).flatten()
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        return rect

    def perspective_correct(self, image: np.ndarray, corners: np.ndarray) -> np.ndarray:
        (tl, tr, br, bl) = corners
        width_a = np.linalg.norm(br - bl)
        width_b = np.linalg.norm(tr - tl)
        max_width = max(int(width_a), int(width_b))

        height_a = np.linalg.norm(tr - br)
        height_b = np.linalg.norm(tl - bl)
        max_height = max(int(height_a), int(height_b))

        dst = np.array([
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1],
        ], dtype=np.float32)

        M = cv2.getPerspectiveTransform(corners, dst)
        return cv2.warpPerspective(image, M, (max_width, max_height))

    def dewarp(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY, 11, 2)

        kernel = np.ones((5, 5), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return image

        all_pts = np.vstack(contours)
        hull = cv2.convexHull(all_pts)

        corners = cv2.approxPolyDP(hull, 0.02 * cv2.arcLength(hull, True), True)
        if len(corners) < 4:
            return image

        ordered = self._order_corners(corners[:4].reshape(4, 1, 2))
        return self.perspective_correct(image, ordered)

    def auto_crop(self, image: np.ndarray) -> np.ndarray:
        corners = self.find_document_contour(image)
        if corners is not None:
            return self.perspective_correct(image, corners)
        return image
