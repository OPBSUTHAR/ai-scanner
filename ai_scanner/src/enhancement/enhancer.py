import cv2
import numpy as np
from typing import Tuple


class ImageEnhancer:
    def auto_contrast(self, image: np.ndarray) -> np.ndarray:
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        enhanced = cv2.merge([l, a, b])
        return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

    def sharpen(self, image: np.ndarray) -> np.ndarray:
        kernel = np.array([
            [0, -1, 0],
            [-1, 5, -1],
            [0, -1, 0]
        ], dtype=np.float32)
        return cv2.filter2D(image, -1, kernel)

    def remove_shadow(self, image: np.ndarray) -> np.ndarray:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        dilated = cv2.dilate(rgb, np.ones((7, 7), np.uint8), iterations=3)
        bg = cv2.medianBlur(dilated, 21)
        diff = 255 - cv2.absdiff(rgb, bg)
        norm = cv2.normalize(diff, None, 0, 255, cv2.NORM_MINMAX)
        return cv2.cvtColor(norm, cv2.COLOR_RGB2BGR)

    def detect_blur(self, image: np.ndarray, threshold: float = 100.0) -> Tuple[bool, float]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        return laplacian_var < threshold, laplacian_var

    def check_lighting(self, image: np.ndarray) -> Tuple[bool, float]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        mean_brightness = gray.mean()
        return 30 <= mean_brightness <= 240, mean_brightness

    def quality_assessment(self, image: np.ndarray) -> dict:
        is_blurry, blur_score = self.detect_blur(image)
        good_lighting, brightness = self.check_lighting(image)
        h, w = image.shape[:2]
        resolution_score = min(1.0, (h * w) / (1920 * 1080))

        return {
            "is_blurry": is_blurry,
            "blur_score": round(blur_score, 2),
            "good_lighting": good_lighting,
            "brightness": round(brightness, 1),
            "resolution_score": round(resolution_score, 2),
            "quality_pass": not is_blurry and good_lighting,
        }

    def multi_shot_fusion(self, images: list) -> np.ndarray:
        if not images:
            raise ValueError("No images provided")
        if len(images) == 1:
            return images[0]

        aligned = []
        gray_ref = cv2.cvtColor(images[0], cv2.COLOR_BGR2GRAY)
        for img in images[1:]:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            warp_matrix = np.eye(2, 3, dtype=np.float32)
            criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 50, 1e-5)
            _, warp_matrix = cv2.findTransformECC(gray_ref, gray, warp_matrix, cv2.MOTION_AFFINE, criteria)
            aligned_img = cv2.warpAffine(img, warp_matrix, (images[0].shape[1], images[0].shape[0]),
                                          borderMode=cv2.BORDER_REPLICATE)
            aligned.append(aligned_img)

        aligned.insert(0, images[0])
        return np.median(aligned, axis=0).astype(np.uint8)

    def enhance_document(self, image: np.ndarray) -> np.ndarray:
        result = self.remove_shadow(image)
        result = self.auto_contrast(result)
        result = self.sharpen(result)
        return result
