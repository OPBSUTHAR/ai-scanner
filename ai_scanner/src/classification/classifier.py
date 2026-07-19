import re
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class ClassificationResult:
    doc_type: str
    confidence: float
    extracted_data: dict = field(default_factory=dict)


class DocumentClassifier:
    DOCUMENT_PATTERNS = {
        "invoice": {
            "keywords": ["invoice", "bill", "amount due", "total due", "payment terms",
                         "invoice number", "invoice #", "due date"],
            "patterns": [
                (r'(?:total|amount|sum)\s*(?:due|:|$)?\s*[\$£€]?\s*([\d,]+\.?\d*)', "amount"),
                (r'(?:invoice|inv)\s*(?:#|number|no|:)?\s*([\w-]+)', "invoice_number"),
                (r'(?:due\s*date|payment\s*due)[:\s]+([\w\s,]+)', "due_date"),
            ]
        },
        "receipt": {
            "keywords": ["receipt", "thank you", "store", "purchase", "total", "change",
                         "cash", "credit", "debit", "sale"],
            "patterns": [
                (r'(?:total|amount)\s*[\$£€]?\s*([\d,]+\.?\d*)', "amount"),
                (r'(?:date|datetime)[:\s]+([\d/\-\.\s:]+)', "date"),
                (r'(?:store|merchant|seller)[:\s]+([A-Za-z\s]+)', "merchant"),
            ]
        },
        "id": {
            "keywords": ["identification", "id card", "passport", "driver license",
                         "driver's license", "driving license", "date of birth",
                         "id number", "national id", "social security"],
            "patterns": [
                (r'(?:name|full name)[:\s]+([A-Za-z\s,]+)', "name"),
                (r'(?:date of birth|dob|birth)[:\s]+([\d/\-\.]+)', "date_of_birth"),
                (r'(?:id|number|no)[:\s]*([A-Z0-9-]+)', "id_number"),
                (r'(?:expiry|expiration|valid until|exp)[:\s]+([\d/\-\.]+)', "expiry_date"),
            ]
        },
        "contract": {
            "keywords": ["agreement", "contract", "terms", "conditions", "party",
                         "hereby", "witness", "effective date", "signature",
                         "termination", "liability", "confidential"],
            "patterns": [
                (r'(?:effective|commencement|agreement)\s*date[:\s]+([\w\s,]+)', "date"),
                (r'(?:party|between)[:\s]+([A-Za-z\s,]+)', "party"),
                (r'(?:termination|expiry)[:\s]+([\w\s,]+)', "termination_date"),
            ]
        }
    }

    def classify(self, text: str) -> ClassificationResult:
        if not text.strip():
            return ClassificationResult(doc_type="unknown", confidence=0.0)

        scores = {}
        extracted = {}

        for doc_type, config in self.DOCUMENT_PATTERNS.items():
            score = 0
            text_lower = text.lower()

            for kw in config["keywords"]:
                if kw in text_lower:
                    score += 1

            for pattern, label in config["patterns"]:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    score += 2
                    if label not in extracted:
                        extracted[label] = match.group(1).strip()

            max_possible = len(config["keywords"]) + 2 * len(config["patterns"])
            scores[doc_type] = score / max_possible if max_possible > 0 else 0

        if not scores:
            return ClassificationResult(doc_type="unknown", confidence=0.0)

        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]

        if best_score < 0.15:
            return ClassificationResult(doc_type="unknown", confidence=best_score)

        return ClassificationResult(
            doc_type=best_type,
            confidence=best_score,
            extracted_data=extracted,
        )

    def extract_dates(self, text: str) -> List[str]:
        patterns = [
            r'\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}',
            r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}',
            r'\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2}',
        ]
        dates = []
        for p in patterns:
            dates.extend(re.findall(p, text, re.IGNORECASE))
        return dates

    def extract_amounts(self, text: str) -> List[dict]:
        pattern = r'[\$£€]?\s*(\d{1,3}(?:,\d{3})*\.\d{2})'
        amounts = []
        for match in re.finditer(pattern, text):
            amounts.append({
                "value": float(match.group(1).replace(",", "")),
                "raw": match.group(0),
            })
        return amounts
