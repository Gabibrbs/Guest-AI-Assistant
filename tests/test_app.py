"""Guest pages: home page, asking a question, starting over, one conversation per guest.

Each test builds its own app with a fake Gemini client and a small documents folder.
"""

import io

import pytest
from conftest import GUEST, SLUG
from helpers import FakeGeminiClient, api_error

from app import clean_filename, create_app


def make_app(data_folder, *replies):
    """App with a fake client that will give `replies`, plus a Flask test browser."""
    fake = FakeGeminiClient(*replies)
    app = create_app(client=fake, data_folder=data_folder)
    app.config["TESTING"] = True
    return app.test_client(), fake


def page_text(response):
    return response.get_data(as_text=True)


# ---------- Home page ----------

def test_home_page_shows_business_documents_and_examples(data_folder):
    browser, fake = make_app(data_folder)

    response = browser.get(GUEST)

    assert response.status_code == 200
    html = page_text(response)
    assert "Casa Test Example" in html
    assert "the-house.md" in html and "house-rules.md" in html
    assert "2 documents" in html
    assert "What is the Wi-Fi password?" in html  # example question
    assert fake.models.calls == []                 # opening the page does not call the model


# ---------- Asking ----------

def test_question_shows_answer_and_source(data_folder):
    browser, fake = make_app(data_folder, "A palavra-passe é azulejo2026.\nSOURCE: the-house.md")

    response = browser.post(f"{GUEST}/ask", data={"question": "Qual é a palavra-passe?"}, follow_redirects=True)

    html = page_text(response)
    assert "Qual é a palavra-passe?" in html
    assert "A palavra-passe é azulejo2026." in html
    assert "Source: the-house.md" in html
    assert "Wi-Fi password: azulejo2026" in fake.models.calls[0]["contents"]  # documents were sent


def test_question_not_in_documents_shows_the_hosts_message(data_folder):
    browser, fake = make_app(data_folder, "Not in the house guide. Please message the host on Airbnb.\nSOURCE: none")

    html = page_text(browser.post(f"{GUEST}/ask", data={"question": "Do you have a cot?"}, follow_redirects=True))

    assert "Not in the house guide · Please message the host on Airbnb." in html  # from config.toml
    assert "Source:" not in html
    prompt = fake.models.calls[0]["contents"]
    assert '"Please message the host on Airbnb."' in prompt  # the model translates it for the guest
    assert "Casa Test Example" in prompt


def test_conversation_history_is_kept(data_folder):
    browser, _ = make_app(
        data_folder,
        "First answer.\nSOURCE: the-house.md",
        "Second answer.\nSOURCE: house-rules.md",
    )

    browser.post(f"{GUEST}/ask", data={"question": "First question?"})
    html = page_text(browser.post(f"{GUEST}/ask", data={"question": "Second question?"}, follow_redirects=True))

    assert html.index("First question?") < html.index("Second question?")
    assert "First answer." in html and "Second answer." in html


def test_ask_redirects_to_the_latest_answer(data_folder):
    browser, _ = make_app(data_folder, "Answer.\nSOURCE: the-house.md")

    response = browser.post(f"{GUEST}/ask", data={"question": "Question?"})

    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"{GUEST}#latest")


@pytest.mark.parametrize("question", ["", "    "])
def test_empty_question_is_refused_without_calling_the_model(data_folder, question):
    browser, fake = make_app(data_folder)

    html = page_text(browser.post(f"{GUEST}/ask", data={"question": question}, follow_redirects=True))

    assert "Please type a question." in html
    assert fake.models.calls == []


def test_api_error_is_shown_to_the_user(data_folder):
    browser, _ = make_app(data_folder, api_error(403))

    html = page_text(browser.post(f"{GUEST}/ask", data={"question": "Question?"}, follow_redirects=True))

    assert "could not answer" in html


def test_busy_main_model_and_the_fallback_answers_the_guest(data_folder):
    browser, fake = make_app(data_folder, api_error(503), api_error(503), api_error(503),
                             "Answer from the fallback.\nSOURCE: the-house.md")

    html = page_text(browser.post(f"{GUEST}/ask", data={"question": "Wi-Fi?"}, follow_redirects=True))

    assert "Answer from the fallback." in html
    assert [call["model"] for call in fake.models.calls] == ["gemini-3.5-flash-lite"] * 3 + ["gemini-3.6-flash"]


def test_both_models_busy_shows_the_error_to_the_guest(data_folder):
    browser, fake = make_app(data_folder, *[api_error(503)] * 4)

    html = page_text(browser.post(f"{GUEST}/ask", data={"question": "Wi-Fi?"}, follow_redirects=True))

    assert "The assistant is busy right now." in html
    assert len(fake.models.calls) == 4


def test_missing_api_key_is_shown_to_the_user(data_folder, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    app = create_app(client=None, data_folder=data_folder)  # no fake: the real client is needed
    browser = app.test_client()

    html = page_text(browser.post(f"{GUEST}/ask", data={"question": "Question?"}, follow_redirects=True))

    assert "GEMINI_API_KEY is not set" in html


# ---------- File names ----------

@pytest.mark.parametrize(
    "original, cleaned",
    [
        ('../my "guide".txt', "my_guide.txt"),  # no folders or quotes (the name goes into the prompt)
        ("Guia da casa.PDF", "Guia_da_casa.pdf"),
        ("pequeno-almoço.md", "pequeno-almoco.md"),
        ("指南.txt", "document.txt"),           # non-Latin name: keep the extension
    ],
)
def test_clean_filename(original, cleaned):
    assert clean_filename(original) == cleaned


# ---------- Starting over ----------

def test_start_over_clears_only_the_conversation(data_folder):
    browser, _ = make_app(data_folder, "Answer.\nSOURCE: the-house.md")
    browser.post(f"{GUEST}/ask", data={"question": "My question?"})

    html = page_text(browser.post(f"{GUEST}/reset", follow_redirects=True))

    assert "My question?" not in html
    assert "Your conversation was cleared." in html
    assert "2 documents" in html  # the house guide is not touched


# ---------- Guests cannot change the guide ----------

def test_guest_page_has_no_upload(data_folder):
    browser, _ = make_app(data_folder)

    html = page_text(browser.get(GUEST))

    assert 'type="file"' not in html
    assert "Upload" not in html


def test_old_guest_upload_address_no_longer_exists(data_folder):
    browser, _ = make_app(data_folder)

    response = browser.post(
        "/upload",
        data={"document": (io.BytesIO(b"Fake rule"), "rules.txt")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 404
    assert not (data_folder / "rules.txt").exists()


# ---------- One conversation per guest ----------

def test_two_guests_have_separate_conversations(data_folder):
    anna, fake = make_app(data_folder, "Answer for Anna.\nSOURCE: the-house.md")
    bruno = anna.application.test_client()  # a second browser on the same app

    anna.post(f"{GUEST}/ask", data={"question": "Question from Anna?"})
    bruno_page = page_text(bruno.get(GUEST))
    anna_page = page_text(anna.get(GUEST))

    assert "Question from Anna?" in anna_page and "Answer for Anna." in anna_page
    assert "Question from Anna?" not in bruno_page and "Answer for Anna." not in bruno_page


def test_start_over_clears_only_that_guests_conversation(data_folder):
    anna, _ = make_app(data_folder, "Answer A.\nSOURCE: the-house.md", "Answer B.\nSOURCE: the-house.md")
    bruno = anna.application.test_client()
    anna.post(f"{GUEST}/ask", data={"question": "Question from Anna?"})
    bruno.post(f"{GUEST}/ask", data={"question": "Question from Bruno?"})

    anna.post(f"{GUEST}/reset")

    assert "Question from Anna?" not in page_text(anna.get(GUEST))
    assert "Question from Bruno?" in page_text(bruno.get(GUEST))


def test_conversation_survives_a_new_app_process(data_folder):
    """PythonAnywhere runs several processes: another process must see the same conversation."""
    first_process, _ = make_app(data_folder, "Saved answer.\nSOURCE: the-house.md")
    first_process.post(f"{GUEST}/ask", data={"question": "Saved question?"})

    second_process, _ = make_app(data_folder)
    with first_process.session_transaction() as cookie:
        guest_id = cookie["guest_id"]
    with second_process.session_transaction() as cookie:
        cookie["guest_id"] = guest_id

    assert "Saved question?" in page_text(second_process.get(GUEST))


@pytest.mark.parametrize("bad_id", ["../app", r"..\..\.env", "not-a-valid-id", 42])
def test_invalid_guest_id_in_the_session_is_replaced(data_folder, bad_id):
    browser, _ = make_app(data_folder, "Answer.\nSOURCE: the-house.md")
    (data_folder / "conversas" / "app.json").parent.mkdir(parents=True)
    (data_folder / "conversas" / "app.json").write_text('[{"question": "leaked", "answer": {"text": "x"}}]', encoding="utf-8")
    with browser.session_transaction() as cookie:
        cookie["guest_id"] = bad_id

    html = page_text(browser.get(GUEST))
    browser.post(f"{GUEST}/ask", data={"question": "My question?"})

    assert "leaked" not in html
    with browser.session_transaction() as cookie:
        assert cookie["guest_id"] != bad_id
        assert len(cookie["guest_id"]) == 32
    assert "My question?" in page_text(browser.get(GUEST))


def test_page_shows_only_the_last_20_questions(data_folder, monkeypatch):
    monkeypatch.setenv("GUEST_QUESTIONS_PER_HOUR", "100")  # this test is about the history, not the limit
    replies = [f"Answer {n}.\nSOURCE: the-house.md" for n in range(1, 23)]
    browser, _ = make_app(data_folder, *replies)

    for n in range(1, 23):
        browser.post(f"{GUEST}/ask", data={"question": f"Question number {n}?"})
    html = page_text(browser.get(GUEST))

    assert "Question number 1?" not in html and "Question number 2?" not in html
    assert "Question number 3?" in html and "Question number 22?" in html
    assert html.count('class="message guest"') == 20


@pytest.mark.parametrize("setting", ["SECRET_KEY", "HOST_PASSWORD_HASH"])
def test_app_refuses_to_start_without_a_required_setting(data_folder, monkeypatch, setting):
    monkeypatch.delenv(setting)

    with pytest.raises(RuntimeError, match=setting):
        create_app(client=FakeGeminiClient(), data_folder=data_folder)


# ---------- Question limits ----------

def test_guest_hourly_limit_stops_questions_before_the_api(data_folder, monkeypatch):
    monkeypatch.setenv("GUEST_QUESTIONS_PER_HOUR", "2")
    browser, fake = make_app(data_folder, "One.\nSOURCE: the-house.md", "Two.\nSOURCE: the-house.md")

    browser.post(f"{GUEST}/ask", data={"question": "First?"})
    browser.post(f"{GUEST}/ask", data={"question": "Second?"})
    html = page_text(browser.post(f"{GUEST}/ask", data={"question": "Third?"}, follow_redirects=True))

    assert "a lot of questions in the last hour" in html
    assert len(fake.models.calls) == 2  # the third question never reached the API
    assert "Third?" not in html


def test_guest_limit_applies_to_each_guest_separately(data_folder, monkeypatch):
    monkeypatch.setenv("GUEST_QUESTIONS_PER_HOUR", "1")
    anna, fake = make_app(data_folder, "For Anna.\nSOURCE: the-house.md", "For Bruno.\nSOURCE: the-house.md")
    bruno = anna.application.test_client()

    anna.post(f"{GUEST}/ask", data={"question": "Anna asks?"})
    html = page_text(bruno.post(f"{GUEST}/ask", data={"question": "Bruno asks?"}, follow_redirects=True))

    assert "For Bruno." in html
    assert len(fake.models.calls) == 2


def test_daily_limit_counts_all_guests_together(data_folder, monkeypatch):
    monkeypatch.setenv("QUESTIONS_PER_DAY", "2")
    first, fake = make_app(data_folder, "A.\nSOURCE: the-house.md", "B.\nSOURCE: the-house.md")
    second, third = first.application.test_client(), first.application.test_client()

    first.post(f"{GUEST}/ask", data={"question": "One?"})
    second.post(f"{GUEST}/ask", data={"question": "Two?"})
    html = page_text(third.post(f"{GUEST}/ask", data={"question": "Three?"}, follow_redirects=True))

    assert "limit of questions for today" in html
    assert len(fake.models.calls) == 2


def test_limit_message_uses_the_browser_language(data_folder, monkeypatch):
    monkeypatch.setenv("QUESTIONS_PER_DAY", "1")
    browser, _ = make_app(data_folder, "A.\nSOURCE: the-house.md")
    browser.post(f"{GUEST}/ask", data={"question": "One?"})

    html = page_text(browser.post(f"{GUEST}/ask", data={"question": "Duas?"}, follow_redirects=True,
                                  headers={"Accept-Language": "pt-PT,pt;q=0.9"}))

    assert "O assistente atingiu o limite de perguntas por hoje." in html


def test_empty_questions_do_not_count_towards_the_limit(data_folder, monkeypatch):
    monkeypatch.setenv("GUEST_QUESTIONS_PER_HOUR", "1")
    browser, fake = make_app(data_folder, "Real answer.\nSOURCE: the-house.md")

    for _ in range(3):
        browser.post(f"{GUEST}/ask", data={"question": "   "})
    html = page_text(browser.post(f"{GUEST}/ask", data={"question": "Real question?"}, follow_redirects=True))

    assert "Real answer." in html


def test_limit_does_not_log_the_question_text(data_folder, monkeypatch, caplog):
    monkeypatch.setenv("GUEST_QUESTIONS_PER_HOUR", "1")
    browser, _ = make_app(data_folder, "A.\nSOURCE: the-house.md")
    browser.post(f"{GUEST}/ask", data={"question": "First?"})

    browser.post(f"{GUEST}/ask", data={"question": "My room is 3B and my name is Ana Silva"})

    assert "hourly question limit" in caplog.text
    assert "Ana Silva" not in caplog.text


@pytest.mark.parametrize("value", ["0", "-5", "ten", "2.5"])
def test_invalid_limit_setting_stops_the_app(data_folder, monkeypatch, value):
    monkeypatch.setenv("QUESTIONS_PER_DAY", value)

    with pytest.raises(RuntimeError, match="QUESTIONS_PER_DAY"):
        create_app(client=FakeGeminiClient(), data_folder=data_folder)
