"""Messages on the guest page (errors and confirmations) in the browser's language, or English."""

import pytest
from conftest import GUEST
from helpers import FakeGeminiClient, api_error
from werkzeug.datastructures import LanguageAccept
from werkzeug.http import parse_accept_header

from app import create_app
from assistant.guest_messages import GUEST_MESSAGES, guest_message
from assistant.limits import LIMIT_MESSAGES
from assistant.privacy import NOTICES

PORTUGUESE = {"Accept-Language": "pt-PT,pt;q=0.9,en;q=0.5"}


def accept(header):
    return parse_accept_header(header, LanguageAccept)


def ask(data_folder, *replies, question="Wi-Fi?", headers=None):
    app = create_app(client=FakeGeminiClient(*replies), data_folder=data_folder)
    response = app.test_client().post(f"{GUEST}/ask", data={"question": question},
                                      headers=headers or {}, follow_redirects=True)
    return response.get_data(as_text=True)


# ---------- The texts ----------

def test_every_message_exists_in_the_same_six_languages():
    for kind, texts in GUEST_MESSAGES.items():
        assert set(texts) == {"en", "pt", "es", "fr", "de", "it"}, kind
        assert all(text.strip() for text in texts.values()), kind
    assert set(GUEST_MESSAGES["busy"]) == set(NOTICES) == set(LIMIT_MESSAGES["guest"])


@pytest.mark.parametrize("header, expected", [
    ("pt-PT,pt;q=0.9", "O assistente está ocupado neste momento."),
    ("pt-BR", "O assistente está ocupado neste momento."),
    ("es-ES,es;q=0.9", "El asistente está ocupado en este momento."),
    ("fr-FR", "L'assistant est occupé pour le moment."),
    ("de-DE,de;q=0.9", "Der Assistent ist gerade ausgelastet."),
    ("it-IT", "L'assistente è occupato in questo momento."),
    ("ja-JP,ja;q=0.9", "The assistant is busy right now."),   # no message in Japanese: English
    ("", "The assistant is busy right now."),                  # no header: English
])
def test_busy_message_in_the_browser_language(header, expected):
    assert guest_message("busy", accept(header)).startswith(expected)


# ---------- On the guest page ----------

@pytest.mark.parametrize("headers, expected", [
    (PORTUGUESE, "O assistente está ocupado neste momento. Tente novamente daqui a um minuto."),
    ({"Accept-Language": "es"}, "El asistente está ocupado en este momento."),
    ({}, "The assistant is busy right now. Please try again in a minute."),
])
def test_busy_message_when_both_models_are_busy(data_folder, headers, expected):
    html = ask(data_folder, *[api_error(503)] * 4, headers=headers)

    assert expected in html


def test_permanent_error_message_in_portuguese(data_folder):
    html = ask(data_folder, api_error(403), headers=PORTUGUESE)

    assert "O assistente não conseguiu responder desta vez. Tente novamente ou contacte o anfitrião." in html
    assert "could not answer" not in html


def test_empty_answer_message_in_german(data_folder):
    html = ask(data_folder, "", headers={"Accept-Language": "de-DE"})

    assert "Der Assistent konnte diese Frage nicht beantworten." in html


def test_missing_api_key_message_in_french(data_folder, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    app = create_app(client=None, data_folder=data_folder)

    html = app.test_client().post(f"{GUEST}/ask", data={"question": "Wi-Fi?"},
                                  headers={"Accept-Language": "fr-FR"}, follow_redirects=True).get_data(as_text=True)

    assert "L&#39;assistant n&#39;est pas encore configuré." in html  # Jinja writes ' as &#39;


def test_empty_question_message_in_italian(data_folder):
    html = ask(data_folder, question="   ", headers={"Accept-Language": "it-IT"})

    assert "Scrivi una domanda." in html


def test_conversation_cleared_message_in_portuguese(data_folder):
    app = create_app(client=FakeGeminiClient(), data_folder=data_folder)

    html = app.test_client().post(f"{GUEST}/reset", headers=PORTUGUESE,
                                  follow_redirects=True).get_data(as_text=True)

    assert "A sua conversa foi apagada." in html


def test_error_is_logged_in_english_without_the_question(data_folder, caplog):
    ask(data_folder, *[api_error(503)] * 4, question="My passport is X1234567", headers=PORTUGUESE)

    assert "No answer for a guest: The assistant is busy right now." in caplog.text
    assert "X1234567" not in caplog.text


def test_host_pages_stay_in_english(data_folder):
    app = create_app(client=FakeGeminiClient(), data_folder=data_folder)

    html = app.test_client().post("/host", data={"password": "wrong"}, headers=PORTUGUESE,
                                  follow_redirects=True).get_data(as_text=True)

    assert "Wrong password." in html
