import re
from datetime import datetime
from typing import Optional


class AutoNamer:
    def generate_name(self, doc_type: str, extracted_data: dict, ocr_text: str = "") -> str:
        parts = [doc_type.capitalize()]

        entity = self._extract_entity(ocr_text, extracted_data)
        if entity:
            parts.append(entity)

        date_str = self._extract_date_for_name(ocr_text, extracted_data)
        if date_str:
            parts.append(date_str)
        else:
            parts.append(datetime.now().strftime("%b%d"))

        amount = extracted_data.get("amount", "")
        if amount:
            clean = re.sub(r'[^\d.]', "", amount)
            parts.append(f"${clean}")

        name = "_".join(parts)
        name = re.sub(r'[<>:"/\\|?*]', "", name)
        name = re.sub(r'\s+', "_", name).strip("_")
        return name if name else f"document_{datetime.now():%Y%m%d_%H%M%S}"

    def _extract_entity(self, text: str, data: dict) -> Optional[str]:
        for key in ["merchant", "party", "name"]:
            if key in data and data[key]:
                return data[key].strip().split("\n")[0][:30]
        if text:
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            for line in lines[:3]:
                if re.match(r'^[A-Z][a-zA-Z\s&.]+$', line) and len(line) > 5:
                    return line[:30]
        return None

    def _extract_date_for_name(self, text: str, data: dict) -> Optional[str]:
        date_str = data.get("date") or data.get("due_date") or data.get("date_of_birth")
        if date_str:
            clean = re.sub(r'[^0-9]', "", date_str)
            if len(clean) >= 6:
                return clean[:8]
        return None
