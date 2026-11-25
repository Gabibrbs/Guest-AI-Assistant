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
    ask_with_fallback,
    create_client,
    get_fallback_model_name,
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


def test_automatic_function_calling_is_off(sleep):
    """The app gives the model no tools; with this on, the library logs "AFC is enabled" every time."""
    client = FakeGeminiClient("Answer")

    ask_gemini(client, "test-model", "prompt", sleep=sleep, deadline=None)

    config = client.models.calls[0]["config"]
    assert config.automatic_function_calling.disable is True
    assert config.thinking_config is not None  # the other settings are still there
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
    assert get_model_name() == "gemini-3.5-flash-lite"

    monkeypatch.setenv("GEMINI_MODEL", "other-model")
    assert get_model_name() == "other-model"


def test_fallback_model_default_from_environment_or_off(monkeypatch):
    monkeypatch.delenv("GEMINI_FALLBACK_MODEL", raising=False)
    assert get_fallback_model_name() == "gemini-3.6-flash"

    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "other-flash")
    assert get_fallback_model_name() == "other-flash"

    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "none")
    assert get_fallback_model_name() is None


# ---------- Fallback model ----------

def test_main_model_answers_and_the_fallback_is_not_used(sleep):
    client = FakeGeminiClient("Answer from main")

    assert ask_with_fallback(client, "main", "fallback", "prompt", sleep=sleep) == "Answer from main"
    assert [call["model"] for call in client.models.calls] == ["main"]


def test_busy_main_model_then_the_fallback_answers(sleep, caplog):
    client = FakeGeminiClient(api_error(503), api_error(503), api_error(503), "Answer from fallback")

    text = ask_with_fallback(client, "main", "fallback", "My name is Ana Silva, room 3B", sleep=sleep)

    assert text == "Answer from fallback"
    assert [call["model"] for call in client.models.calls] == ["main", "main", "main", "fallback"]
    assert sleep.waits == [5, 10]  # the fallback is asked at once, with no extra wait
    assert "fallback model fallback answered" in caplog.text
    assert "Ana Silva" not in caplog.text and "prompt" not in caplog.text


@pytest.mark.parametrize("error", [api_error(429), api_error(500), api_error(504), ConnectionError("down")])
def test_every_temporary_error_goes_to_the_fallback(sleep, error):
    client = FakeGeminiClient(error, error, error, "Answer from fallback")

    assert ask_with_fallback(client, "main", "fallback", "prompt", sleep=sleep) == "Answer from fallback"


def test_both_models_busy_shows_the_busy_message(sleep, caplog):
    client = FakeGeminiClient(api_error(503), api_error(503), api_error(503), api_error(503))

    with pytest.raises(GeminiError, match="busy right now"):
        ask_with_fallback(client, "main", "fallback", "Secret question", sleep=sleep)

    assert [call["model"] for call in client.models.calls] == ["main", "main", "main", "fallback"]  # fallback once
    assert "fallback model fallback also failed" in caplog.text
    assert "Secret question" not in caplog.text


def test_fallback_with_a_permanent_error_still_shows_the_busy_message(sleep):
    client = FakeGeminiClient(api_error(503), api_error(503), api_error(503), api_error(400))

    with pytest.raises(GeminiError, match="busy right now"):
        ask_with_fallback(client, "main", "fallback", "prompt", sleep=sleep)


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_permanent_error_does_not_go_to_the_fallback(sleep, code):
    client = FakeGeminiClient(api_error(code))

    with pytest.raises(GeminiError, match="could not answer"):
        ask_with_fallback(client, "main", "fallback", "prompt", sleep=sleep)
    assert [call["model"] for call in client.models.calls] == ["main"]


def test_empty_answer_does_not_go_to_the_fallback(sleep):
    client = FakeGeminiClient("")

    with pytest.raises(GeminiError, match="empty answer"):
        ask_with_fallback(client, "main", "fallback", "prompt", sleep=sleep)
    assert len(client.models.calls) == 1


@pytest.mark.parametrize("fallback", [None, "main"])
def test_no_fallback_when_it_is_off_or_the_same_model(sleep, fallback):
    client = FakeGeminiClient(api_error(503), api_error(503), api_error(503))

    with pytest.raises(GeminiError, match="busy"):
        ask_with_fallback(client, "main", fallback, "prompt", sleep=sleep)
    assert len(client.models.calls) == 3


def test_answer_question_without_fallback_by_default(sleep):
    """The evaluation measures one model at a time, so answer_question has no fallback unless asked."""
    client = FakeGeminiClient(api_error(503), api_error(503), api_error(503))

    with pytest.raises(GeminiError):
        answer_question(client, "main", {"a.md": "text"}, "Question?", sleep=sleep)
    assert len(client.models.calls) == 3


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
