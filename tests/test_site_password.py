"""The optional password for the whole site (SITE_PASSWORD_HASH) and the visitor's real IP
address behind PythonAnywhere's proxy (CLIENT_IP_HEADER)."""

import pytest
from conftest import GUEST, HOST_GUIDE, HOST_PASSWORD
from helpers import FakeGeminiClient
from werkzeug.security import check_password_hash, generate_password_hash

import set_host_password
from app import create_app

SITE_PASSWORD = "test-site-password"
SITE_PASSWORD_HASH = generate_password_hash(SITE_PASSWORD)


def make_app(data_folder, *replies):
    fake = FakeGeminiClient(*replies)
    app = create_app(client=fake, data_folder=data_folder)
    return app, fake


@pytest.fixture
def private(monkeypatch):
    """Turn the site password on for this test."""
    monkeypatch.setenv("SITE_PASSWORD_HASH", SITE_PASSWORD_HASH)


def page_text(response):
    return response.get_data(as_text=True)


# ---------- Off by default ----------

def test_site_is_open_without_the_setting(data_folder):
    app, _ = make_app(data_folder)

    assert app.test_client().get(GUEST).status_code == 200


def test_site_login_page_does_not_exist_when_the_site_is_open(data_folder):
    app, _ = make_app(data_folder)

    assert app.test_client().get("/site-login").status_code == 404


# ---------- On: nothing without the password ----------

@pytest.mark.parametrize("page", ["/", GUEST, f"{GUEST}/privacy", "/host", HOST_GUIDE])
def test_every_page_asks_for_the_site_password(data_folder, private, page):
    app, _ = make_app(data_folder)

    response = app.test_client().get(page)

    assert response.status_code == 302
    assert "/site-login?next=" in response.headers["Location"]


def test_guest_page_content_is_not_shown_without_the_password(data_folder, private):
    app, _ = make_app(data_folder)

    html = page_text(app.test_client().get(GUEST, follow_redirects=True))

    assert "Private test site" in html
    assert "Casa Test Example" not in html and "House guide" not in html


def test_question_without_the_password_never_reaches_the_api(data_folder, private):
    app, fake = make_app(data_folder, "never sent")

    app.test_client().post(f"{GUEST}/ask", data={"question": "Wi-Fi?"})

    assert fake.models.calls == []


def test_styles_load_without_the_password(data_folder, private):
    app, _ = make_app(data_folder)

    assert app.test_client().get("/static/style.css").status_code == 200


# ---------- Logging in ----------

def test_right_password_opens_the_page_asked_for(data_folder, private):
    app, _ = make_app(data_folder)
    browser = app.test_client()

    response = browser.post("/site-login", data={"password": SITE_PASSWORD, "next": GUEST})

    assert response.headers["Location"] == GUEST
    assert "Casa Test Example" in page_text(browser.get(GUEST))


def test_wrong_password_is_refused(data_folder, private):
    app, _ = make_app(data_folder)
    browser = app.test_client()

    html = page_text(browser.post("/site-login", data={"password": "wrong", "next": GUEST}, follow_redirects=True))

    assert "Wrong password." in html
    assert browser.get(GUEST).status_code == 302


def test_site_password_and_host_password_are_separate(data_folder, private):
    app, _ = make_app(data_folder)
    browser = app.test_client()
    browser.post("/site-login", data={"password": SITE_PASSWORD})

    assert browser.get(HOST_GUIDE).status_code == 302  # still needs the host password
    browser.post("/host", data={"password": HOST_PASSWORD})
    assert browser.get(HOST_GUIDE).status_code == 200


@pytest.mark.parametrize("next_page", ["//evil.example", "https://evil.example/", "evil.example", "/\\evil.example", ""])
def test_login_never_sends_the_visitor_to_another_website(data_folder, private, next_page):
    app, _ = make_app(data_folder)

    response = app.test_client().post("/site-login", data={"password": SITE_PASSWORD, "next": next_page})

    assert response.headers["Location"] == "/"


def test_site_login_is_blocked_after_5_failed_attempts(data_folder, private):
    app, _ = make_app(data_folder)
    browser = app.test_client()
    for _ in range(5):
        browser.post("/site-login", data={"password": "guess"})

    html = page_text(browser.post("/site-login", data={"password": SITE_PASSWORD}, follow_redirects=True))

    assert "Too many failed attempts" in html
    assert browser.get(GUEST).status_code == 302


def test_script_makes_the_site_password_line():
    line = set_host_password.make_env_line("my-site-password", "SITE_PASSWORD_HASH")

    assert line.startswith("SITE_PASSWORD_HASH='")
    assert check_password_hash(line.split("=", 1)[1].strip("'"), "my-site-password")


# ---------- Real IP address behind the proxy ----------

def fail_host_login(browser, address, real_ip):
    browser.post("/host", data={"password": "guess"},
                 environ_base={"REMOTE_ADDR": address}, headers={"X-Real-IP": real_ip})


def host_login_works(browser, address, real_ip):
    response = browser.post("/host", data={"password": HOST_PASSWORD}, follow_redirects=True,
                            environ_base={"REMOTE_ADDR": address}, headers={"X-Real-IP": real_ip})
    return "Your properties" in page_text(response)


def test_behind_pythonanywhere_limits_use_the_real_visitor_address(data_folder, monkeypatch):
    """All requests come from the load balancer (10.0.0.1); X-Real-IP tells visitors apart."""
    monkeypatch.setenv("CLIENT_IP_HEADER", "X-Real-IP")
    app, _ = make_app(data_folder)
    for _ in range(5):
        fail_host_login(app.test_client(), "10.0.0.1", "203.0.113.9")  # a guesser

    assert not host_login_works(app.test_client(), "10.0.0.1", "203.0.113.9")  # the guesser is blocked
    assert host_login_works(app.test_client(), "10.0.0.1", "198.51.100.7")     # the real host is not


def test_without_the_setting_the_header_is_ignored(data_folder):
    """On a server without the proxy, a visitor could write any address in X-Real-IP."""
    app, _ = make_app(data_folder)
    for number in range(5):
        fail_host_login(app.test_client(), "203.0.113.9", f"192.0.2.{number}")  # a new fake address each time

    assert not host_login_works(app.test_client(), "203.0.113.9", "192.0.2.99")  # still blocked


def test_missing_header_falls_back_to_the_connection_address(data_folder, monkeypatch):
    monkeypatch.setenv("CLIENT_IP_HEADER", "X-Real-IP")
    app, _ = make_app(data_folder)
    for _ in range(5):
        app.test_client().post("/host", data={"password": "guess"}, environ_base={"REMOTE_ADDR": "203.0.113.9"})

    response = app.test_client().post("/host", data={"password": HOST_PASSWORD}, follow_redirects=True,
                                      environ_base={"REMOTE_ADDR": "203.0.113.9"})
    assert "Too many failed attempts" in page_text(response)
