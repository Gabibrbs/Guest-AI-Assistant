"""Request limits, so a mistake or an abuser cannot run up a big bill on the client's API key.

Counters are kept in a small SQLite file (sqlite3 comes with Python). A plain file is
not enough here: PythonAnywhere runs the app in several processes, and two of them could
read and write a counter at the same moment and lose a count. SQLite locks the file
while one process counts, so the others wait their turn.

Each counter belongs to a time window: for example "guest 3f2a… in the hour 14:00-15:00".
When the window ends the counter starts again from zero, and old rows are deleted.
"""

import sqlite3
import time
from contextlib import closing
from pathlib import Path

HOUR = 60 * 60
DAY = 24 * HOUR

# Shown to guests when a limit is reached, in the language their browser asks for.
LIMIT_MESSAGES = {
    "guest": {
        "en": "You have asked a lot of questions in the last hour. Please wait a little and try again. For anything urgent, contact your host.",
        "pt": "Fez muitas perguntas na última hora. Aguarde um pouco e tente novamente. Se for urgente, contacte o anfitrião.",
        "es": "Has hecho muchas preguntas en la última hora. Espera un poco y vuelve a intentarlo. Si es urgente, contacta con tu anfitrión.",
        "fr": "Vous avez posé beaucoup de questions au cours de la dernière heure. Merci de patienter un peu avant de réessayer. En cas d'urgence, contactez votre hôte.",
        "de": "Sie haben in der letzten Stunde viele Fragen gestellt. Bitte warten Sie kurz und versuchen Sie es erneut. In dringenden Fällen wenden Sie sich an Ihren Gastgeber.",
        "it": "Hai fatto molte domande nell'ultima ora. Attendi un po' e riprova. Per urgenze, contatta il tuo host.",
    },
    "day": {
        "en": "The assistant has reached its limit of questions for today. Please try again tomorrow, or contact your host.",
        "pt": "O assistente atingiu o limite de perguntas por hoje. Tente novamente amanhã ou contacte o anfitrião.",
        "es": "El asistente ha alcanzado su límite de preguntas por hoy. Inténtalo de nuevo mañana o contacta con tu anfitrión.",
        "fr": "L'assistant a atteint sa limite de questions pour aujourd'hui. Réessayez demain ou contactez votre hôte.",
        "de": "Der Assistent hat sein Fragenlimit für heute erreicht. Bitte versuchen Sie es morgen erneut oder wenden Sie sich an Ihren Gastgeber.",
        "it": "L'assistente ha raggiunto il limite di domande per oggi. Riprova domani o contatta il tuo host.",
    },
}
LANGUAGES = list(LIMIT_MESSAGES["guest"])


def limit_message(kind, accept_languages):
    """The message for `kind` ("guest" or "day") in the browser's language, or English.

    `accept_languages` is Flask's request.accept_languages (the browser's language list).
    """
    language = accept_languages.best_match(LANGUAGES, default="en")
    return LIMIT_MESSAGES[kind][language]


def window(name, period_seconds, now):
    """The counter's key for the current window and the moment that window ends.

    Example: name "day", period DAY -> one key per calendar day (UTC).
    """
    number = int(now // period_seconds)
    return f"{name}|{period_seconds}|{number}", (number + 1) * period_seconds


def connect(db_path):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # isolation_level=None: no automatic transactions, we start them ourselves with BEGIN.
    # timeout: wait up to 10 s if another process is counting at the same moment.
    db = sqlite3.connect(db_path, timeout=10, isolation_level=None)
    db.execute(
        "CREATE TABLE IF NOT EXISTS counters ("
        " key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires_at REAL NOT NULL)"
    )
    return db


def used(db_path, name, period_seconds, now=None):
    """How many times `name` was counted in the current window."""
    now = time.time() if now is None else now
    key, _ = window(name, period_seconds, now)
    with closing(connect(db_path)) as db:
        row = db.execute(
            "SELECT count FROM counters WHERE key = ? AND expires_at > ?", (key, now)
        ).fetchone()
    return row[0] if row else 0


def try_use(db_path, name, limit, period_seconds, now=None):
    """Count one use of `name` if it is still under `limit`. Returns True if it was allowed.

    Checking and counting happen in one locked step (BEGIN IMMEDIATE), so two processes
    can never both take the last free place.
    """
    now = time.time() if now is None else now
    key, expires_at = window(name, period_seconds, now)
    with closing(connect(db_path)) as db:
        db.execute("BEGIN IMMEDIATE")  # lock the file for writing until COMMIT
        try:
            db.execute("DELETE FROM counters WHERE expires_at <= ?", (now,))  # tidy up old windows
            row = db.execute("SELECT count FROM counters WHERE key = ?", (key,)).fetchone()
            if row and row[0] >= limit:
                db.execute("COMMIT")
                return False
            db.execute(
                "INSERT INTO counters (key, count, expires_at) VALUES (?, 1, ?)"
                " ON CONFLICT(key) DO UPDATE SET count = count + 1",
                (key, expires_at),
            )
            db.execute("COMMIT")
            return True
        except BaseException:
            db.execute("ROLLBACK")
            raise


def record(db_path, name, period_seconds, now=None):
    """Count one event with no limit (used for failed logins)."""
    try_use(db_path, name, float("inf"), period_seconds, now)
