"""The privacy notice for guests, and the production settings (wsgi.py)."""

import importlib
import sys

import dotenv
import pytest
from conftest import GUEST, SLUG
from helpers import FakeGeminiClient
from werkzeug.datastructures import LanguageAccept
from werkzeug.http import parse_accept_header

from app import create_app
from assistant.limits import LIMIT_MESSAGES
from assistant.privacy import NOTICES, privacy_notice
from assistant.properties import Property


def accept(header):
    return parse_accept_header(header, LanguageAccept)


def make_app(data_folder, **options):
    app = create_app(client=FakeGeminiClient(), data_folder=data_folder, **options)
    app.config["TESTING"] = True
    return app


PROP = Property(slug="casa-a-111111", name="Casa A Example", folder=None, host_contact="WhatsApp +351 000 000 001")


# ---------- What the notice says ----------

def test_full_notice_has_everything_the_guest_must_know():
    paragraphs = privacy_notice(PROP, accept("en"))["paragraphs"]
    text = " ".join(paragraphs)

    assert "Casa A Example" in text and "WhatsApp +351 000 000 001" in text  # who is responsible
    assert "Gemini API, a Google service" in text                           # where questions go
    assert "Google does not use them to improve its products" in text
    assert "do not write personal data" in text                              # what not to write
    assert "names" in text and "passport" in text and "card" in text
    assert "deleted 24 hours after your last message" in text                # how long it is kept
    assert "never the text of your questions" in text


def test_notice_without_contact_has_no_empty_contact_sentence():
    prop = Property(slug="casa-a-111111", name="Casa A Example", folder=None)

    first = privacy_notice(prop, accept("en"))["paragraphs"][0]

    assert first == "This assistant is provided by Casa A Example."


@pytest.mark.parametrize("header, language, words", [
    ("pt-PT,pt;q=0.9", "pt", "apagada 24 horas depois"),
    ("es-ES", "es", "se borra 24 horas después"),
    ("fr-FR,fr;q=0.9", "fr", "supprimée 24 heures après"),
    ("de-DE", "de", "24 Stunden nach Ihrer letzten Nachricht gelöscht"),
    ("it-IT", "it", "cancellata 24 ore dopo"),
    ("ja-JP", "en", "deleted 24 hours after"),
    ("", "en", "deleted 24 hours after"),
])
def test_notice_in_the_browser_language_or_english(header, language, words):
    notice = privacy_notice(PROP, accept(header))

    assert notice["language"] == language
    assert words in " ".join(notice["paragraphs"])
    assert "Casa A Example" in notice["paragraphs"][0]


def test_every_language_has_every_text():
    keys = set(NOTICES["en"])
    for language, texts in NOTICES.items():
        assert set(texts) == keys, language
        assert "{name}" in texts["provider"] and "{contact}" in texts["contact"]


def test_notice_and_limit_messages_have_the_same_languages():
    assert set(NOTICES) == set(LIMIT_MESSAGES["guest"])


# ---------- On the pages ----------

def test_short_line_and_link_are_under_the_question_box(data_folder):
    html = make_app(data_folder).test_client().get(GUEST).get_data(as_text=True)

    assert "Questions are sent to Google&#39;s Gemini AI" in html
    assert f'href="{GUEST}/privacy"' in html
    assert html.index('class="ask"') < html.index('class="privacy-line"')


def test_short_line_follows_the_browser_language(data_folder):
    html = make_app(data_folder).test_client().get(
        GUEST, headers={"Accept-Language": "pt-PT,pt;q=0.9"}).get_data(as_text=True)

    assert "As perguntas são enviadas à IA Gemini da Google." in html
    assert ">Privacidade</a>" in html


def test_privacy_page_shows_the_full_notice_of_that_property(data_folder):
    response = make_app(data_folder).test_client().get(f"{GUEST}/privacy",
                                                       headers={"Accept-Language": "fr-FR"})

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert '<html lang="fr">' in html
    assert "Cet assistant est proposé par Casa Test Example." in html
    assert "Contact : WhatsApp +351 000 000 001." in html
    assert f'href="{GUEST}"' in html  # back to the assistant


def test_privacy_page_of_unknown_property_is_not_found(data_folder):
    assert make_app(data_folder).test_client().get("/p/nope/privacy").status_code == 404


# ---------- Production settings ----------

def test_debug_is_always_off(data_folder):
    assert make_app(data_folder).debug is False
    assert make_app(data_folder, production=True).debug is False


def test_cookie_only_over_https_in_production(data_folder):
    browser = make_app(data_folder, production=True).test_client()

    cookie = browser.get(GUEST, base_url="https://guide.example.com").headers["Set-Cookie"]

    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=Lax" in cookie


def test_cookie_works_over_http_on_this_computer(data_folder):
    browser = make_app(data_folder).test_client()

    cookie = browser.get(GUEST).headers["Set-Cookie"]
    with browser.session_transaction() as session:
        guest_id = session["guest_id"]

    assert "Secure" not in cookie
    assert len(guest_id) == 32  # the browser kept the cookie, so the guest keeps the conversation


def test_wsgi_entry_point_builds_a_production_app(data_folder, monkeypatch):
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: None)  # never read the real .env
    monkeypatch.setenv("DATA_FOLDER", str(data_folder))
    monkeypatch.delitem(sys.modules, "wsgi", raising=False)

    wsgi = importlib.import_module("wsgi")

    assert wsgi.application.debug is False
    assert wsgi.application.config["SESSION_COOKIE_SECURE"] is True
    response = wsgi.application.test_client().get(GUEST, base_url="https://guide.example.com")
    assert response.status_code == 200
    assert SLUG in response.get_data(as_text=True)
