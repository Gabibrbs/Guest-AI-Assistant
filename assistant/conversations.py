"""One conversation per guest, saved as a small JSON file.

Each browser gets a random guest id (kept in the Flask session cookie). The guest's
questions and answers are saved in <folder>/<guest id>.json. Files on disk work even
when the server runs the app in several processes at once (PythonAnywhere uses 3),
because every process reads the same folder. Python memory would not: each process
has its own.
"""

import json
import os
import re
import tempfile
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from .prompt import Answer

MAX_TURNS = 20                     # only the last 20 questions (with their answers) are kept
MAX_AGE_SECONDS = 24 * 60 * 60     # conversations untouched for 24 hours are deleted

# The exact format new_guest_id() creates: 32 lowercase hexadecimal characters.
GUEST_ID_PATTERN = re.compile(r"[0-9a-f]{32}")


def new_guest_id():
    """A random id that nobody can guess, for example '3f2a9c...' (32 characters)."""
    return uuid.uuid4().hex


def is_valid_guest_id(guest_id):
    """True only for ids in the exact format the app creates.

    This check stops an id like '../../app' from pointing at a file outside the folder.
    """
    return isinstance(guest_id, str) and GUEST_ID_PATTERN.fullmatch(guest_id) is not None


def conversation_path(folder, guest_id):
    if not is_valid_guest_id(guest_id):
        raise ValueError("Invalid guest id.")
    return Path(folder) / f"{guest_id}.json"


def load_history(folder, guest_id):
    """The guest's conversation: a list of {"question": str, "answer": Answer}.

    A missing or damaged file just means an empty conversation.
    """
    path = conversation_path(folder, guest_id)
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return [{"question": turn["question"], "answer": Answer(**turn["answer"])} for turn in saved]


def add_turn(folder, guest_id, question, answer):
    """Add a question and its answer, keeping only the last MAX_TURNS."""
    history = load_history(folder, guest_id)
    history.append({"question": question, "answer": answer})
    history = history[-MAX_TURNS:]

    saved = [{"question": turn["question"], "answer": asdict(turn["answer"])} for turn in history]
    write_atomically(conversation_path(folder, guest_id), json.dumps(saved, ensure_ascii=False).encode("utf-8"))


def write_atomically(path, data):
    """Write the whole file (bytes) or nothing. Also used for the host's documents.

    The data goes first to a temporary file in the same folder, and os.replace then swaps
    it in one step. If the server stops halfway, the old file is still complete.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as file:
            file.write(data)
        os.replace(temporary, path)
    except BaseException:
        os.remove(temporary)
        raise


def clear_history(folder, guest_id):
    """Delete the guest's conversation ("Start over")."""
    conversation_path(folder, guest_id).unlink(missing_ok=True)


def delete_old_conversations(folder, max_age_seconds=MAX_AGE_SECONDS, now=None):
    """Delete conversations not changed for max_age_seconds. Returns how many were deleted."""
    folder = Path(folder)
    if not folder.is_dir():
        return 0
    now = time.time() if now is None else now
    deleted = 0
    for path in folder.iterdir():  # also catches a .tmp file left by a crash
        if path.is_file() and now - path.stat().st_mtime > max_age_seconds:
            path.unlink(missing_ok=True)  # another process may have deleted it first
            deleted += 1
    return deleted
