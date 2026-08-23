import os
from unittest import mock

from src.ai_assistant.engine import AIAssistantEngine

INVOICE_TEXT = (
    "INVOICE #2026-0042\n"
    "Billed to: Acme Corp, 12 Main Street\n"
    "Invoice Date: 14/03/2026\n"
    "Amount Due: $1,250.00\n"
    "Payment due within 30 days. Contact billing@acme.example or 555-123-4567."
)


def _offline_engine() -> AIAssistantEngine:
    """Engine with Ollama unreachable and transformers provider disabled."""
    eng = AIAssistantEngine()
    eng.ollama_host = "http://127.0.0.1:1"  # nothing listens here
    eng._hf_failed = True
    return eng


def test_status_reports_builtin_when_nothing_installed():
    eng = _offline_engine()
    s = eng.status()
    assert s["engine"] == "builtin"
    assert s["available"] is True
    assert s["ollama"]["installed"] is False


def test_builtin_usage_answers():
    eng = _offline_engine()
    for question in ("How do I merge PDFs?", "how does cloud sync work",
                     "where are my files stored?"):
        reply = eng.chat(question)
        assert len(reply.reply) > 20
        assert reply.engine == "builtin"


def test_chat_greeting():
    eng = _offline_engine()
    reply = eng.chat("hello")
    assert "assistant" in reply.reply.lower()


def test_extractive_summary_contains_amount():
    eng = _offline_engine()
    reply = eng.summarize(INVOICE_TEXT)
    assert reply.engine == "builtin"
    # The extractive summarizer must surface the amount-bearing sentence.
    assert "$1,250.00".replace(",", "") in reply.reply.replace(",", "") \
        or "1250" in reply.reply.replace(",", "")


def test_key_points_extracts_facts():
    eng = _offline_engine()
    reply = eng.key_points(INVOICE_TEXT)
    assert "Amounts" in reply.reply
    assert "Dates" in reply.reply
    assert "billing@acme.example" in reply.reply


def test_ask_matches_context_sentence():
    eng = _offline_engine()
    reply = eng.ask("what is the amount due?", INVOICE_TEXT)
    assert "1,250" in reply.reply or "1250" in reply.reply.replace(",", "")


def test_ask_without_context_is_graceful():
    eng = _offline_engine()
    reply = eng.ask("what is the total?", "")
    assert "no ocr text" in reply.reply.lower()


def test_summarize_short_text_guard():
    eng = _offline_engine()
    reply = eng.summarize("too short")
    assert "Not enough OCR text" in reply.reply


def test_ollama_provider_preferred_when_available():
    eng = _offline_engine()

    class FakeResp:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def fake_get(url, timeout):
        assert "/api/tags" in url
        return FakeResp({"models": [{"name": "llama3.2:latest"}, {"name": "phi3"}]})

    def fake_post(url, json=None, timeout=None):
        assert "/api/generate" in url
        assert json["model"].startswith("llama3.2")
        return FakeResp({"response": " Ollama says hi "})

    with mock.patch("src.ai_assistant.engine.requests.get", side_effect=fake_get), \
         mock.patch("src.ai_assistant.engine.requests.post", side_effect=fake_post):
        s = eng.status()
        assert s["engine"] == "ollama"
        assert s["model"] == "llama3.2:latest"
        reply = eng.chat("hello")
        assert reply.engine == "ollama"
        assert reply.reply == "Ollama says hi"
