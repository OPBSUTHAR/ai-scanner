from src.classification.classifier import DocumentClassifier, ClassificationResult


def test_invoice_classification():
    cls = DocumentClassifier()
    text = "INVOICE #12345\nAmount Due: $150.00\nDue Date: 15 March 2026"
    result = cls.classify(text)
    assert result.doc_type == "invoice"
    assert result.confidence > 0
    assert "amount" in result.extracted_data


def test_receipt_classification():
    cls = DocumentClassifier()
    text = "Thank you for your purchase\nTotal: $24.99\nCash: $30.00"
    result = cls.classify(text)
    assert result.doc_type == "receipt"
    assert "amount" in result.extracted_data


def test_id_classification():
    cls = DocumentClassifier()
    text = "Driver License\nName: John Smith\nDate of Birth: 05/14/1990\nID: 55544321"
    result = cls.classify(text)
    assert result.doc_type == "id"
    assert "name" in result.extracted_data


def test_contract_classification():
    cls = DocumentClassifier()
    text = "This Agreement between Party A and Party B\nEffective Date: 1 January 2026"
    result = cls.classify(text)
    assert result.doc_type == "contract"


def test_unknown_classification():
    cls = DocumentClassifier()
    text = "hello world random words without meaning"
    result = cls.classify(text)
    assert result.doc_type == "unknown"


def test_empty_text():
    cls = DocumentClassifier()
    result = cls.classify("")
    assert result.doc_type == "unknown"
    assert result.confidence == 0.0


def test_extract_amounts():
    cls = DocumentClassifier()
    amounts = cls.extract_amounts("Total $1,234.56 and 12.00")
    values = [a["value"] for a in amounts]
    assert 1234.56 in values
    assert 12.0 in values


def test_extract_dates():
    cls = DocumentClassifier()
    dates = cls.extract_dates("Date: 12/05/2026 and Jan 3, 2027")
    assert len(dates) >= 2


def test_result_dataclass():
    r = ClassificationResult(doc_type="invoice", confidence=0.8)
    assert r.doc_type == "invoice"
    assert r.extracted_data == {}
