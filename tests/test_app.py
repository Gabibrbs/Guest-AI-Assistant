"""Guest pages: home page, asking a question, starting over, one conversation per guest.

Each test builds its own app with a fake Gemini client and a small documents folder.
"""

import io

import pytest
from helpers import FakeGeminiClient, api_error

from app import clean_filename, create_app


@pytest.fixture
def documents_folder(tmp_path):
    (tmp_path / "the-house.md").write_text("Wi-Fi password: azulejo2026", encoding="utf-8")
    (tmp_path / "house-rules.md").write_text("Quiet hours from 22:00.", encoding="utf-8")
    return tmp_path


def make_app(documents_folder, *replies):
    """App with a fake client that will give `replies`, plus a Flask test browser."""
    fake = FakeGeminiClient(*replies)
    app = create_app(client=fake, documents_folder=documents_folder,
                     conversations_folder=documents_folder / "conversas")
    app.config["TESTING"] = True
    return app.test_client(), fake


def page_text(response):
    return response.get_data(as_text=True)


# ---------- Home page ----------

def test_home_page_shows_business_documents_and_examples(documents_folder):
    browser, fake = make_app(documents_folder)

    response = browser.get("/")

    assert response.status_code == 200
    html = page_text(response)
    assert "Casa da Ribeira Example" in html
    assert "the-house.md" in html and "house-rules.md" in html
    assert "2 documents" in html
    assert "What is the Wi-Fi password?" in html  # example question
    assert fake.models.calls == []                 # opening the page does not call the model


# ---------- Asking ----------

def test_question_shows_answer_and_source(documents_folder):
    browser, fake = make_app(documents_folder, "A palavra-passe é azulejo2026.\nSOURCE: the-house.md")

    response = browser.post("/ask", data={"question": "Qual é a palavra-passe?"}, follow_redirects=True)

    html = page_text(response)
    assert "Qual é a palavra-passe?" in html
    assert "A palavra-passe é azulejo2026." in html
    assert "Source: the-house.md" in html
    assert "Wi-Fi password: azulejo2026" in fake.models.calls[0]["contents"]  # documents were sent


def test_question_not_in_documents_shows_contact_host(documents_folder):
    browser, _ = make_app(documents_folder, "Not in the house guide. Please contact the host.\nSOURCE: none")

    html = page_text(browser.post("/ask", data={"question": "Do you have a cot?"}, follow_redirects=True))

    assert "Not in the house guide · please contact the host" in html
    assert "Source:" not in html


def test_conversation_history_is_kept(documents_folder):
    browser, _ = make_app(
        documents_folder,
        "First answer.\nSOURCE: the-house.md",
        "Second answer.\nSOURCE: house-rules.md",
    )

    browser.post("/ask", data={"question": "First question?"})
    html = page_text(browser.post("/ask", data={"question": "Second question?"}, follow_redirects=True))

    assert html.index("First question?") < html.index("Second question?")
    assert "First answer." in html and "Second answer." in html


def test_ask_redirects_to_the_latest_answer(documents_folder):
    browser, _ = make_app(documents_folder, "Answer.\nSOURCE: the-house.md")

    response = browser.post("/ask", data={"question": "Question?"})

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/#latest")


@pytest.mark.parametrize("question", ["", "    "])
def test_empty_question_is_refused_without_calling_the_model(documents_folder, question):
    browser, fake = make_app(documents_folder)

    html = page_text(browser.post("/ask", data={"question": question}, follow_redirects=True))

    assert "Please type a question." in html
    assert fake.models.calls == []


def test_api_error_is_shown_to_the_user(documents_folder):
    browser, _ = make_app(documents_folder, api_error(403))

    html = page_text(browser.post("/ask", data={"question": "Question?"}, follow_redirects=True))

    assert "could not answer" in html


def test_missing_api_key_is_shown_to_the_user(documents_folder, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    app = create_app(client=None, documents_folder=documents_folder,  # no fake: the real client is needed
                     conversations_folder=documents_folder / "conversas")
    browser = app.test_client()

    html = page_text(browser.post("/ask", data={"question": "Question?"}, follow_redirects=True))

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

def test_start_over_clears_only_the_conversation(documents_folder):
    browser, _ = make_app(documents_folder, "Answer.\nSOURCE: the-house.md")
    browser.post("/ask", data={"question": "My question?"})

    html = page_text(browser.post("/reset", follow_redirects=True))

    assert "My question?" not in html
    assert "Your conversation was cleared." in html
    assert "2 documents" in html  # the house guide is not touched


# ---------- Guests cannot change the guide ----------

def test_guest_page_has_no_upload(documents_folder):
    browser, _ = make_app(documents_folder)

    html = page_text(browser.get("/"))

    assert 'type="file"' not in html
    assert "Upload" not in html


def test_old_guest_upload_address_no_longer_exists(documents_folder):
    browser, _ = make_app(documents_folder)

    response = browser.post(
        "/upload",
        data={"document": (io.BytesIO(b"Fake rule"), "rules.txt")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 404
    assert not (documents_folder / "rules.txt").exists()


# ---------- One conversation per guest ----------

def test_two_guests_have_separate_conversations(documents_folder):
    anna, fake = make_app(documents_folder, "Answer for Anna.\nSOURCE: the-house.md")
    bruno = anna.application.test_client()  # a second browser on the same app

    anna.post("/ask", data={"question": "Question from Anna?"})
    bruno_page = page_text(bruno.get("/"))
    anna_page = page_text(anna.get("/"))

    assert "Question from Anna?" in anna_page and "Answer for Anna." in anna_page
    assert "Question from Anna?" not in bruno_page and "Answer for Anna." not in bruno_page


def test_start_over_clears_only_that_guests_conversation(documents_folder):
    anna, _ = make_app(documents_folder, "Answer A.\nSOURCE: the-house.md", "Answer B.\nSOURCE: the-house.md")
    bruno = anna.application.test_client()
    anna.post("/ask", data={"question": "Question from Anna?"})
    bruno.post("/ask", data={"question": "Question from Bruno?"})

    anna.post("/reset")

    assert "Question from Anna?" not in page_text(anna.get("/"))
    assert "Question from Bruno?" in page_text(bruno.get("/"))


def test_conversation_survives_a_new_app_process(documents_folder):
    """PythonAnywhere runs several processes: another process must see the same conversation."""
    first_process, _ = make_app(documents_folder, "Saved answer.\nSOURCE: the-house.md")
    first_process.post("/ask", data={"question": "Saved question?"})

    second_process, _ = make_app(documents_folder)
    with first_process.session_transaction() as cookie:
        guest_id = cookie["guest_id"]
    with second_process.session_transaction() as cookie:
        cookie["guest_id"] = guest_id

    assert "Saved question?" in page_text(second_process.get("/"))


@pytest.mark.parametrize("bad_id", ["../app", r"..\..\.env", "not-a-valid-id", 42])
def test_invalid_guest_id_in_the_session_is_replaced(documents_folder, bad_id):
    browser, _ = make_app(documents_folder, "Answer.\nSOURCE: the-house.md")
    (documents_folder / "app.json").write_text('[{"question": "leaked", "answer": {"text": "x"}}]', encoding="utf-8")
    with browser.session_transaction() as cookie:
        cookie["guest_id"] = bad_id

    html = page_text(browser.get("/"))
    browser.post("/ask", data={"question": "My question?"})

    assert "leaked" not in html
    with browser.session_transaction() as cookie:
        assert cookie["guest_id"] != bad_id
        assert len(cookie["guest_id"]) == 32
    assert "My question?" in page_text(browser.get("/"))


def test_page_shows_only_the_last_20_questions(documents_folder):
    replies = [f"Answer {n}.\nSOURCE: the-house.md" for n in range(1, 23)]
    browser, _ = make_app(documents_folder, *replies)

    for n in range(1, 23):
        browser.post("/ask", data={"question": f"Question number {n}?"})
    html = page_text(browser.get("/"))

    assert "Question number 1?" not in html and "Question number 2?" not in html
    assert "Question number 3?" in html and "Question number 22?" in html
    assert html.count('class="message guest"') == 20


@pytest.mark.parametrize("setting", ["SECRET_KEY", "HOST_PASSWORD_HASH"])
def test_app_refuses_to_start_without_a_required_setting(documents_folder, monkeypatch, setting):
    monkeypatch.delenv(setting)

    with pytest.raises(RuntimeError, match=setting):
        create_app(client=FakeGeminiClient(), documents_folder=documents_folder)
