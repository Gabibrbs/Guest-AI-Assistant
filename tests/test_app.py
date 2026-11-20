"""Flask routes: home page, asking a question, uploading a document, starting over.

Each test builds its own app with a fake Gemini client and a small documents folder.
"""

import io

import pytest
from helpers import FakeGeminiClient, api_error, make_pdf

from app import clean_filename, create_app


@pytest.fixture
def documents_folder(tmp_path):
    (tmp_path / "the-house.md").write_text("Wi-Fi password: azulejo2026", encoding="utf-8")
    (tmp_path / "house-rules.md").write_text("Quiet hours from 22:00.", encoding="utf-8")
    return tmp_path


def make_app(documents_folder, *replies):
    """App with a fake client that will give `replies`, plus a Flask test browser."""
    fake = FakeGeminiClient(*replies)
    app = create_app(client=fake, documents_folder=documents_folder)
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
    app = create_app(client=None, documents_folder=documents_folder)  # no fake: the real client is needed
    browser = app.test_client()

    html = page_text(browser.post("/ask", data={"question": "Question?"}, follow_redirects=True))

    assert "GEMINI_API_KEY is not set" in html


# ---------- Uploading ----------

def upload(browser, filename, data):
    return browser.post(
        "/upload",
        data={"document": (io.BytesIO(data), filename)},
        content_type="multipart/form-data",
        follow_redirects=True,
    )


def test_uploaded_text_document_is_listed_and_used(documents_folder):
    browser, fake = make_app(documents_folder, "Breakfast costs 12 euros.\nSOURCE: breakfast.txt")

    html = page_text(upload(browser, "breakfast.txt", b"Breakfast basket: 12 euros per person."))
    assert "breakfast.txt was added" in html
    assert "3 documents" in html
    assert "uploaded" in html

    html = page_text(browser.post("/ask", data={"question": "Breakfast?"}, follow_redirects=True))
    assert '<document name="breakfast.txt">' in fake.models.calls[0]["contents"]
    assert "Source: breakfast.txt" in html


def test_upload_pdf(documents_folder):
    browser, fake = make_app(documents_folder, "Ok.\nSOURCE: map.pdf")

    upload(browser, "map.pdf", make_pdf("The metro is 5 minutes away"))
    browser.post("/ask", data={"question": "Metro?"})

    assert "The metro is 5 minutes away" in fake.models.calls[0]["contents"]


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


@pytest.mark.parametrize("original, cleaned", [("../Guia da casa.txt", "Guia_da_casa.txt"), ("指南.txt", "document.txt")])
def test_uploaded_file_name_is_cleaned(documents_folder, original, cleaned):
    browser, _ = make_app(documents_folder)

    html = page_text(upload(browser, original, b"Some text"))

    assert f"{cleaned} was added" in html


@pytest.mark.parametrize(
    "filename, data, message",
    [
        ("empty.txt", b"", "the file has no text"),
        ("photo.jpg", b"image bytes", "only .md, .txt and .pdf"),
        ("broken.pdf", b"not a pdf", "the PDF could not be read"),
    ],
)
def test_invalid_upload_shows_error_and_is_not_added(documents_folder, filename, data, message):
    browser, _ = make_app(documents_folder)

    html = page_text(upload(browser, filename, data))

    assert message in html
    assert "2 documents" in html


def test_upload_without_file(documents_folder):
    browser, _ = make_app(documents_folder)

    html = page_text(browser.post("/upload", data={}, follow_redirects=True))

    assert "Choose a file to upload." in html


def test_document_with_too_much_text_is_refused(documents_folder):
    browser, _ = make_app(documents_folder)

    html = page_text(upload(browser, "long.txt", b"a" * 50_001))

    assert "too long for this demo" in html
    assert "2 documents" in html


def test_file_larger_than_the_limit_is_refused(documents_folder):
    app = create_app(client=FakeGeminiClient(), documents_folder=documents_folder)
    app.config["MAX_CONTENT_LENGTH"] = 100  # bytes, so the test file can stay small
    browser = app.test_client()

    html = page_text(upload(browser, "big.txt", b"a" * 1000))

    assert "larger than" in html
    assert "2 documents" in html


# ---------- Starting over ----------

def test_start_over_clears_history_and_uploads(documents_folder):
    browser, _ = make_app(documents_folder, "Answer.\nSOURCE: the-house.md")
    upload(browser, "extra.txt", b"Extra text")
    browser.post("/ask", data={"question": "My question?"})

    html = page_text(browser.post("/reset", follow_redirects=True))

    assert "My question?" not in html
    assert "extra.txt" not in html
    assert "2 documents" in html
