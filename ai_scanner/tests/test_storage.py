import json
import numpy as np
import pytest

from src.storage.local_storage import LocalStorage


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(base_dir=str(tmp_path / "data"))


@pytest.fixture
def image():
    return np.full((100, 100, 3), 200, dtype=np.uint8)


def test_default_base_dir_is_inside_project():
    storage = LocalStorage()
    assert "ai_scanner" in str(storage.base_dir).replace("\\", "/")
    assert (storage.base_dir / "documents").exists()


def test_save_document_creates_file(storage, image):
    path = storage.save_document(image, "test_doc", "invoice")
    assert path.endswith(".png")
    assert storage.base_dir.joinpath("documents/invoice/test_doc.png").exists()


def test_save_document_writes_metadata(storage, image):
    storage.save_document(image, "meta_doc", "receipt",
                          {"ocr_text": "hello", "quality": {"pass": True}})
    meta = storage.get_metadata("meta_doc")
    assert meta is not None
    assert meta["type"] == "receipt"
    assert meta["ocr_text"] == "hello"


def test_save_document_handles_numpy_values(storage, image):
    storage.save_document(image, "np_doc", "document",
                          {"blur_score": np.float32(12.5), "count": np.int64(3)})
    meta = storage.get_metadata("np_doc")
    assert meta["blur_score"] == 12.5
    assert meta["count"] == 3


def test_get_metadata_missing(storage):
    assert storage.get_metadata("nope") is None


def test_list_documents_by_type(storage, image):
    storage.save_document(image, "a", "invoice")
    storage.save_document(image, "b", "invoice")
    storage.save_document(image, "c", "receipt")
    docs = storage.list_documents("invoice")
    assert len(docs) == 2
    assert all("invoice" in d for d in docs)


def test_list_all_documents(storage, image):
    storage.save_document(image, "a", "invoice")
    storage.save_document(image, "b", "contract")
    assert len(storage.list_documents()) == 2


def test_doc_type_folder_is_lowercased(storage, image):
    storage.save_document(image, "x", "ID")
    assert storage.base_dir.joinpath("documents/id/x.png").exists()
