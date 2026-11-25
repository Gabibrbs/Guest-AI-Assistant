"""Flask web pages.

Guests:  /p/<slug>         one property's house guide, the guest's conversation, the question box
Host:    /host             password page; once logged in, the list of properties
         /host/p/<slug>    upload, replace or delete one property's documents

Everything that belongs to the client (config.toml, documents, logos, conversations,
counters) lives in the data folder, which is never added to Git. See exemplo/.

Run with:  python app.py   then open http://127.0.0.1:5000
"""

import io
import os
import time
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, send_file, session, url_for
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from assistant import conversations, limits
from assistant.answer import answer_question
from assistant.conversations import write_atomically
from assistant.documents import SUPPORTED_EXTENSIONS, DocumentError, load_folder, read_document
from assistant.gemini_client import (
    DEFAULT_MAX_WAIT_SECONDS,
    FALLBACK_RESERVE_SECONDS,
    MIN_REQUEST_SECONDS,
    GeminiError,
    create_client,
    get_fallback_model_name,
    get_model_name,
)
from assistant.privacy import privacy_notice
from assistant.properties import color_shades, load_properties
from assistant.qr import PublicAddressError, check_public_base_url, guest_link, make_qr_png

PROJECT_FOLDER = Path(__file__).parent
EXAMPLE_FOLDER = PROJECT_FOLDER / "exemplo"   # the demo (in Git)
DEFAULT_DATA_FOLDER = "dados"                 # the client's data (never in Git); DATA_FOLDER in .env changes it

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


def positive_number_setting(name, default, minimum=1):
    """A whole number (at least `minimum`) from .env, or `default` when it is not set."""
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    if not value.isdigit() or int(value) < minimum:
        raise RuntimeError(f"{name} must be a whole number of at least {minimum}, not {value!r}.")
    return int(value)


def data_folder_setting():
    """The data folder from DATA_FOLDER in .env (default "dados"), next to app.py if relative."""
    return PROJECT_FOLDER / os.environ.get("DATA_FOLDER", DEFAULT_DATA_FOLDER)


def create_app(client=None, data_folder=None, production=False):
    """Create the Flask app.

    `client` is the Gemini client. The tests pass a fake one; when it is None the real
    client is created on the first question (so the page opens even without an API key).
    `data_folder` holds config.toml and everything of this client; the tests pass a
    temporary one.
    `production` is True only in wsgi.py (the online server): see below.
    """
    app = Flask(__name__)
    # Debug mode shows error details and a console in the browser: never online.
    app.config["DEBUG"] = False
    # Online, the session cookie is only sent over HTTPS, so nobody on the same Wi-Fi can
    # read it. Not on this computer: http://127.0.0.1 has no HTTPS and the cookie would be lost.
    app.config["SESSION_COOKIE_SECURE"] = production
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
    # The longest a guest waits for an answer. It must leave the main model some time
    # after the part kept for the fallback model.
    max_wait_seconds = positive_number_setting("GEMINI_MAX_WAIT_SECONDS", DEFAULT_MAX_WAIT_SECONDS,
                                               minimum=FALLBACK_RESERVE_SECONDS + MIN_REQUEST_SECONDS)

    data_folder = Path(data_folder) if data_folder else data_folder_setting()
    properties = load_properties(data_folder)  # {slug: Property}; stops here if config.toml has a mistake
    conversations_folder = data_folder / "conversas"
    limits_file = data_folder / "limites.sqlite3"
    state = {"client": client}

    def get_client():
        if state["client"] is None:
            state["client"] = create_client()
        return state["client"]

    def get_property(slug):
        """The property for this link, or a 404 page. Guests only ever see this one property."""
        if slug not in properties:
            abort(404)
        return properties[slug]

    def get_documents(prop):
        """The property's house guide, read from disk on every request.

        The server runs several processes; reading the folder each time means all of them
        see a document the host has just uploaded or deleted. The files are few and small.
        """
        return load_folder(prop.documents_folder)

    def guest_conversations(prop):
        return conversations_folder / prop.slug  # each property keeps its own conversations

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
                return redirect(url_for("host_home"))
            return view(*args, **kwargs)
        return wrapper

    def public_base_url():
        """PUBLIC_BASE_URL from .env, checked. Raises PublicAddressError if it is missing or wrong."""
        return check_public_base_url(os.environ.get("PUBLIC_BASE_URL"))

    def guest_url(prop):
        """The full guest link shown to the host: the public address if it is set,
        otherwise the address this page was opened with."""
        try:
            return guest_link(public_base_url(), prop.slug)
        except PublicAddressError:
            return url_for("guest_page", slug=prop.slug, _external=True)

    @app.context_processor
    def page_settings():
        """Values every template can use."""
        return {"color_shades": color_shades, "guest_url": guest_url}

    # ---------- Guest pages ----------

    @app.get("/")
    def home():
        # With one property, the address alone is enough. With several, guests must use
        # their own link: the page does not list the others.
        if len(properties) == 1:
            return redirect(url_for("guest_page", slug=next(iter(properties))))
        return render_template("use_your_link.html")

    @app.get("/p/<slug>")
    def guest_page(slug):
        prop = get_property(slug)
        for each in properties.values():  # conversations older than 24 hours are deleted
            conversations.delete_old_conversations(guest_conversations(each))
        return render_template(
            "index.html",
            prop=prop,
            documents=list(get_documents(prop)),
            history=conversations.load_history(guest_conversations(prop), get_guest_id()),
            example_questions=EXAMPLE_QUESTIONS,
            privacy=privacy_notice(prop, request.accept_languages),
        )

    @app.get("/p/<slug>/privacy")
    def privacy(slug):
        prop = get_property(slug)
        notice = privacy_notice(prop, request.accept_languages)
        return render_template("privacy.html", prop=prop, privacy=notice, page_language=notice["language"])

    @app.get("/p/<slug>/logo")
    def logo(slug):
        prop = get_property(slug)
        if prop.logo is None:
            abort(404)
        return send_file(prop.logo)

    @app.post("/p/<slug>/ask")
    def ask(slug):
        prop = get_property(slug)
        question = request.form.get("question", "").strip()
        if not question:
            flash("Please type a question.", "error")
            return redirect(url_for("guest_page", slug=slug, _anchor="ask"))

        # Limits first, before the paid API call. The guest's own limit is checked first,
        # so a guest who is over it does not use up the daily total for everyone else.
        guest_id = get_guest_id()
        if not limits.try_use(limits_file, f"guest:{guest_id}", guest_questions_per_hour, limits.HOUR):
            app.logger.warning("A guest reached the hourly question limit.")  # never the question text
            flash(limits.limit_message("guest", request.accept_languages), "error")
            return redirect(url_for("guest_page", slug=slug, _anchor="ask"))
        if not limits.try_use(limits_file, "all-questions", questions_per_day, limits.DAY):
            app.logger.warning("The daily question limit was reached.")
            flash(limits.limit_message("day", request.accept_languages), "error")
            return redirect(url_for("guest_page", slug=slug, _anchor="ask"))

        try:
            answer = answer_question(get_client(), get_model_name(), get_documents(prop), question,
                                     business_name=prop.name, not_found_message=prop.not_found_message,
                                     fallback_model=get_fallback_model_name(),
                                     max_wait_seconds=max_wait_seconds)
        except GeminiError as error:
            flash(str(error), "error")
            return redirect(url_for("guest_page", slug=slug, _anchor="ask"))

        conversations.add_turn(guest_conversations(prop), guest_id, question, answer)
        # The #latest anchor scrolls the page down to the new answer
        return redirect(url_for("guest_page", slug=slug, _anchor="latest"))

    @app.post("/p/<slug>/reset")
    def reset(slug):
        prop = get_property(slug)
        conversations.clear_history(guest_conversations(prop), get_guest_id())
        flash("Your conversation was cleared.", "success")
        return redirect(url_for("guest_page", slug=slug))

    # ---------- Host pages ----------

    @app.route("/host", methods=["GET", "POST"])
    def host_home():
        """The login form, or the list of properties once the host is logged in."""
        if is_logged_in_host():
            return render_template(
                "host_home.html",
                properties=[(prop, len(get_documents(prop))) for prop in properties.values()],
            )
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
                return redirect(url_for("host_home"))
            else:
                limits.record(limits_file, f"login:{address}", LOGIN_ADDRESS_PERIOD)
                limits.record(limits_file, "login:all", limits.HOUR)
                flash("Wrong password.", "error")
        return render_template("host_login.html")

    @app.post("/host/logout")
    def host_logout():
        log_out_host()
        flash("You are logged out.", "success")
        return redirect(url_for("host_home"))

    @app.get("/host/p/<slug>")
    @host_required
    def host_property(slug):
        prop = get_property(slug)
        return render_template(
            "host_property.html",
            prop=prop,
            documents=list(get_documents(prop)),
            max_upload_mb=MAX_UPLOAD_MB,
            extensions=", ".join(SUPPORTED_EXTENSIONS),
        )

    @app.get("/host/p/<slug>/qr-code.png")
    @host_required
    def host_qr_code(slug):
        """Download the printable QR code that opens this property's guest page."""
        prop = get_property(slug)
        try:
            link = guest_link(public_base_url(), prop.slug)
        except PublicAddressError as error:
            # Without the real public address, the QR code would open the wrong page
            flash(str(error), "error")
            return redirect(url_for("host_property", slug=slug))
        return send_file(io.BytesIO(make_qr_png(link, prop.name)), mimetype="image/png",
                         as_attachment=True, download_name=f"qr-code-{prop.slug}.png")

    @app.post("/host/p/<slug>/upload")
    @host_required
    def host_upload(slug):
        prop = get_property(slug)
        file = request.files.get("document")
        if file is None or file.filename == "":
            flash("Choose a file to upload.", "error")
            return redirect(url_for("host_property", slug=slug))

        name = clean_filename(file.filename)
        data = file.read()
        try:
            text = read_document(name, data)  # checked before saving: a bad file never reaches the guide
        except DocumentError as error:
            flash(str(error), "error")
            return redirect(url_for("host_property", slug=slug))

        if len(text) > MAX_DOCUMENT_CHARACTERS:
            flash(f"{name}: the document is too long. Split it into smaller documents.", "error")
            return redirect(url_for("host_property", slug=slug))

        path = prop.documents_folder / name
        replaced = path.exists()
        write_atomically(path, data)  # a file with the same name replaces the old one
        flash(f"{name} was {'replaced' if replaced else 'added'}. Guests' answers now use it.", "success")
        return redirect(url_for("host_property", slug=slug))

    @app.post("/host/p/<slug>/delete")
    @host_required
    def host_delete(slug):
        prop = get_property(slug)
        name = request.form.get("name", "")
        # Only a name from this property's list can be deleted, never a path like "../app.py".
        if name not in get_documents(prop):
            flash("That document does not exist.", "error")
            return redirect(url_for("host_property", slug=slug))

        (prop.documents_folder / name).unlink(missing_ok=True)
        flash(f"{name} was deleted.", "success")
        return redirect(url_for("host_property", slug=slug))

    # ---------- Errors ----------

    @app.errorhandler(413)
    def file_too_large(error):
        flash(f"The file is larger than {MAX_UPLOAD_MB} MB.", "error")
        slug = (request.view_args or {}).get("slug")
        if slug in properties:
            return redirect(url_for("host_property", slug=slug))
        return redirect(url_for("host_home"))

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template("not_found.html"), 404

    return app


if __name__ == "__main__":
    load_dotenv()
    create_app().run(host="127.0.0.1", port=5000)
