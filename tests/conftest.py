"""Settings that apply to every test."""

import pytest
from werkzeug.security import generate_password_hash

HOST_PASSWORD = "test-host-password"
HOST_PASSWORD_HASH = generate_password_hash(HOST_PASSWORD)  # made once: hashing is slow on purpose


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
