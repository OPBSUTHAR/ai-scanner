import numpy as np
import pytest

from src.camera.capture import CameraCapture, CaptureResult


@pytest.fixture
def camera():
    return CameraCapture(camera_id=9999)


@pytest.fixture
def synthetic_frame():
    img = np.full((480, 640, 3), 20, dtype=np.uint8)
    cv2 = pytest.importorskip("cv2")
    cv2.rectangle(img, (80, 100), (560, 380), (255, 255, 255), -1)
    return img


def test_capture_result_dataclass():
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    r = CaptureResult(frame=frame, success=True)
    assert r.success
    assert r.corners is None


def test_auto_detect_document_finds_page(camera, synthetic_frame):
    result = camera.auto_detect_document(synthetic_frame)
    assert result.success
    assert result.corners is not None
    assert result.corners.shape == (4, 2)


def test_auto_detect_blank_frame(camera):
    img = np.full((200, 200, 3), 128, dtype=np.uint8)
    result = camera.auto_detect_document(img)
    assert result.success
    assert result.corners is None


def test_draw_detection_returns_frame(camera, synthetic_frame):
    result = camera.auto_detect_document(synthetic_frame)
    drawn = camera.draw_detection(result.frame, result.corners)
    assert drawn.shape == synthetic_frame.shape


def test_capture_frame_without_open_returns_none(camera):
    assert camera.capture_frame() is None


def test_order_corners_consistency(camera, synthetic_frame):
    result = camera.auto_detect_document(synthetic_frame)
    pts = result.corners
    xs = pts[:, 0]
    ys = pts[:, 1]
    assert pts.shape == (4, 2)
    assert xs.min() >= 0 and xs.max() <= 640
    assert ys.min() >= 0 and ys.max() <= 480
