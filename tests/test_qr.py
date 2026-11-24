"""Printable QR codes: the module, the host's download button and the script."""

import io

import pytest
import qrcode
from conftest import HOST_GUIDE, HOST_PASSWORD, SLUG
from helpers import FakeGeminiClient
from PIL import Image

import make_qr_codes
from app import create_app
from assistant.qr import (
    MARGIN,
    QR_WIDTH,
    WIDTH,
    PublicAddressError,
    check_public_base_url,
    guest_link,
    make_qr_code,
    make_qr_png,
)

LINK = "https://account.pythonanywhere.com/p/casa-da-ribeira-k7q3xz"


def qr_in_image(png, link):
    """True if the PNG really draws the QR code of `link`, square by square.

    Without a QR reader in the tests, the image is compared with the matrix the qrcode
    library calculated: the centre of each square must be black exactly where it should.
    """
    code = make_qr_code(link)
    modules = code.modules_count + 2 * code.border
    box = QR_WIDTH // modules
    left = (WIDTH - modules * box) // 2
    image = Image.open(io.BytesIO(png)).convert("L")  # grey levels: 0 black, 255 white
    for row, squares in enumerate(code.get_matrix()):  # get_matrix includes the white border
        for column, is_black in enumerate(squares):
            x = left + column * box + box // 2
            y = MARGIN + row * box + box // 2
            if (image.getpixel((x, y)) < 128) != is_black:
                return False
    return True


# ---------- Public address ----------

@pytest.mark.parametrize("value, expected", [
    ("https://account.pythonanywhere.com", "https://account.pythonanywhere.com"),
    ("https://account.pythonanywhere.com/", "https://account.pythonanywhere.com"),
    ("  https://guide.example.com  ", "https://guide.example.com"),
    ("http://localhost:5000", "http://localhost:5000"),
])
def test_valid_public_address(value, expected):
    assert check_public_base_url(value) == expected


@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_public_address_is_refused(value):
    with pytest.raises(PublicAddressError, match="PUBLIC_BASE_URL is missing"):
        check_public_base_url(value)


@pytest.mark.parametrize("value", [
    "account.pythonanywhere.com", "ftp://account.pythonanywhere.com", "https://",
    "https://example.com?x=1", "https://example.com#top", "localhost:5000",
])
def test_invalid_public_address_is_refused(value):
    with pytest.raises(PublicAddressError, match="must be a web address"):
        check_public_base_url(value)


def test_guest_link():
    assert guest_link("https://account.pythonanywhere.com", "casa-da-ribeira-k7q3xz") == LINK


# ---------- The image ----------

def test_qr_code_holds_the_link_with_high_error_correction():
    code = make_qr_code(LINK)

    assert code.data_list[0].data == LINK.encode()
    assert code.error_correction == qrcode.constants.ERROR_CORRECT_H


def test_png_draws_the_qr_code_of_the_link():
    png = make_qr_png(LINK, "Casa da Ribeira Example")

    assert qr_in_image(png, LINK)
    assert not qr_in_image(png, LINK + "x")  # the check really tells links apart


def test_png_is_large_white_and_ready_to_print():
    image = Image.open(io.BytesIO(make_qr_png(LINK, "Casa da Ribeira Example")))

    assert image.format == "PNG"
    assert image.width == WIDTH and image.height > WIDTH  # room for the text below the QR code
    assert round(image.info["dpi"][0]) == 300
    assert image.convert("RGB").getpixel((5, 5)) == (255, 255, 255)
    assert image.convert("RGB").getpixel((5, image.height - 5)) == (255, 255, 255)


def test_text_is_drawn_below_the_qr_code():
    image = Image.open(io.BytesIO(make_qr_png(LINK, "Casa da Ribeira Example"))).convert("L")
    below_qr = image.crop((0, MARGIN + QR_WIDTH, WIDTH, image.height))

    assert below_qr.getextrema()[0] < 128  # something dark (the text) is there


def test_very_long_name_still_fits():
    name = "Casa da Ribeira Example with a Very Long Name for Testing the Font Size"

    image = Image.open(io.BytesIO(make_qr_png(LINK, name)))

    assert image.width == WIDTH


# ---------- Download button on the host page ----------

def make_app(data_folder):
    app = create_app(client=FakeGeminiClient(), data_folder=data_folder)
    app.config["TESTING"] = True
    return app


def logged_in_host(app):
    browser = app.test_client()
    browser.post("/host", data={"password": HOST_PASSWORD})
    return browser


def test_property_page_has_the_download_button(data_folder):
    html = logged_in_host(make_app(data_folder)).get(HOST_GUIDE).get_data(as_text=True)

    assert "Download QR code" in html
    assert f'href="{HOST_GUIDE}/qr-code.png"' in html


def test_download_gives_the_printable_png(data_folder, monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://account.pythonanywhere.com/")
    host = logged_in_host(make_app(data_folder))

    response = host.get(f"{HOST_GUIDE}/qr-code.png")

    link = f"https://account.pythonanywhere.com/p/{SLUG}"
    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert f"qr-code-{SLUG}.png" in response.headers["Content-Disposition"]
    assert qr_in_image(response.data, link)


def test_download_is_refused_without_the_public_address(data_folder):
    host = logged_in_host(make_app(data_folder))

    response = host.get(f"{HOST_GUIDE}/qr-code.png", follow_redirects=True)

    assert response.mimetype == "text/html"
    assert "PUBLIC_BASE_URL is missing" in response.get_data(as_text=True)


def test_download_is_refused_with_a_wrong_public_address(data_folder, monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "account.pythonanywhere.com")
    host = logged_in_host(make_app(data_folder))

    response = host.get(f"{HOST_GUIDE}/qr-code.png", follow_redirects=True)

    assert "must be a web address" in response.get_data(as_text=True)


def test_download_needs_login(data_folder, monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://account.pythonanywhere.com")

    response = make_app(data_folder).test_client().get(f"{HOST_GUIDE}/qr-code.png")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/host")


def test_download_for_unknown_property_is_not_found(data_folder, monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://account.pythonanywhere.com")

    assert logged_in_host(make_app(data_folder)).get("/host/p/nope/qr-code.png").status_code == 404


def test_host_pages_show_the_public_link_when_it_is_set(data_folder, monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://account.pythonanywhere.com")
    host = logged_in_host(make_app(data_folder))

    for page in ["/host", HOST_GUIDE]:
        assert f"https://account.pythonanywhere.com/p/{SLUG}" in host.get(page).get_data(as_text=True)


# ---------- Script ----------

def test_script_saves_one_qr_code_per_property(data_folder):
    saved = make_qr_codes.make_all(data_folder, "https://account.pythonanywhere.com")

    link, path = saved[0]
    assert len(saved) == 1
    assert link == f"https://account.pythonanywhere.com/p/{SLUG}"
    assert path == data_folder / "alojamentos" / SLUG / "qr-code.png"
    assert qr_in_image(path.read_bytes(), link)


def test_script_refuses_without_the_public_address(data_folder, monkeypatch, capsys):
    monkeypatch.setattr(make_qr_codes, "load_dotenv", lambda: None)  # never read the real .env here
    monkeypatch.setenv("DATA_FOLDER", str(data_folder))

    with pytest.raises(SystemExit) as stopped:
        make_qr_codes.main()

    assert stopped.value.code == 1
    assert "PUBLIC_BASE_URL is missing" in capsys.readouterr().out
    assert not (data_folder / "alojamentos" / SLUG / "qr-code.png").exists()
