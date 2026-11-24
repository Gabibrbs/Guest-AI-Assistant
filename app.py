"""Flask web pages.

Guests:  /          the house guide, their conversation and the question box
Host:    /host      password page; once logged in, upload, replace or delete documents

Run with:  python app.py   then open http://127.0.0.1:5000
"""

import os
import time
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from assistant import conversations, limits
from assistant.answer import BUSINESS_NAME, answer_question
from assistant.conversations import write_atomically
from assistant.documents import SUPPORTED_EXTENSIONS, DocumentError, load_folder, read_document
from assistant.gemini_client import GeminiError, create_client, get_model_name

DOCUMENTS_FOLDER = Path(__file__).parent / "documentos"   # the house guide, managed by the host
CONVERSATIONS_FOLDER = Path(__file__).parent / "conversas"  # one JSON file per guest
LIMITS_FILE = Path(__file__).parent / "dados" / "limites.sqlite3"  # request counters
MAX_UPLOAD_MB = 5
MAX_DOCUMENT_CHARACTERS = 50_000  # all documents go into every prompt, so each one must stay short

# Limits for questions: the defaults, changed in .env (GUEST_QUESTIONS_PER_HOUR, QUESTIONS_PER_DAY)
DEFAULT_GUEST_QUESTIONS_PER_HOUR = 20
DEFAULT_QUESTIONS_PER_DAY = 200

# Failed host logins: a guesser is stopped long before finding the password
LOGIN_FAILURES_PER_ADDRESS = 5     # per IP address, every 15 minutes
LOGIN_FAILURES_TOTAL = 20          # from everyone together, every hour
LOGIN_ADDRESS_PERIOD = 15 * 60

HOST_SESSION_SECONDS = 8 * 60 * 60  # the host is logged out after 8 hours

EXAMPLE_QUESTIONS = [
    "What is the Wi-Fi password?",
    "A que horas é o check-out?",
    "¿Tienen cuna para bebé?",
]


def clean_filename(filename):
    """Make an uploaded file name safe to show and to put in the prompt.

    secure_filename removes folders, spaces, quotes and non-Latin letters. The extension
    is kept apart so that a name like "指南.txt" becomes "document.txt" and not "txt".
    """
    path = Path(filename)
    name = secure_filename(path.stem) or "document"
    return name + path.suffix.lower()


def required_setting(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is missing. Add it to the .env file (see .env.example).")
    return value


def positive_number_setting(name, default):
    """A whole number above zero from .env, or `default` when it is not set."""
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    if not value.isdigit() or int(value) < 1:
        raise RuntimeError(f"{name} must be a whole number above 0, not {value!r}.")
    return int(value)


def create_app(client=None, documents_folder=DOCUMENTS_FOLDER, conversations_folder=CONVERSATIONS_FOLDER,
               limits_file=LIMITS_FILE):
    """Create the Flask app.

    `client` is the Gemini client. The tests pass a fake one; when it is None the real
    client is created on the first question (so the page opens even without an API key).
    """
    app = Flask(__name__)
    # A fixed key: every server process must sign the session cookie the same way.
    app.config["SECRET_KEY"] = required_setting("SECRET_KEY")
    # Only the hash of the host password is stored (create it with set_host_password.py).
    host_password_hash = required_setting("HOST_PASSWORD_HASH")
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
    # The browser does not send the cookie with forms posted from other websites,
    # so another site cannot make a logged-in host delete documents.
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # The session cookie has no expiry date, so the browser deletes it when it closes
    # (Flask's default, written here so it is clear). The host's 8 hours are checked below.
    app.config["SESSION_PERMANENT"] = False

    guest_questions_per_hour = positive_number_setting("GUEST_QUESTIONS_PER_HOUR", DEFAULT_GUEST_QUESTIONS_PER_HOUR)
    questions_per_day = positive_number_setting("QUESTIONS_PER_DAY", DEFAULT_QUESTIONS_PER_DAY)

    documents_folder = Path(documents_folder)
    state = {"client": client}

    def get_client():
        if state["client"] is None:
            state["client"] = create_client()
        return state["client"]

    def get_documents():
        """The house guide, read from disk on every request.

        The server runs several processes; reading the folder each time means all of them
        see a document the host has just uploaded or deleted. The files are few and small.
        """
        return load_folder(documents_folder)

    def get_guest_id():
        """This browser's guest id, kept in the signed session cookie. Created on first visit."""
        guest_id = session.get("guest_id")
        if not conversations.is_valid_guest_id(guest_id):
            guest_id = conversations.new_guest_id()
            session["guest_id"] = guest_id
        return guest_id

    def is_logged_in_host():
        """True if this browser logged in as the host less than 8 hours ago."""
        if not session.get("is_host"):
            return False
        if time.time() - session.get("host_since", 0) > HOST_SESSION_SECONDS:
            log_out_host()
            return False
        return True

    def log_out_host():
        session.pop("is_host", None)
        session.pop("host_since", None)

    def host_required(view):
        """Pages and actions only the logged-in host may use."""
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not is_logged_in_host():
                flash("Please log in as the host.", "error")
                return redirect(url_for("host_login"))
            return view(*args, **kwargs)
        return wrapper

    # ---------- Guest pages ----------

    @app.get("/")
    def index():
        conversations.delete_old_conversations(conversations_folder)
        return render_template(
            "index.html",
            business_name=BUSINESS_NAME,
            documents=list(get_documents()),
            history=conversations.load_history(conversations_folder, get_guest_id()),
            example_questions=EXAMPLE_QUESTIONS,
        )

    @app.post("/ask")
    def ask():
        question = request.form.get("question", "").strip()
        if not question:
            flash("Please type a question.", "error")
            return redirect(url_for("index"))

        # Limits first, before the paid API call. The guest's own limit is checked first,
        # so a guest who is over it does not use up the daily total for everyone else.
        guest_id = get_guest_id()
        if not limits.try_use(limits_file, f"guest:{guest_id}", guest_questions_per_hour, limits.HOUR):
            app.logger.warning("A guest reached the hourly question limit.")  # never the question text
            flash(limits.limit_message("guest", request.accept_languages), "error")
            return redirect(url_for("index"))
        if not limits.try_use(limits_file, "all-questions", questions_per_day, limits.DAY):
            app.logger.warning("The daily question limit was reached.")
            flash(limits.limit_message("day", request.accept_languages), "error")
            return redirect(url_for("index"))

        try:
            answer = answer_question(get_client(), get_model_name(), get_documents(), question)
        except GeminiError as error:
            flash(str(error), "error")
            return redirect(url_for("index"))

        conversations.add_turn(conversations_folder, guest_id, question, answer)
        # The #latest anchor scrolls the page down to the new answer
        return redirect(url_for("index", _anchor="latest"))

    @app.post("/reset")
    def reset():
        conversations.clear_history(conversations_folder, get_guest_id())
        flash("Your conversation was cleared.", "success")
        return redirect(url_for("index"))

    # ---------- Host pages ----------

    @app.route("/host", methods=["GET", "POST"])
    def host_login():
        if is_logged_in_host():
            return redirect(url_for("host_documents"))
        if request.method == "POST":
            address = request.remote_addr or "unknown"
            too_many = (
                limits.used(limits_file, f"login:{address}", LOGIN_ADDRESS_PERIOD) >= LOGIN_FAILURES_PER_ADDRESS
                or limits.used(limits_file, "login:all", limits.HOUR) >= LOGIN_FAILURES_TOTAL
            )
            if too_many:
                # The password is not even checked, so guessing stops here.
                app.logger.warning("Host login blocked after too many failed attempts.")
                flash("Too many failed attempts. Please wait 15 minutes and try again.", "error")
            elif check_password_hash(host_password_hash, request.form.get("password", "")):
                session["is_host"] = True
                session["host_since"] = time.time()
                return redirect(url_for("host_documents"))
            else:
                limits.record(limits_file, f"login:{address}", LOGIN_ADDRESS_PERIOD)
                limits.record(limits_file, "login:all", limits.HOUR)
                flash("Wrong password.", "error")
        return render_template("host_login.html", business_name=BUSINESS_NAME)

    @app.post("/host/logout")
    def host_logout():
        log_out_host()
        flash("You are logged out.", "success")
        return redirect(url_for("host_login"))

    @app.get("/host/documents")
    @host_required
    def host_documents():
        return render_template(
            "host.html",
            business_name=BUSINESS_NAME,
            documents=list(get_documents()),
            max_upload_mb=MAX_UPLOAD_MB,
            extensions=", ".join(SUPPORTED_EXTENSIONS),
        )

    @app.post("/host/upload")
    @host_required
    def host_upload():
        file = request.files.get("document")
        if file is None or file.filename == "":
            flash("Choose a file to upload.", "error")
            return redirect(url_for("host_documents"))

        name = clean_filename(file.filename)
        data = file.read()
        try:
            text = read_document(name, data)  # checked before saving: a bad file never reaches the guide
        except DocumentError as error:
            flash(str(error), "error")
            return redirect(url_for("host_documents"))

        if len(text) > MAX_DOCUMENT_CHARACTERS:
            flash(f"{name}: the document is too long. Split it into smaller documents.", "error")
            return redirect(url_for("host_documents"))

        path = documents_folder / name
        replaced = path.exists()
        write_atomically(path, data)  # a file with the same name replaces the old one
        flash(f"{name} was {'replaced' if replaced else 'added'}. Guests' answers now use it.", "success")
        return redirect(url_for("host_documents"))

    @app.post("/host/delete")
    @host_required
    def host_delete():
        name = request.form.get("name", "")
        # Only a name from the current list can be deleted, never a path like "../app.py".
        if name not in get_documents():
            flash("That document does not exist.", "error")
            return redirect(url_for("host_documents"))

        (documents_folder / name).unlink(missing_ok=True)
        flash(f"{name} was deleted.", "success")
        return redirect(url_for("host_documents"))

    @app.errorhandler(413)
    def file_too_large(error):
        flash(f"The file is larger than {MAX_UPLOAD_MB} MB.", "error")
        return redirect(url_for("host_documents"))

    return app


if __name__ == "__main__":
    load_dotenv()
    create_app().run(host="127.0.0.1", port=5000)
