import numpy as np
import pytest

from src.ocr.ocr_engine import OCREngine, OCRResult


@pytest.fixture
def engine():
    return OCREngine()


@pytest.fixture
def text_image():
    import cv2
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (600, 200), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
        draw.text((20, 80), "INVOICE TEST 2026", fill="black", font=font)
    except Exception:
        draw.text((20, 80), "INVOICE TEST 2026", fill="black")
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def test_ocr_result_dataclass():
    r = OCRResult(text="abc", confidence=0.9, engine="tesseract")
    assert r.text == "abc"
    assert r.confidence == 0.9
    assert r.engine == "tesseract"


def test_extract_text_returns_ocrresult(engine, text_image):
    result = engine.extract_text(text_image)
    assert isinstance(result, OCRResult)
    assert isinstance(result.text, str)


@pytest.mark.skipif(
    not OCREngine().tesseract_available,
    reason="Tesseract not installed",
)
def test_tesseract_reads_known_text(engine, text_image):
    result = engine.extract_text(text_image)
    assert result.engine == "tesseract"
    assert "INVOICE" in result.text.upper() or "TEST" in result.text.upper()


def test_handwriting_flag_passed(engine, text_image):
    result = engine.extract_text(text_image, use_handwriting=True)
    assert isinstance(result, OCRResult)


def test_blank_image_graceful():
    import cv2
    engine = OCREngine()
    blank = np.full((100, 100, 3), 255, dtype=np.uint8)
    result = engine.extract_text(cv2.GaussianBlur(blank, (9, 9), 0))
    assert isinstance(result.text, str)


def test_is_handwritten_returns_bool(engine, text_image):
    assert isinstance(engine.is_handwritten(text_image), bool)
