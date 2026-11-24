"""Flask web pages.

Guests:  /          the house guide, their conversation and the question box
Host:    /host      password page; once logged in, upload, replace or delete documents

Run with:  python app.py   then open http://127.0.0.1:5000
"""

import os
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from assistant import conversations
from assistant.answer import BUSINESS_NAME, answer_question
from assistant.conversations import write_atomically
from assistant.documents import SUPPORTED_EXTENSIONS, DocumentError, load_folder, read_document
from assistant.gemini_client import GeminiError, create_client, get_model_name

DOCUMENTS_FOLDER = Path(__file__).parent / "documentos"   # the house guide, managed by the host
CONVERSATIONS_FOLDER = Path(__file__).parent / "conversas"  # one JSON file per guest
MAX_UPLOAD_MB = 5
MAX_DOCUMENT_CHARACTERS = 50_000  # all documents go into every prompt, so each one must stay short

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


def create_app(client=None, documents_folder=DOCUMENTS_FOLDER, conversations_folder=CONVERSATIONS_FOLDER):
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

    def host_required(view):
        """Pages and actions only the logged-in host may use."""
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not session.get("is_host"):
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

        try:
            answer = answer_question(get_client(), get_model_name(), get_documents(), question)
        except GeminiError as error:
            flash(str(error), "error")
            return redirect(url_for("index"))

        conversations.add_turn(conversations_folder, get_guest_id(), question, answer)
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
        if session.get("is_host"):
            return redirect(url_for("host_documents"))
        if request.method == "POST":
            password = request.form.get("password", "")
            if check_password_hash(host_password_hash, password):
                session["is_host"] = True
                return redirect(url_for("host_documents"))
            flash("Wrong password.", "error")
        return render_template("host_login.html", business_name=BUSINESS_NAME)

    @app.post("/host/logout")
    def host_logout():
        session.pop("is_host", None)
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
