"""Flask web page: document list, chat history, question box and upload button.

Run with:  python app.py   then open http://127.0.0.1:5000
"""

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from assistant.answer import BUSINESS_NAME, answer_question
from assistant.documents import DocumentError, load_folder, read_document
from assistant.gemini_client import GeminiError, create_client, get_model_name

DOCUMENTS_FOLDER = Path(__file__).parent / "documentos"
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


def create_app(client=None, documents_folder=DOCUMENTS_FOLDER):
    """Create the Flask app.

    `client` is the Gemini client. The tests pass a fake one; when it is None the real
    client is created on the first question (so the page opens even without an API key).
    """
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(16)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

    # The demo keeps everything in memory: one conversation, no database.
    sample_documents = load_folder(documents_folder)
    state = {
        "client": client,
        "documents": dict(sample_documents),  # {file name: text}
        "uploaded": [],                       # names of the documents uploaded on the page
        "history": [],                        # [{"question": ..., "answer": Answer}]
    }

    def get_client():
        if state["client"] is None:
            state["client"] = create_client()
        return state["client"]

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            business_name=BUSINESS_NAME,
            documents=list(state["documents"]),
            uploaded=state["uploaded"],
            history=state["history"],
            example_questions=EXAMPLE_QUESTIONS,
            max_upload_mb=MAX_UPLOAD_MB,
        )

    @app.post("/ask")
    def ask():
        question = request.form.get("question", "").strip()
        if not question:
            flash("Please type a question.", "error")
            return redirect(url_for("index"))

        try:
            answer = answer_question(get_client(), get_model_name(), state["documents"], question)
        except GeminiError as error:
            flash(str(error), "error")
            return redirect(url_for("index"))

        state["history"].append({"question": question, "answer": answer})
        # The #latest anchor scrolls the page down to the new answer
        return redirect(url_for("index", _anchor="latest"))

    @app.post("/upload")
    def upload():
        file = request.files.get("document")
        if file is None or file.filename == "":
            flash("Choose a file to upload.", "error")
            return redirect(url_for("index"))

        name = clean_filename(file.filename)
        try:
            text = read_document(name, file.read())
        except DocumentError as error:
            flash(str(error), "error")
            return redirect(url_for("index"))

        if len(text) > MAX_DOCUMENT_CHARACTERS:
            flash(f"{name}: the document is too long for this demo.", "error")
            return redirect(url_for("index"))

        state["documents"][name] = text  # a file with the same name replaces the old one
        if name not in state["uploaded"]:
            state["uploaded"].append(name)
        flash(f"{name} was added. The assistant now uses it to answer.", "success")
        return redirect(url_for("index"))

    @app.post("/reset")
    def reset():
        state["documents"] = dict(sample_documents)
        state["uploaded"] = []
        state["history"] = []
        flash("The conversation and uploaded documents were cleared.", "success")
        return redirect(url_for("index"))

    @app.errorhandler(413)
    def file_too_large(error):
        flash(f"The file is larger than {MAX_UPLOAD_MB} MB.", "error")
        return redirect(url_for("index"))

    return app


if __name__ == "__main__":
    load_dotenv()
    create_app().run(host="127.0.0.1", port=5000)
