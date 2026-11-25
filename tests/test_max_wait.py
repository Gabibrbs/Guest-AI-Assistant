"""The longest a guest waits for an answer (GEMINI_MAX_WAIT_SECONDS).

A fake clock measures the time: waits between attempts and slow answers move it forward,
so the tests check the real timing rules without waiting.
"""

import pytest
from conftest import GUEST
from helpers import FakeClock, FakeClockSleep, FakeGeminiClient, Slow, api_error

from app import create_app
from assistant.gemini_client import (
    DEFAULT_MAX_WAIT_SECONDS,
    FALLBACK_RESERVE_SECONDS,
    GeminiError,
    TIMEOUT_SECONDS,
    ask_gemini,
    ask_with_fallback,
)


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def sleep(clock):
    return FakeClockSleep(clock)


def timeouts(client):
    """The time limit (in seconds) given to each request."""
    return [call["config"].http_options.timeout / 1000 for call in client.models.calls]


def test_default_limit_is_40_seconds():
    assert DEFAULT_MAX_WAIT_SECONDS == 40


def test_without_a_limit_each_request_may_take_60_seconds(clock, sleep):
    client = FakeGeminiClient("Answer")

    ask_gemini(client, "main", "prompt", sleep=sleep, clock=clock)

    assert timeouts(client) == [TIMEOUT_SECONDS]


def test_quick_answer_is_not_affected(clock, sleep):
    client = FakeGeminiClient(Slow(clock, 3, "Answer"))

    text = ask_with_fallback(client, "main", "fallback", "prompt", sleep=sleep, max_wait_seconds=40, clock=clock)

    assert text == "Answer"
    assert timeouts(client) == [40 - FALLBACK_RESERVE_SECONDS]  # the main model gets 25 s


def test_slow_main_model_hands_over_to_the_fallback_in_time(clock, sleep):
    client = FakeGeminiClient(Slow(clock, 63, "too late"), Slow(clock, 4, "Answer from fallback"))
    start = clock.now

    text = ask_with_fallback(client, "main", "fallback", "prompt", sleep=sleep, max_wait_seconds=40, clock=clock)

    assert text == "Answer from fallback"
    assert [call["model"] for call in client.models.calls] == ["main", "fallback"]
    assert timeouts(client) == [25, 15]   # the main model stopped at 25 s; the fallback had the last 15 s
    assert clock.now - start == 29


def test_guest_never_waits_more_than_the_limit(clock, sleep):
    """The worst case: everything is slow. Without the limit this took 255 s."""
    client = FakeGeminiClient(Slow(clock, 63, "late"), Slow(clock, 63, "late"),
                              Slow(clock, 63, "late"), Slow(clock, 63, "late"))
    start = clock.now

    with pytest.raises(GeminiError, match="busy right now"):
        ask_with_fallback(client, "main", "fallback", "prompt", sleep=sleep, max_wait_seconds=40, clock=clock)

    assert clock.now - start <= 40
    assert len(client.models.calls) == 2  # no time left for new attempts after the slow main request


def test_retries_stop_when_there_is_no_time_left_for_them(clock, sleep):
    client = FakeGeminiClient(Slow(clock, 6, api_error(503)), Slow(clock, 6, api_error(503)),
                              Slow(clock, 2, "Answer from fallback"))
    start = clock.now

    text = ask_with_fallback(client, "main", "fallback", "prompt", sleep=sleep, max_wait_seconds=40, clock=clock)

    # Main: 6 s, wait 5 s, 6 s -> 17 s used of its 25 s; a 10 s wait would leave less than 5 s, so it stops
    assert text == "Answer from fallback"
    assert [call["model"] for call in client.models.calls] == ["main", "main", "fallback"]
    assert sleep.waits == [5]
    assert timeouts(client) == [25, 14, 23]  # 25 - (6 + 5) = 14; the fallback gets all the time left
    assert clock.now - start == 19


def test_busy_errors_that_come_back_fast_still_use_all_three_attempts(clock, sleep):
    client = FakeGeminiClient(api_error(503), api_error(503), "Answer")

    text = ask_with_fallback(client, "main", "fallback", "prompt", sleep=sleep, max_wait_seconds=40, clock=clock)

    assert text == "Answer"
    assert sleep.waits == [5, 10]  # 15 s of waiting fits in the main model's 25 s


def test_without_fallback_the_main_model_gets_the_whole_time(clock, sleep):
    client = FakeGeminiClient(Slow(clock, 3, "Answer"))

    ask_with_fallback(client, "main", None, "prompt", sleep=sleep, max_wait_seconds=40, clock=clock)

    assert timeouts(client) == [40]


def test_no_request_starts_with_too_little_time(clock, sleep):
    client = FakeGeminiClient("never sent")

    with pytest.raises(GeminiError, match="busy") as raised:
        ask_gemini(client, "main", "prompt", sleep=sleep, deadline=clock.now + 4, clock=clock)

    assert raised.value.temporary is True
    assert client.models.calls == []


# ---------- On the guest page ----------

def test_guest_sees_the_busy_message_when_time_runs_out(data_folder, monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr("assistant.gemini_client.time.monotonic", clock)
    monkeypatch.setattr("assistant.gemini_client.time.sleep", FakeClockSleep(clock))
    fake = FakeGeminiClient(Slow(clock, 63, "late"), Slow(clock, 63, "late"))
    app = create_app(client=fake, data_folder=data_folder)
    start = clock.now

    html = app.test_client().post(f"{GUEST}/ask", data={"question": "Wi-Fi?"},
                                  follow_redirects=True).get_data(as_text=True)

    assert "The assistant is busy right now." in html
    assert clock.now - start <= DEFAULT_MAX_WAIT_SECONDS


def test_limit_from_the_env_file(data_folder, monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr("assistant.gemini_client.time.monotonic", clock)
    monkeypatch.setenv("GEMINI_MAX_WAIT_SECONDS", "30")
    fake = FakeGeminiClient(Slow(clock, 2, "Answer.\nSOURCE: the-house.md"))
    app = create_app(client=fake, data_folder=data_folder)

    app.test_client().post(f"{GUEST}/ask", data={"question": "Wi-Fi?"})

    assert timeouts(fake) == [30 - FALLBACK_RESERVE_SECONDS]


@pytest.mark.parametrize("value", ["0", "19", "ten", "-5"])
def test_too_small_or_invalid_limit_stops_the_app(data_folder, monkeypatch, value):
    monkeypatch.setenv("GEMINI_MAX_WAIT_SECONDS", value)

    with pytest.raises(RuntimeError, match="GEMINI_MAX_WAIT_SECONDS must be a whole number of at least 20"):
        create_app(client=FakeGeminiClient(), data_folder=data_folder)
