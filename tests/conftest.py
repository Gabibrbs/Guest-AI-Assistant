"""Settings that apply to every test."""

import pytest


@pytest.fixture(autouse=True)
def no_real_api_key(monkeypatch):
    """Remove the API key during the tests, so no test can ever call the real Gemini API."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


@pytest.fixture(autouse=True)
def no_real_waiting(monkeypatch):
    """New attempts after errors wait 5 s and 10 s: in the tests they do not wait at all."""
    monkeypatch.setattr("assistant.gemini_client.time.sleep", lambda seconds: None)


@pytest.fixture(autouse=True)
def test_secret_key(monkeypatch):
    """The app refuses to start without SECRET_KEY, so the tests use a fixed one."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
