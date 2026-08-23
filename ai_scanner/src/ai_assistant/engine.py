"""Local AI Assistant — 100% free, no API keys, open-source models.

Provider chain (first available wins):
  1. Ollama      — local open-source LLM runtime (llama3.2, phi3, gemma, mistral...)
                   Install from https://ollama.com then `ollama pull llama3.2`
  2. Transformers— google/flan-t5-small (Apache-2.0, ~300MB) downloaded once
                   from the Hugging Face Hub, then runs fully offline.
  3. Builtin     — rule-based helper that answers app-usage questions and can
                   summarize/answer from provided document context. Always works.
"""

import os
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import requests

OLLAMA_PREFERRED_MODELS = [
    "llama3.2", "llama3.1", "llama3", "phi3", "phi4",
    "gemma2", "gemma", "qwen2.5", "mistral", "tinyllama",
]

SYSTEM_PROMPT = (
    "You are the built-in assistant of AI Scanner, a document scanning app. "
    "You help users scan, organize and understand their documents "
    "(invoices, receipts, IDs, contracts). Be concise and practical."
)

USAGE_HELP = {
    "merge": (
        "To merge documents into one PDF: open the VAULT, select 2+ documents "
        "with the checkbox on each card, then press MERGE PDF. Merged files land "
        "in the 'merged' folder."
    ),
    "search": (
        "Use the search box in the top bar — it searches OCR text inside every "
        "scanned document plus filenames and categories."
    ),
    "cloud": (
        "Cloud sync: Settings -> Cloud Sync -> CONNECT next to Google Drive / "
        "Dropbox / OneDrive. You need your own API keys (Settings -> API Keys). "
        "Scanning itself is 100% local and needs no keys."
    ),
    "api key|keys": (
        "API keys live in Settings -> API Keys. They are only needed for optional "
        "services: Google Vision OCR and cloud sync. Tesseract OCR and this AI "
        "assistant work without any keys."
    ),
    "ocr": (
        "OCR runs automatically on every processed scan. Tesseract is used when "
        "installed; Google Vision if its key is configured; EasyOCR handles "
        "handwriting when the toggle is enabled."
    ),
    "scan|camera|phone": (
        "Scan options: upload files, Open Camera (webcam), Phone Camera (native "
        "capture), or Bluetooth Camera (QR pairing with another device). After "
        "capture press PROCESS SCAN, then DONE & SAVE."
    ),
    "storage|where|folder": (
        "Documents are saved under the storage path shown in Settings -> Storage "
        "(default ai_scanner/data/documents/<category>/). Metadata JSON sits in "
        "data/metadata/."
    ),
    "pdf": (
        "PDF tools: merge images into a PDF via the Vault selection bar; Office "
        "files (docx/xlsx/pptx/csv) are auto-converted to PDF during batch "
        "processing; DONE & SAVE can combine everything as a single PDF."
    ),
    "delete": (
        "Delete a document from the Vault card's trash icon or from the document "
        "inspector. Its metadata JSON is removed too."
    ),
    "rename": (
        "Rename any file from the document inspector (open a card) or let "
        "auto-naming do it: names follow Type_Vendor_Date_Amount."
    ),
}

# Strict grounding appended whenever real app data is supplied, so the model
# cannot invent files that do not exist.
GROUNDING_RULES = (
    "You are connected to live app data. Use ONLY these facts about the vault. "
    "If the data shows 0 documents, say the vault is empty. NEVER invent file "
    "names, counts or categories that are not listed."
)


def _format_vault_facts(app_data: dict) -> str:
    lines = [f"- Total documents in vault: {app_data.get('total_documents', 0)}"]
    size = app_data.get("total_size")
    if size:
        lines.append(f"- Total storage used: {size}")
    cats = app_data.get("categories") or {}
    if cats:
        cat_str = ", ".join(f"{k}: {v}" for k, v in sorted(cats.items()))
        lines.append(f"- Documents by category: {cat_str}")
    else:
        lines.append("- Documents by category: none")
    recent = app_data.get("recent_files") or []
    if recent:
        lines.append("- Recent files (newest first): " + "; ".join(recent[:8]))
    else:
        lines.append("- Recent files: none")
    return "\n".join(lines)


VAULT_INTENT = re.compile(
    r"\b(files?|documents?|vault|archive|library|scans?|stored|available|"
    r"how many|any\s+(?:files|docs|documents)|list|show\s+(?:me\s+)?(?:all|files|docs)|"
    r"what\s+(?:do|i|have|is)\s+(?:have|in|there))\b", re.IGNORECASE)


@dataclass
class ChatReply:
    reply: str
    engine: str = "builtin"
    model: str = ""
    grounded: bool = False


class AIAssistantEngine:
    """Routes AI requests through the best available FREE local provider."""

    def __init__(self):
        self.ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        self.ollama_model = os.environ.get("OLLAMA_MODEL", "")
        self.hf_model = os.environ.get("AI_LOCAL_MODEL", "google/flan-t5-small")
        self._ollama_models: List[str] = []
        self._ollama_checked_at = 0.0
        self._hf_pipeline = None
        self._hf_failed = False

    # ------------------------------------------------------------------ #
    # Provider detection
    # ------------------------------------------------------------------ #

    def _check_ollama(self, force: bool = False) -> List[str]:
        now = time.time()
        if not force and now - self._ollama_checked_at < 30:
            return self._ollama_models
        try:
            r = requests.get(f"{self.ollama_host}/api/tags", timeout=1.5)
            models = [m.get("name", "") for m in r.json().get("models", [])]
            self._ollama_models = [m for m in models if m]
        except Exception:
            self._ollama_models = []
        self._ollama_checked_at = now
        return self._ollama_models

    def _pick_ollama_model(self, models: List[str]) -> str:
        if self.ollama_model:
            for m in models:
                if m == self.ollama_model or m.split(":")[0] == self.ollama_model:
                    return m
        for pref in OLLAMA_PREFERRED_MODELS:
            for m in models:
                if m.split(":")[0] == pref:
                    return m
        return models[0] if models else ""

    def status(self) -> dict:
        ollama_models = self._check_ollama()
        hf_ready = self.hf_available(check=False)
        if ollama_models:
            model = self._pick_ollama_model(ollama_models)
            engine, detail = "ollama", f"Ollama · {model}"
        elif hf_ready:
            engine, detail = "transformer", f"Transformers · {self.hf_model}"
        else:
            engine = "builtin"
            detail = "Built-in helper"
        return {
            "engine": engine,
            "model": model if engine == "ollama" else (self.hf_model if engine == "transformer" else ""),
            "detail": detail,
            "available": True,
            "ollama": {"host": self.ollama_host, "installed": bool(ollama_models),
                       "models": ollama_models},
            "transformer": {"model": self.hf_model, "package": self.transformers_installed(),
                            "downloaded": hf_ready},
        }

    # ------------------------------------------------------------------ #
    # Ollama provider
    # ------------------------------------------------------------------ #

    def _ollama_generate(self, prompt: str, system: str = "") -> Optional[str]:
        models = self._check_ollama()
        if not models:
            return None
        payload = {
            "model": self._pick_ollama_model(models),
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.4},
        }
        if system:
            payload["system"] = system
        try:
            r = requests.post(f"{self.ollama_host}/api/generate", json=payload, timeout=120)
            text = (r.json().get("response") or "").strip()
            return text or None
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    # Transformers provider (google/flan-t5-small)
    # ------------------------------------------------------------------ #

    def transformers_installed(self) -> bool:
        try:
            import transformers  # noqa: F401
            return True
        except ImportError:
            return False

    def hf_available(self, check: bool = False) -> bool:
        if self._hf_failed or not self.transformers_installed():
            return False
        if self._hf_pipeline is not None:
            return True
        if not check:
            try:
                from huggingface_hub import try_to_load_from_cache
                return try_to_load_from_cache(self.hf_model, "config.json") is not None
            except Exception:
                return False
        return False

    def _get_hf_pipeline(self):
        if self._hf_pipeline is None and not self._hf_failed:
            try:
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
                tok = AutoTokenizer.from_pretrained(self.hf_model)
                mdl = AutoModelForSeq2SeqLM.from_pretrained(self.hf_model)
                mdl.eval()
                self._hf_pipeline = (tok, mdl)
            except Exception:
                self._hf_failed = True
        return self._hf_pipeline

    def _hf_answer_sane(self, answer: str, context: str) -> bool:
        """Reject degenerate seq2seq outputs (empty / unrelated to context)."""
        if not answer:
            return False
        words = re.findall(r"[a-z0-9]+", answer.lower())
        if len(words) < 3:
            return False
        ctx = context.lower()
        hits = sum(1 for w in set(words) if w in ctx)
        return hits > 0

    def _clip(self, text: str, limit: int = 3500) -> str:
        text = re.sub(r"\s+", " ", text or "").strip()
        return text[:limit]

    def _hf_generate(self, prompt: str) -> Optional[str]:
        loaded = self._get_hf_pipeline()
        if loaded is None:
            return None
        tok, mdl = loaded
        try:
            inputs = tok(prompt, return_tensors="pt", truncation=True, max_length=512)
            with __import__("torch").no_grad():
                out = mdl.generate(**inputs, max_new_tokens=220)
            text = tok.decode(out[0], skip_special_tokens=True).strip()
            return text or None
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    # Builtin fallback (always available)
    # ------------------------------------------------------------------ #

    def _builtin_help(self, message: str) -> Optional[str]:
        msg = message.lower().strip()
        for key, answer in USAGE_HELP.items():
            for token in key.split("|"):
                if re.search(rf"\b{re.escape(token)}\b", msg):
                    return answer
        greetings = ("hello", "hi", "hey", "help", "what can you")
        if any(g in msg for g in greetings):
            return ("Hi! I'm the AI Scanner assistant. I can summarize or answer "
                    "questions about any document in your vault, and explain app "
                    "features (merging PDFs, cloud sync, OCR...). Ask me anything!")
        return None

    def _builtin_extractive_summary(self, text: str) -> Optional[str]:
        sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 15]
        if not sentences:
            return None
        keywords = re.compile(
            r"invoice|receipt|total|amount|due|date|paid|tax|id|license|passport|"
            r"contract|agreement|name|number|\$|£|€|\d", re.IGNORECASE)
        scored = [(keywords.findall(s), s) for s in sentences[:60]]
        scored.sort(key=lambda p: len(p[0]), reverse=True)
        top = [s for _, s in scored[:4]]
        ordered = [s for s in sentences if s in top]
        return " ".join(ordered[:4]) if ordered else None

    def _builtin_answer_from_context(self, question: str, context: str) -> Optional[str]:
        q = question.lower()
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", context) if s.strip()]
        stop = set("the a an of is are was were for to in on at what which who how "
                   "much many does do this that my your i it".split())
        q_words = [w for w in re.findall(r"[a-z0-9$£€]+", q) if w not in stop]
        best, best_score = "", 0
        for s in sentences:
            sl = s.lower()
            score = sum(1 for w in q_words if w in sl)
            if score > best_score:
                best, best_score = s, score
        if best_score > 0:
            return best
        amount = re.search(r"[\$£€]\s*[\d,]+\.?\d*", context)
        dates = re.findall(r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}", context)
        found = []
        if amount:
            found.append(f"Amount mentioned: {amount.group(0)}")
        if dates:
            found.append(f"Dates found: {', '.join(dates[:3])}")
        if found:
            return ". ".join(found) + "."
        return ("I couldn't match that in the document text. The OCR content may be "
                "too short — try rescanning with better lighting, or install Ollama "
                "for full LLM answers.")

    def _builtin_vault_answer(self, message: str, app_data: dict) -> Optional[str]:
        """Deterministic answers about the vault — always from REAL data."""
        total = int(app_data.get("total_documents", 0))
        cats = app_data.get("categories") or {}
        recent = app_data.get("recent_files") or []
        size = app_data.get("total_size", "")
        if total == 0:
            return ("Your vault is currently EMPTY — 0 documents saved. "
                    "Scan or upload something in the Scanner section and press "
                    "DONE & SAVE; it will appear in Dashboard and Vault right away.")
        parts = [f"Your vault holds {total} document{'s' if total != 1 else ''}"
                 + (f" ({size})" if size else "") + "."]
        if cats:
            cat_str = ", ".join(f"{v} {k}" for k, v in sorted(cats.items(),
                                                              key=lambda kv: -kv[1]))
            parts.append(f"By category: {cat_str}.")
        if recent:
            shown = ", ".join(recent[:5])
            more = f" (+{len(recent) - 5} more)" if len(recent) > 5 else ""
            parts.append(f"Most recent: {shown}{more}.")
        parts.append("Open the Vault section to browse them.")
        return " ".join(parts)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def chat(self, message: str, history: Optional[List[Dict]] = None,
             context: str = "", app_data: Optional[Dict] = None) -> ChatReply:
        message = (message or "").strip()
        if not message:
            return ChatReply(reply="Say something and I'll help!", engine="builtin")
        app_data = app_data or {}

        # Vault/file questions are answered strictly from real data — no LLM
        # guessing, so files can never be invented.
        if app_data and VAULT_INTENT.search(message):
            return ChatReply(reply=self._builtin_vault_answer(message, app_data),
                             engine="builtin", grounded=True)

        prompt = message
        if context:
            prompt = (f"Document text:\n\"\"\"\n{self._clip(context)}\n\"\"\"\n\n"
                      f"User question: {message}")
        system = SYSTEM_PROMPT
        if app_data:
            prompt = (f"Live vault data:\n{_format_vault_facts(app_data)}\n\n"
                      + prompt)
            system = f"{SYSTEM_PROMPT}\n\n{GROUNDING_RULES}"
        if history:
            recent = "\n".join(
                f"{h.get('role', 'user')}: {h.get('content', '')}"
                for h in history[-6:] if h.get("content"))
            prompt = f"{recent}\nuser: {message}"

        reply = self._ollama_generate(prompt, system=system)
        if reply:
            return ChatReply(reply=reply, engine="ollama", grounded=bool(app_data),
                             model=self._pick_ollama_model(self._check_ollama()))
        builtin = self._builtin_help(message)
        if builtin:
            return ChatReply(reply=builtin, engine="builtin")
        if context:
            ans = self._hf_generate(
                f"question: {self._clip(message, 300)} context: {self._clip(context, 2500)}")
            if ans and self._hf_answer_sane(ans, context):
                return ChatReply(reply=ans, engine="transformer", model=self.hf_model)
            ans = self._builtin_answer_from_context(message, context)
            if ans:
                return ChatReply(reply=ans, engine="builtin")
        else:
            ans = self._hf_generate(f"answer the question: {message}")
            if ans and len(ans.split()) >= 3:
                return ChatReply(reply=ans, engine="transformer", model=self.hf_model)
        return ChatReply(
            reply=("I'm running in basic mode right now. For full AI chat install "
                   "Ollama (https://ollama.com, then `ollama pull llama3.2`) — it's "
                   "free and offline. Meanwhile I can still help with app features: "
                   "try \"how do I merge PDFs?\" or use Summarize on a document."),
            engine="builtin")

    def summarize(self, text: str) -> ChatReply:
        text = (text or "").strip()
        if len(text) < 40:
            return ChatReply(reply="Not enough OCR text to summarize.", engine="builtin")
        out = self._ollama_generate(
            f"Summarize this scanned document in 3-4 bullet points:\n\n{self._clip(text)}",
            system=SYSTEM_PROMPT)
        if out:
            return ChatReply(reply=out, engine="ollama",
                             model=self._pick_ollama_model(self._check_ollama()))
        out = self._hf_generate(f"summarize: {self._clip(text, 2800)}")
        if out:
            return ChatReply(reply=out, engine="transformer", model=self.hf_model)
        out = self._builtin_extractive_summary(text)
        if out:
            return ChatReply(reply=out, engine="builtin")
        return ChatReply(reply="Could not generate a summary for this text.",
                         engine="builtin")

    def key_points(self, text: str) -> ChatReply:
        text = (text or "").strip()
        if len(text) < 20:
            return ChatReply(reply="Not enough OCR text to analyze.", engine="builtin")
        out = self._ollama_generate(
            f"List the key facts (dates, amounts, names, IDs) from this document "
            f"as short bullet points:\n\n{self._clip(text)}", system=SYSTEM_PROMPT)
        if out:
            return ChatReply(reply=out, engine="ollama",
                             model=self._pick_ollama_model(self._check_ollama()))
        amounts = re.findall(r"[\$£€]\s*[\d,]+\.?\d*", text)[:5]
        dates = re.findall(r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|"
                           r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
                           r"\s+\d{1,2},?\s+\d{4}", text)[:5]
        emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", text)[:3]
        phones = re.findall(r"(?:\+\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}",
                            text)[:3]
        lines = []
        if amounts:
            lines.append("Amounts: " + ", ".join(amounts))
        if dates:
            lines.append("Dates: " + ", ".join(dates))
        if emails:
            lines.append("Emails: " + ", ".join(emails))
        if phones:
            lines.append("Phones: " + ", ".join(phones))
        if lines:
            return ChatReply(reply="\n".join(f"• {l}" for l in lines), engine="builtin")
        summary = self._builtin_extractive_summary(text)
        return ChatReply(reply=summary or "No key facts detected in the OCR text.",
                         engine="builtin")

    def ask(self, question: str, context: str) -> ChatReply:
        question = (question or "").strip()
        context = (context or "").strip()
        if not question:
            return ChatReply(reply="Ask a question about the document.", engine="builtin")
        if not context:
            return ChatReply(reply="This document has no OCR text to search. Try "
                                   "rescanning it first.", engine="builtin")
        out = self._ollama_generate(
            f"Document:\n\"\"\"\n{self._clip(context, 6000)}\n\"\"\"\n\n"
            f"Question: {question}\nAnswer using only the document.",
            system=SYSTEM_PROMPT)
        if out:
            return ChatReply(reply=out, engine="ollama",
                             model=self._pick_ollama_model(self._check_ollama()))
        out = self._hf_generate(
            f"question: {self._clip(question, 250)} context: {self._clip(context, 2500)}")
        if out and self._hf_answer_sane(out, context):
            return ChatReply(reply=out, engine="transformer", model=self.hf_model)
        out = self._builtin_answer_from_context(question, context)
        return ChatReply(reply=out, engine="builtin")

    def vault_overview(self, app_data: Dict) -> ChatReply:
        """Natural-language overview of the vault for the dashboard."""
        total = int(app_data.get("total_documents", 0))
        if total == 0:
            return ChatReply(
                reply=("Your archive is empty — nothing has been saved yet. Head to "
                       "the Scanner, capture or upload a document, press PROCESS and "
                       "then DONE & SAVE. Your first scan will show up here."),
                engine="builtin")
        prompt = ("Write a friendly 3-sentence overview of this document archive "
                  "for the user:\n" + _format_vault_facts(app_data))
        system = f"{SYSTEM_PROMPT}\n\n{GROUNDING_RULES}"
        out = self._ollama_generate(prompt, system=system)
        if out:
            return ChatReply(reply=out, engine="ollama",
                             model=self._pick_ollama_model(self._check_ollama()))
        cats = app_data.get("categories") or {}
        recent = app_data.get("recent_files") or []
        size = app_data.get("total_size", "")
        top = sorted(cats.items(), key=lambda kv: -kv[1])[:3]
        cat_str = ", ".join(f"{v} {k}{'s' if v != 1 else ''}" for k, v in top) \
            if top else "no categories yet"
        lines = [f"The archive currently preserves {total} document"
                 f"{'s' if total != 1 else ''}"
                 + (f" using {size}" if size else "") + f" — mainly {cat_str}."]
        if recent:
            lines.append(f"Latest addition: {recent[0]}.")
        lines.append("Everything is searchable from the top bar and stored locally "
                     "on this machine.")
        return ChatReply(reply=" ".join(lines), engine="builtin")
