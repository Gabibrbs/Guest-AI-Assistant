"""Two properties in one installation: each with its own link, guide, look and conversations."""

import io
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import GUEST, HOST_PASSWORD
from helpers import FakeGeminiClient

from app import EXAMPLE_FOLDER, create_app

PROJECT_FOLDER = Path(__file__).parent.parent
CASA, LOFT = "casa-a-111111", "loft-b-222222"
PNG = b"\x89PNG\r\n\x1a\n" + b"rest of the image"

CONFIG = f"""
[[property]]
slug = "{CASA}"
name = "Casa A Example"
color = "#aa3300"
not_found_message = "Please message the host on Airbnb."
host_contact = "WhatsApp +351 000 000 001"

[[property]]
slug = "{LOFT}"
name = "Loft B Example"
color = "#2f6f4e"
logo = "logo.png"
not_found_message = "Please send us a message on Booking.com."
"""


@pytest.fixture
def two_properties(tmp_path):
    folder = tmp_path / "dados"
    for slug, text in [(CASA, "Door code: AAA111"), (LOFT, "Door code: BBB222")]:
        documents = folder / "alojamentos" / slug / "documentos"
        documents.mkdir(parents=True)
        (documents / "guide.md").write_text(text, encoding="utf-8")
    (folder / "alojamentos" / LOFT / "logo.png").write_bytes(PNG)
    (folder / "config.toml").write_text(CONFIG, encoding="utf-8")
    return folder


def make_app(data_folder, *replies):
    fake = FakeGeminiClient(*replies)
    app = create_app(client=fake, data_folder=data_folder)
    app.config["TESTING"] = True
    return app, fake


def page_text(response):
    return response.get_data(as_text=True)


def logged_in_host(app):
    browser = app.test_client()
    browser.post("/host", data={"password": HOST_PASSWORD})
    return browser


# ---------- Links ----------

def test_home_with_one_property_goes_straight_to_it(data_folder):
    app, _ = make_app(data_folder)

    response = app.test_client().get("/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith(GUEST)


def test_home_with_several_properties_does_not_list_them(two_properties):
    app, _ = make_app(two_properties)

    html = page_text(app.test_client().get("/"))

    assert "Please open the link or scan the QR code" in html
    for hidden in [CASA, LOFT, "Casa A Example", "Loft B Example"]:
        assert hidden not in html


@pytest.mark.parametrize("address", ["/p/casa-a", "/p/nope", f"/p/{CASA}x", "/p/", "/p/../host"])
def test_unknown_link_shows_page_not_found(two_properties, address):
    app, _ = make_app(two_properties)

    response = app.test_client().get(address)

    assert response.status_code == 404
    assert "This link does not work" in page_text(response)


def test_question_to_an_unknown_property_never_reaches_the_api(two_properties):
    app, fake = make_app(two_properties)

    response = app.test_client().post("/p/nope/ask", data={"question": "Door code?"})

    assert response.status_code == 404
    assert fake.models.calls == []


# ---------- Each guest sees only their property ----------

def test_guest_page_shows_only_its_property(two_properties):
    app, _ = make_app(two_properties)

    html = page_text(app.test_client().get(f"/p/{CASA}"))

    assert "Casa A Example" in html
    assert "Loft B Example" not in html
    assert "WhatsApp +351 000 000 001" in html          # host contact
    assert "--blue: #aa3300" in html                     # the property's color


def test_question_uses_only_that_propertys_guide(two_properties):
    app, fake = make_app(two_properties, "The code is AAA111.\nSOURCE: guide.md")

    app.test_client().post(f"/p/{CASA}/ask", data={"question": "Door code?"})

    prompt = fake.models.calls[0]["contents"]
    assert "AAA111" in prompt and "Casa A Example" in prompt
    assert "BBB222" not in prompt and "Loft B Example" not in prompt
    assert "Please message the host on Airbnb." in prompt


def test_conversations_are_separate_per_property(two_properties):
    app, _ = make_app(two_properties, "Answer about Casa A.\nSOURCE: guide.md")
    browser = app.test_client()  # the same guest opens both links

    browser.post(f"/p/{CASA}/ask", data={"question": "Question at Casa A?"})

    assert "Question at Casa A?" in page_text(browser.get(f"/p/{CASA}"))
    assert "Question at Casa A?" not in page_text(browser.get(f"/p/{LOFT}"))
    assert (two_properties / "conversas" / CASA).is_dir()


def test_logo_is_shown_and_served(two_properties):
    app, _ = make_app(two_properties)
    browser = app.test_client()

    html = page_text(browser.get(f"/p/{LOFT}"))
    logo = browser.get(f"/p/{LOFT}/logo")

    assert f'src="/p/{LOFT}/logo"' in html
    assert logo.status_code == 200
    assert logo.data == PNG
    assert logo.mimetype == "image/png"


def test_property_without_logo_shows_the_tile(two_properties):
    app, _ = make_app(two_properties)
    browser = app.test_client()

    assert 'class="tile"' in page_text(browser.get(f"/p/{CASA}"))
    assert browser.get(f"/p/{CASA}/logo").status_code == 404


# ---------- Messages near the question box ----------

def test_messages_appear_just_above_the_question_box(data_folder):
    app, _ = make_app(data_folder)

    html = page_text(app.test_client().post(f"{GUEST}/ask", data={"question": " "}, follow_redirects=True))

    message = html.index("Please type a question.")
    assert html.index('class="messages"') < message < html.index('class="ask"')


def test_errors_link_back_to_the_question_box(data_folder):
    app, _ = make_app(data_folder)

    response = app.test_client().post(f"{GUEST}/ask", data={"question": " "})

    assert response.headers["Location"].endswith(f"{GUEST}#ask")


# ---------- Host with several properties ----------

def test_host_sees_every_property_with_its_link(two_properties):
    app, _ = make_app(two_properties)

    html = page_text(logged_in_host(app).get("/host"))

    for slug, name in [(CASA, "Casa A Example"), (LOFT, "Loft B Example")]:
        assert name in html
        assert f"http://localhost/p/{slug}" in html
        assert f'href="/host/p/{slug}"' in html
    assert html.count("1 documents") == 2


def test_upload_goes_only_to_that_property(two_properties):
    app, fake = make_app(two_properties, "Ok.\nSOURCE: guide.md")
    host = logged_in_host(app)

    html = page_text(host.post(f"/host/p/{LOFT}/upload", data={"document": (io.BytesIO(b"Pool: 09:00"), "pool.md")},
                               content_type="multipart/form-data", follow_redirects=True))
    app.test_client().post(f"/p/{CASA}/ask", data={"question": "Pool?"})

    assert "pool.md was added" in html
    assert (two_properties / "alojamentos" / LOFT / "documentos" / "pool.md").exists()
    assert not (two_properties / "alojamentos" / CASA / "documentos" / "pool.md").exists()
    assert "Pool: 09:00" not in fake.models.calls[0]["contents"]


def test_delete_cannot_reach_another_propertys_document(two_properties):
    app, _ = make_app(two_properties)
    host = logged_in_host(app)
    (two_properties / "alojamentos" / LOFT / "documentos" / "only-loft.md").write_text("x", encoding="utf-8")

    html = page_text(host.post(f"/host/p/{CASA}/delete", data={"name": "only-loft.md"}, follow_redirects=True))

    assert "That document does not exist." in html
    assert (two_properties / "alojamentos" / LOFT / "documentos" / "only-loft.md").exists()


def test_host_page_of_unknown_property_is_not_found(two_properties):
    app, _ = make_app(two_properties)

    assert logged_in_host(app).get("/host/p/nope").status_code == 404


def test_too_large_upload_returns_to_the_property_page(two_properties):
    app, _ = make_app(two_properties)
    app.config["MAX_CONTENT_LENGTH"] = 100
    host = logged_in_host(app)

    response = host.post(f"/host/p/{LOFT}/upload", data={"document": (io.BytesIO(b"a" * 1000), "big.md")},
                         content_type="multipart/form-data")

    assert response.headers["Location"].endswith(f"/host/p/{LOFT}")


# ---------- The client's data never goes to Git ----------

def test_uploads_never_change_the_example_folder(tmp_path):
    data = tmp_path / "dados"
    shutil.copytree(EXAMPLE_FOLDER, data)  # exactly what the setup checklist does
    before = sorted(str(path.relative_to(EXAMPLE_FOLDER)) for path in EXAMPLE_FOLDER.rglob("*"))
    app, _ = make_app(data)

    logged_in_host(app).post("/host/p/casa-da-ribeira-demo/upload",
                             data={"document": (io.BytesIO(b"Client data"), "client-guide.md")},
                             content_type="multipart/form-data")

    after = sorted(str(path.relative_to(EXAMPLE_FOLDER)) for path in EXAMPLE_FOLDER.rglob("*"))
    assert after == before
    assert (data / "alojamentos" / "casa-da-ribeira-demo" / "documentos" / "client-guide.md").exists()


def git_ignores(path):
    result = subprocess.run(["git", "check-ignore", "-q", path], cwd=PROJECT_FOLDER)
    return result.returncode == 0  # 0 = ignored, 1 = not ignored


@pytest.mark.skipif(shutil.which("git") is None or not (PROJECT_FOLDER / ".git").exists(), reason="needs git")
def test_git_ignores_the_client_data_but_keeps_the_example():
    assert git_ignores("dados/config.toml")
    assert git_ignores("dados/alojamentos/casa-x-123456/documentos/guide.md")
    assert git_ignores("dados/alojamentos/casa-x-123456/logo.png")
    assert git_ignores("dados/conversas/casa-x-123456/abc.json")
    assert git_ignores("dados/limites.sqlite3")
    assert not git_ignores("exemplo/config.toml")
    assert not git_ignores("exemplo/alojamentos/casa-da-ribeira-demo/documentos/the-house.md")
