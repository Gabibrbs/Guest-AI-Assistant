"""Calling the model: answers, temporary errors with new attempts, and permanent errors.

The fake client replaces the real one and a fake sleep records the waits, so the
tests never call the API and never wait for real.
"""

import pytest
from helpers import FakeGeminiClient, api_error

from assistant.answer import answer_question
from assistant.gemini_client import (
    GeminiError,
    ask_gemini,
    create_client,
    get_model_name,
)


class FakeSleep:
    """Records how long the code asked to wait, without waiting."""

    def __init__(self):
        self.waits = []

    def __call__(self, seconds):
        self.waits.append(seconds)


@pytest.fixture
def sleep():
    return FakeSleep()


def test_returns_the_model_text(sleep):
    client = FakeGeminiClient("  The password is abc.\nSOURCE: the-house.md  ")

    text = ask_gemini(client, "test-model", "my prompt", sleep=sleep)

    assert text == "The password is abc.\nSOURCE: the-house.md"
    call = client.models.calls[0]
    assert call["model"] == "test-model"
    assert call["contents"] == "my prompt"
    assert call["config"] is not None  # the generation settings are sent
    assert sleep.waits == []


@pytest.mark.parametrize("code", [429, 500, 503, 504])
def test_temporary_error_then_success(sleep, code):
    client = FakeGeminiClient(api_error(code), "Answer")

    assert ask_gemini(client, "test-model", "prompt", sleep=sleep) == "Answer"
    assert len(client.models.calls) == 2
    assert sleep.waits == [5]


def test_wait_doubles_between_attempts(sleep):
    client = FakeGeminiClient(api_error(503), api_error(429), "Answer")

    assert ask_gemini(client, "test-model", "prompt", sleep=sleep) == "Answer"
    assert sleep.waits == [5, 10]


def test_gives_up_after_three_temporary_errors(sleep):
    client = FakeGeminiClient(api_error(503), api_error(503), api_error(503))

    with pytest.raises(GeminiError, match="busy"):
        ask_gemini(client, "test-model", "prompt", sleep=sleep)
    assert len(client.models.calls) == 3
    assert sleep.waits == [5, 10]  # no wait after the last attempt


def test_connection_errors_are_retried(sleep):
    client = FakeGeminiClient(ConnectionError("network down"), TimeoutError("too slow"), "Answer")

    assert ask_gemini(client, "test-model", "prompt", sleep=sleep) == "Answer"
    assert len(client.models.calls) == 3


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_permanent_errors_are_not_retried(sleep, code):
    client = FakeGeminiClient(api_error(code))

    with pytest.raises(GeminiError, match="could not answer"):
        ask_gemini(client, "test-model", "prompt", sleep=sleep)
    assert len(client.models.calls) == 1
    assert sleep.waits == []


@pytest.mark.parametrize("empty_reply", [None, "", "   "])
def test_empty_answer_is_an_error(sleep, empty_reply):
    client = FakeGeminiClient(empty_reply)

    with pytest.raises(GeminiError, match="empty answer"):
        ask_gemini(client, "test-model", "prompt", sleep=sleep)


# ---------- Settings from .env ----------

def test_missing_api_key_gives_a_clear_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(GeminiError, match="GEMINI_API_KEY is not set"):
        create_client()


def test_model_name_default_and_from_environment(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    assert get_model_name() == "gemini-3.5-flash"

    monkeypatch.setenv("GEMINI_MODEL", "other-model")
    assert get_model_name() == "other-model"


# ---------- Everything together ----------

def test_answer_question_sends_the_documents_and_reads_the_sources():
    documents = {"the-house.md": "Wi-Fi password: azulejo2026"}
    client = FakeGeminiClient("A palavra-passe é azulejo2026.\nSOURCE: the-house.md")

    answer = answer_question(client, "test-model", documents, "Qual é a palavra-passe do Wi-Fi?")

    sent_prompt = client.models.calls[0]["contents"]
    assert '<document name="the-house.md">' in sent_prompt
    assert "Qual é a palavra-passe do Wi-Fi?" in sent_prompt
    assert answer.text == "A palavra-passe é azulejo2026."
    assert answer.sources == ["the-house.md"]
    assert answer.found is True


def test_answer_question_not_in_the_documents():
    documents = {"the-house.md": "Wi-Fi password: azulejo2026"}
    client = FakeGeminiClient("This is not in the house guide. Please contact the host.\nSOURCE: none")

    answer = answer_question(client, "test-model", documents, "Do you have a baby cot?")

    assert answer.found is False
    assert answer.sources == []
