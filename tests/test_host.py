"""Host pages: login with a password, then upload, replace or delete documents.

Documents are saved in the documents folder on disk, so the tests check the files too.
"""

import io

import pytest
from conftest import HOST_PASSWORD
from helpers import FakeGeminiClient, make_pdf

import set_host_password
from app import create_app
from werkzeug.security import check_password_hash


@pytest.fixture
def documents_folder(tmp_path):
    folder = tmp_path / "documentos"
    folder.mkdir()
    (folder / "the-house.md").write_text("Wi-Fi password: azulejo2026", encoding="utf-8")
    (folder / "house-rules.md").write_text("Quiet hours from 22:00.", encoding="utf-8")
    return folder


def make_app(documents_folder, *replies):
    fake = FakeGeminiClient(*replies)
    app = create_app(client=fake, documents_folder=documents_folder,
                     conversations_folder=documents_folder.parent / "conversas")
    app.config["TESTING"] = True
    return app, fake


def page_text(response):
    return response.get_data(as_text=True)


def log_in(browser, password=HOST_PASSWORD):
    return browser.post("/host", data={"password": password}, follow_redirects=True)


def upload(browser, filename, data):
    return browser.post(
        "/host/upload",
        data={"document": (io.BytesIO(data), filename)},
        content_type="multipart/form-data",
        follow_redirects=True,
    )


@pytest.fixture
def host(documents_folder):
    """A browser already logged in as the host."""
    app, _ = make_app(documents_folder)
    browser = app.test_client()
    log_in(browser)
    return browser


# ---------- Logging in ----------

def test_login_page_opens(documents_folder):
    app, _ = make_app(documents_folder)

    html = page_text(app.test_client().get("/host"))

    assert 'type="password"' in html
    assert "Host login" in html


def test_right_password_opens_the_documents_page(documents_folder):
    app, _ = make_app(documents_folder)

    html = page_text(log_in(app.test_client()))

    assert "Add or replace a document" in html
    assert "the-house.md" in html and "house-rules.md" in html


@pytest.mark.parametrize("password", ["wrong-password", "", HOST_PASSWORD.upper(), HOST_PASSWORD + " "])
def test_wrong_password_is_refused(documents_folder, password):
    app, _ = make_app(documents_folder)
    browser = app.test_client()

    html = page_text(log_in(browser, password))

    assert "Wrong password." in html
    assert "Add or replace a document" not in html
    assert browser.get("/host/documents").status_code == 302  # still not logged in


def test_logout_closes_the_host_area(host):
    host.post("/host/logout")

    response = host.get("/host/documents")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/host")


def test_session_cookie_is_not_sent_from_other_websites(documents_folder):
    app, _ = make_app(documents_folder)

    response = app.test_client().get("/")

    assert "SameSite=Lax" in response.headers["Set-Cookie"]


# ---------- Guests cannot use the host pages ----------

def test_documents_page_needs_login(documents_folder):
    app, _ = make_app(documents_folder)

    response = app.test_client().get("/host/documents", follow_redirects=True)

    assert "Please log in as the host." in page_text(response)
    assert "Add or replace a document" not in page_text(response)


def test_upload_needs_login(documents_folder):
    app, _ = make_app(documents_folder)

    html = page_text(upload(app.test_client(), "fake-rules.txt", b"Parties are allowed."))

    assert "Please log in as the host." in html
    assert not (documents_folder / "fake-rules.txt").exists()


def test_delete_needs_login(documents_folder):
    app, _ = make_app(documents_folder)

    app.test_client().post("/host/delete", data={"name": "the-house.md"})

    assert (documents_folder / "the-house.md").exists()


def test_host_and_guest_sessions_are_separate(documents_folder):
    app, _ = make_app(documents_folder)
    host_browser, guest_browser = app.test_client(), app.test_client()
    log_in(host_browser)

    assert host_browser.get("/host/documents").status_code == 200
    assert guest_browser.get("/host/documents").status_code == 302


# ---------- Uploading ----------

def test_uploaded_document_is_saved_and_used_by_guests(documents_folder):
    app, fake = make_app(documents_folder, "Breakfast costs 12 euros.\nSOURCE: breakfast.txt")
    host_browser, guest_browser = app.test_client(), app.test_client()
    log_in(host_browser)

    html = page_text(upload(host_browser, "breakfast.txt", b"Breakfast basket: 12 euros per person."))
    assert "breakfast.txt was added" in html
    assert "3 documents" in html
    assert (documents_folder / "breakfast.txt").read_bytes() == b"Breakfast basket: 12 euros per person."

    guest_html = page_text(guest_browser.post("/ask", data={"question": "Breakfast?"}, follow_redirects=True))
    assert '<document name="breakfast.txt">' in fake.models.calls[0]["contents"]
    assert "Source: breakfast.txt" in guest_html


def test_uploaded_document_survives_a_restart(documents_folder, host):
    upload(host, "breakfast.txt", b"Breakfast basket: 12 euros per person.")

    restarted, _ = make_app(documents_folder)  # a new app, like after a reload on PythonAnywhere

    assert "breakfast.txt" in page_text(restarted.test_client().get("/"))


def test_upload_pdf(documents_folder):
    app, fake = make_app(documents_folder, "Ok.\nSOURCE: map.pdf")
    host_browser = app.test_client()
    log_in(host_browser)

    upload(host_browser, "map.pdf", make_pdf("The metro is 5 minutes away"))
    app.test_client().post("/ask", data={"question": "Metro?"})

    assert "The metro is 5 minutes away" in fake.models.calls[0]["contents"]


def test_same_name_replaces_the_document(documents_folder, host):
    html = page_text(upload(host, "the-house.md", b"Wi-Fi password: newpassword2027"))

    assert "the-house.md was replaced" in html
    assert "2 documents" in html
    assert (documents_folder / "the-house.md").read_text(encoding="utf-8") == "Wi-Fi password: newpassword2027"


@pytest.mark.parametrize("original, cleaned", [("../Guia da casa.txt", "Guia_da_casa.txt"), ("指南.txt", "document.txt")])
def test_uploaded_file_name_is_cleaned(documents_folder, host, original, cleaned):
    html = page_text(upload(host, original, b"Some text"))

    assert f"{cleaned} was added" in html
    assert (documents_folder / cleaned).exists()
    assert not (documents_folder.parent / "Guia da casa.txt").exists()


@pytest.mark.parametrize(
    "filename, data, message",
    [
        ("empty.txt", b"", "the file has no text"),
        ("photo.jpg", b"image bytes", "only .md, .txt and .pdf"),
        ("broken.pdf", b"not a pdf", "the PDF could not be read"),
    ],
)
def test_invalid_upload_shows_error_and_is_not_saved(documents_folder, host, filename, data, message):
    html = page_text(upload(host, filename, data))

    assert message in html
    assert "2 documents" in html
    assert sorted(path.name for path in documents_folder.iterdir()) == ["house-rules.md", "the-house.md"]


def test_upload_without_file(host):
    html = page_text(host.post("/host/upload", data={}, follow_redirects=True))

    assert "Choose a file to upload." in html


def test_document_with_too_much_text_is_refused(documents_folder, host):
    html = page_text(upload(host, "long.txt", b"a" * 50_001))

    assert "too long" in html
    assert not (documents_folder / "long.txt").exists()


def test_file_larger_than_the_limit_is_refused(documents_folder):
    app, _ = make_app(documents_folder)
    app.config["MAX_CONTENT_LENGTH"] = 100  # bytes, so the test file can stay small
    browser = app.test_client()
    log_in(browser)

    html = page_text(upload(browser, "big.txt", b"a" * 1000))

    assert "larger than" in html
    assert not (documents_folder / "big.txt").exists()


# ---------- Deleting ----------

def test_delete_removes_the_document(documents_folder, host):
    html = page_text(host.post("/host/delete", data={"name": "house-rules.md"}, follow_redirects=True))

    assert "house-rules.md was deleted" in html
    assert "1 documents" in html
    assert not (documents_folder / "house-rules.md").exists()


@pytest.mark.parametrize("name", ["../conversas", "../../app.py", "missing.md", "", "the-house.md/.."])
def test_delete_refuses_names_not_in_the_guide(documents_folder, host, name):
    outside = documents_folder.parent / "app.py"
    outside.write_text("must survive", encoding="utf-8")

    html = page_text(host.post("/host/delete", data={"name": name}, follow_redirects=True))

    assert "That document does not exist." in html
    assert outside.exists()
    assert "2 documents" in html


def test_empty_guide_shows_a_warning(documents_folder, host):
    host.post("/host/delete", data={"name": "house-rules.md"})
    html = page_text(host.post("/host/delete", data={"name": "the-house.md"}, follow_redirects=True))

    assert "The guide is empty" in html


# ---------- Password script ----------

def test_password_script_makes_a_line_the_app_accepts():
    line = set_host_password.make_env_line("my-new-password")

    assert line.startswith("HOST_PASSWORD_HASH='") and line.endswith("'")
    assert "my-new-password" not in line  # only the hash is written
    saved_hash = line.split("=", 1)[1].strip("'")
    assert check_password_hash(saved_hash, "my-new-password")
    assert not check_password_hash(saved_hash, "another-password")
