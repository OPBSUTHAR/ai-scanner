import numpy as np
import pytest

from src.edge_detection.detector import EdgeDetector


@pytest.fixture
def detector():
    return EdgeDetector()


@pytest.fixture
def page_image():
    img = np.full((400, 500, 3), 30, dtype=np.uint8)
    cv2 = pytest.importorskip("cv2")
    cv2.rectangle(img, (50, 60), (450, 340), (250, 250, 250), -1)
    return img


def test_detect_edges_shape(detector, page_image):
    edges = detector.detect_edges(page_image)
    assert edges.shape[:2] == page_image.shape[:2]


def test_find_document_contour(detector, page_image):
    corners = detector.find_document_contour(page_image)
    assert corners is not None
    assert corners.shape == (4, 2)


def test_find_document_contour_none_on_blank(detector):
    img = np.full((200, 200, 3), 200, dtype=np.uint8)
    assert detector.find_document_contour(img) is None


def test_perspective_correct(detector, page_image):
    corners = detector.find_document_contour(page_image)
    out = detector.perspective_correct(page_image, corners)
    assert out.shape[0] > 0 and out.shape[1] > 0
    assert out.ndim == 3


def test_auto_crop_finds_page(detector, page_image):
    out = detector.auto_crop(page_image)
    assert out.shape[:2] != page_image.shape[:2]


def test_auto_crop_unchanged_on_blank(detector):
    img = np.full((200, 200, 3), 200, dtype=np.uint8)
    out = detector.auto_crop(img)
    assert np.array_equal(out, img)


def test_dewarp_returns_image(detector, page_image):
    out = detector.dewarp(page_image)
    assert out.ndim == 3
    assert out.shape[0] > 0
