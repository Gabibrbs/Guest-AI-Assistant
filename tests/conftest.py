"""Settings that apply to every test."""

import pytest
from werkzeug.security import generate_password_hash

HOST_PASSWORD = "test-host-password"
HOST_PASSWORD_HASH = generate_password_hash(HOST_PASSWORD)  # made once: hashing is slow on purpose

# The test property: its slug and the addresses of its guest and host pages
SLUG = "casa-test-abc123"
GUEST = f"/p/{SLUG}"
HOST_GUIDE = f"/host/p/{SLUG}"

TEST_CONFIG = f"""
[[property]]
slug = "{SLUG}"
name = "Casa Test Example"
color = "#2f6f4e"
not_found_message = "Please message the host on Airbnb."
host_contact = "WhatsApp +351 000 000 001"
"""


@pytest.fixture
def data_folder(tmp_path):
    """A data folder like dados/: config.toml with one property and a 2-document guide."""
    folder = tmp_path / "dados"
    documents = folder / "alojamentos" / SLUG / "documentos"
    documents.mkdir(parents=True)
    (documents / "the-house.md").write_text("Wi-Fi password: azulejo2026", encoding="utf-8")
    (documents / "house-rules.md").write_text("Quiet hours from 22:00.", encoding="utf-8")
    (folder / "config.toml").write_text(TEST_CONFIG, encoding="utf-8")
    return folder


@pytest.fixture
def documents_folder(data_folder):
    """The test property's documents folder."""
    return data_folder / "alojamentos" / SLUG / "documentos"


@pytest.fixture(autouse=True)
def no_real_api_key(monkeypatch):
    """Remove the API key during the tests, so no test can ever call the real Gemini API."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


@pytest.fixture(autouse=True)
def no_real_waiting(monkeypatch):
    """New attempts after errors wait 5 s and 10 s: in the tests they do not wait at all."""
    monkeypatch.setattr("assistant.gemini_client.time.sleep", lambda seconds: None)


@pytest.fixture(autouse=True)
def test_settings(monkeypatch):
    """The app refuses to start without these settings, so the tests use fixed ones."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("HOST_PASSWORD_HASH", HOST_PASSWORD_HASH)
    # The limits use their defaults unless a test sets them (never the values in a real .env)
    monkeypatch.delenv("GUEST_QUESTIONS_PER_HOUR", raising=False)
    monkeypatch.delenv("QUESTIONS_PER_DAY", raising=False)
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
