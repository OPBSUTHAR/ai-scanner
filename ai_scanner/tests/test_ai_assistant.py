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


def _vault_data(total=3):
    return {
        "total_documents": total,
        "total_size": "4.2 MB",
        "categories": {"invoice": 2, "receipt": 1} if total else {},
        "recent_files": (["Invoice_Acme_Mar15.png", "Receipt_Store_Mar14.png",
                          "Contract_Jan2026.pdf"][:total] if total else []),
    }


def test_vault_question_empty_vault_never_invents_files():
    eng = _offline_engine()
    reply = eng.chat("are there any files available?", app_data=_vault_data(0))
    assert "empty" in reply.reply.lower()
    assert ".png" not in reply.reply and ".pdf" not in reply.reply


def test_vault_question_reports_real_files():
    eng = _offline_engine()
    reply = eng.chat("is there any files avaialbe", app_data=_vault_data(3))
    assert "3 documents" in reply.reply
    assert "Invoice_Acme_Mar15.png" in reply.reply
    assert reply.engine == "builtin"


def test_vault_question_with_ollama_still_grounded():
    """Even when Ollama is installed, vault questions use real data only."""
    eng = _offline_engine()
    called = {"post": False}

    def fake_post(url, json=None, timeout=None):
        called["post"] = True
        raise AssertionError("LLM must not be consulted for vault questions")

    with mock.patch("src.ai_assistant.engine.requests.get",
                    side_effect=lambda u, t: (_ for _ in ()).throw(Exception("down"))), \
         mock.patch("src.ai_assistant.engine.requests.post", side_effect=fake_post):
        reply = eng.chat("what files do i have?", app_data=_vault_data(2))
    assert not called["post"]
    assert "2 documents" in reply.reply


def test_vault_overview_empty_and_filled():
    eng = _offline_engine()
    empty = eng.vault_overview(_vault_data(0))
    assert "empty" in empty.reply.lower()
    filled = eng.vault_overview(_vault_data(3))
    assert "3 documents" in filled.reply
    assert "Invoice_Acme_Mar15.png" in filled.reply


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


def test_cloud_provider_used_when_no_ollama():
    eng = _offline_engine()

    class FakeResp:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": " Cloud says hi "}}]}

    def fake_post(url, json=None, timeout=None, headers=None):
        assert "/chat/completions" in url
        assert headers["Authorization"] == "Bearer test-key"
        assert json["messages"][-1]["role"] == "user"
        return FakeResp()

    with mock.patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}), \
         mock.patch("src.ai_assistant.engine.requests.post", side_effect=fake_post):
        s = eng.status()
        assert s["engine"] == "cloud"
        assert s["cloud"]["enabled"] is True
        reply = eng.chat("hello")
    assert reply.engine == "cloud"
    assert reply.reply == "Cloud says hi"


def test_cloud_failure_falls_back_to_builtin():
    eng = _offline_engine()

    def fail_post(url, json=None, timeout=None, headers=None):
        class R:
            status_code = 500

            def json(self):
                return {}

        return R()

    with mock.patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}), \
         mock.patch("src.ai_assistant.engine.requests.post", side_effect=fail_post):
        reply = eng.chat("how do I merge PDFs?")
    assert reply.engine == "builtin"
    # engine is put into cool-down so later calls skip the dead provider
    assert eng._cloud_failed_until > 0


def test_cloud_disabled_without_key_stays_builtin():
    eng = _offline_engine()
    assert eng._cloud_enabled() is False
    s = eng.status()
    assert s["engine"] == "builtin"
    assert s["cloud"]["enabled"] is False


def test_cloud_key_picked_up_live_from_env():
    """Key saved via Settings -> API Keys syncs to os.environ; engine must
    see it without restart."""
    eng = _offline_engine()
    assert eng._cloud_enabled() is False
    with mock.patch.dict(os.environ, {"GROQ_API_KEY": "late-key"}):
        assert eng._cloud_enabled() is True
        assert eng.cloud_key == "late-key"
