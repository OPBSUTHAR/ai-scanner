import re
import json
import os
from typing import List, Dict
from dataclasses import dataclass


@dataclass
class SearchResult:
    filename: str
    filepath: str
    score: float
    matches: List[str] = None


class DocumentSearch:
    def __init__(self, index_path: str = None):
        self.index_path = index_path
        self.index: Dict[str, dict] = {}

    def build_index(self, scan_dir: str):
        self.index = {}
        for root, _, files in os.walk(scan_dir):
            for fname in files:
                if fname.endswith((".txt", ".json")):
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            content = f.read()
                        self.index[fname] = {
                            "path": fpath,
                            "content": content,
                            "type": self._detect_type(fname),
                        }
                    except Exception:
                        pass

    def _detect_type(self, filename: str) -> str:
        for t in ["invoice", "receipt", "contract", "id"]:
            if t in filename.lower():
                return t
        return "document"

    def search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        if not self.index:
            return []

        terms = query.lower().split()
        results = []

        for fname, data in self.index.items():
            content_lower = data["content"].lower()
            score = 0
            matches = []

            for term in terms:
                count = content_lower.count(term)
                if count > 0:
                    score += count * 10
                    matches.append(term)

            fname_lower = fname.lower()
            for term in terms:
                if term in fname_lower:
                    score += 20

            if query.lower() in content_lower:
                score += 5

            if score > 0:
                results.append(SearchResult(
                    filename=fname,
                    filepath=data["path"],
                    score=score,
                    matches=list(set(matches)),
                ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def fuzzy_search(self, query: str, threshold: int = 60) -> List[SearchResult]:
        results = self.search(query)
        return results
