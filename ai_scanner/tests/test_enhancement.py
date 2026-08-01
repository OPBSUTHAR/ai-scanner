import numpy as np
import pytest

from src.enhancement.enhancer import ImageEnhancer


@pytest.fixture
def enhancer():
    return ImageEnhancer()


@pytest.fixture
def sample_image():
    rng = np.random.default_rng(42)
    img = np.full((200, 300, 3), 200, dtype=np.uint8)
    noise = rng.integers(0, 40, (200, 300, 3), dtype=np.uint8)
    return np.clip(img + noise, 0, 255).astype(np.uint8)


def test_enhance_document_shape(enhancer, sample_image):
    out = enhancer.enhance_document(sample_image)
    assert out.shape == sample_image.shape
    assert out.dtype == sample_image.dtype


def test_enhance_document_changes_pixels(enhancer, sample_image):
    out = enhancer.enhance_document(sample_image)
    assert not np.array_equal(out, sample_image)


def test_auto_contrast(enhancer, sample_image):
    out = enhancer.auto_contrast(sample_image)
    assert out.shape == sample_image.shape


def test_sharpen(enhancer, sample_image):
    out = enhancer.sharpen(sample_image)
    assert out.shape == sample_image.shape


def test_remove_shadow(enhancer, sample_image):
    out = enhancer.remove_shadow(sample_image)
    assert out.shape == sample_image.shape


def test_detect_blur_sharp_image(enhancer):
    img = np.zeros((200, 300, 3), dtype=np.uint8)
    cv2 = pytest.importorskip("cv2")
    cv2.rectangle(img, (30, 30), (270, 170), (255, 255, 255), 5)
    is_blurry, score = enhancer.detect_blur(img)
    assert score > 0
    assert isinstance(is_blurry, bool)


def test_quality_assessment_keys(enhancer, sample_image):
    q = enhancer.quality_assessment(sample_image)
    for key in ["is_blurry", "blur_score", "good_lighting", "brightness",
                "resolution_score", "quality_pass"]:
        assert key in q


def test_multi_shot_fusion_single(enhancer, sample_image):
    out = enhancer.multi_shot_fusion([sample_image])
    assert np.array_equal(out, sample_image)


def test_multi_shot_fusion_multiple(enhancer, sample_image):
    shifted = np.roll(sample_image, 1, axis=1)
    out = enhancer.multi_shot_fusion([sample_image, shifted])
    assert out.shape == sample_image.shape
    assert out.dtype == np.uint8


def test_multi_shot_fusion_empty(enhancer):
    with pytest.raises(ValueError):
        enhancer.multi_shot_fusion([])
