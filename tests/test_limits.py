"""Request counters kept in SQLite (assistant/limits.py)."""

import threading

import pytest
from werkzeug.datastructures import LanguageAccept
from werkzeug.http import parse_accept_header

from assistant.limits import DAY, HOUR, LIMIT_MESSAGES, limit_message, record, try_use, used

NOON = 1_800_000_000.0  # a fixed moment, so the tests never depend on the real clock


@pytest.fixture
def db(tmp_path):
    return tmp_path / "dados" / "limites.sqlite3"


def test_uses_are_allowed_until_the_limit(db):
    results = [try_use(db, "guest:a", 3, HOUR, now=NOON) for _ in range(5)]

    assert results == [True, True, True, False, False]
    assert used(db, "guest:a", HOUR, now=NOON) == 3  # refused uses are not counted


def test_each_name_has_its_own_counter(db):
    for _ in range(3):
        try_use(db, "guest:a", 3, HOUR, now=NOON)

    assert try_use(db, "guest:b", 3, HOUR, now=NOON) is True
    assert try_use(db, "guest:a", 3, HOUR, now=NOON) is False


def test_counter_starts_again_in_the_next_window(db):
    start_of_hour = (NOON // HOUR) * HOUR
    for _ in range(3):
        try_use(db, "guest:a", 3, HOUR, now=start_of_hour + 10)

    assert try_use(db, "guest:a", 3, HOUR, now=start_of_hour + HOUR - 1) is False  # same hour
    assert try_use(db, "guest:a", 3, HOUR, now=start_of_hour + HOUR) is True       # next hour


def test_daily_counter_starts_again_the_next_day(db):
    start_of_day = (NOON // DAY) * DAY
    try_use(db, "all-questions", 1, DAY, now=start_of_day + 5)

    assert try_use(db, "all-questions", 1, DAY, now=start_of_day + DAY - 5) is False
    assert try_use(db, "all-questions", 1, DAY, now=start_of_day + DAY + 5) is True


def test_old_windows_are_deleted(db):
    try_use(db, "guest:old", 10, HOUR, now=NOON)

    try_use(db, "guest:new", 10, HOUR, now=NOON + 2 * HOUR)  # every new count tidies up

    assert used(db, "guest:old", HOUR, now=NOON) == 0


def test_record_counts_without_a_limit(db):
    for _ in range(7):
        record(db, "login:all", HOUR, now=NOON)

    assert used(db, "login:all", HOUR, now=NOON) == 7


def test_unused_name_counts_zero_and_creates_the_folder(db):
    assert used(db, "never-used", HOUR, now=NOON) == 0
    assert db.exists()


def test_counting_from_many_threads_at_once_never_goes_over_the_limit(db):
    """Like several server processes counting at the same moment: exactly `limit` are allowed."""
    allowed = []

    def ask():
        for _ in range(10):
            if try_use(db, "all-questions", 25, DAY, now=NOON):
                allowed.append(1)

    threads = [threading.Thread(target=ask) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(allowed) == 25
    assert used(db, "all-questions", DAY, now=NOON) == 25


# ---------- Messages ----------

def accept(header):
    return parse_accept_header(header, LanguageAccept)


@pytest.mark.parametrize("header, language", [
    ("pt-PT,pt;q=0.9,en;q=0.8", "pt"),
    ("es-ES,es;q=0.9", "es"),
    ("fr-FR", "fr"),
    ("de-DE,de;q=0.9,en;q=0.5", "de"),
    ("it", "it"),
    ("ja-JP,ja;q=0.9", "en"),   # a language with no message: English
    ("", "en"),                 # no header at all: English
])
@pytest.mark.parametrize("kind", ["guest", "day"])
def test_message_in_the_browser_language_or_english(kind, header, language):
    assert limit_message(kind, accept(header)) == LIMIT_MESSAGES[kind][language]


def test_every_message_exists_in_every_language():
    assert set(LIMIT_MESSAGES["guest"]) == set(LIMIT_MESSAGES["day"])
