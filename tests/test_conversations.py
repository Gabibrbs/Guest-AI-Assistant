"""Saving each guest's conversation in its own JSON file."""

import os

import pytest

from assistant import conversations
from assistant.conversations import (
    MAX_TURNS,
    add_turn,
    clear_history,
    delete_old_conversations,
    is_valid_guest_id,
    load_history,
    new_guest_id,
)
from assistant.prompt import Answer


def answer(text="An answer."):
    return Answer(text=text, sources=["the-house.md"], found=True)


# ---------- Guest ids ----------

def test_new_guest_ids_are_valid_and_different():
    first, second = new_guest_id(), new_guest_id()

    assert is_valid_guest_id(first) and is_valid_guest_id(second)
    assert first != second


@pytest.mark.parametrize("guest_id", [
    "../app",
    "..\\..\\.env",
    "/etc/passwd",
    "C:\\Windows\\win.ini",
    "a" * 31,                    # one character short
    "a" * 33,                    # one character too many
    "A" * 32,                    # upper case is not what the app creates
    "g" * 32,                    # not hexadecimal
    "0123456789abcdef0123456789abcde\n",
    "",
    None,
    12345,
])
def test_invalid_guest_ids_are_refused(tmp_path, guest_id):
    assert not is_valid_guest_id(guest_id)
    with pytest.raises(ValueError):
        load_history(tmp_path, guest_id)
    with pytest.raises(ValueError):
        add_turn(tmp_path, guest_id, "Question?", answer())
    with pytest.raises(ValueError):
        clear_history(tmp_path, guest_id)


def test_invalid_guest_id_never_reads_a_file_outside_the_folder(tmp_path):
    folder = tmp_path / "conversas"
    folder.mkdir()
    (tmp_path / "secret.json").write_text('[{"question": "leak", "answer": {"text": "x"}}]', encoding="utf-8")

    with pytest.raises(ValueError):
        load_history(folder, "../secret")


# ---------- Saving and loading ----------

def test_new_guest_has_an_empty_conversation(tmp_path):
    assert load_history(tmp_path, new_guest_id()) == []


def test_turns_are_saved_and_loaded_in_order(tmp_path):
    guest = new_guest_id()

    add_turn(tmp_path, guest, "A que horas é o check-out?", answer("Às 11:00."))
    add_turn(tmp_path, guest, "Do you have a cot?", Answer(text="Not in the guide.", found=False))

    history = load_history(tmp_path, guest)
    assert [turn["question"] for turn in history] == ["A que horas é o check-out?", "Do you have a cot?"]
    assert history[0]["answer"] == Answer(text="Às 11:00.", sources=["the-house.md"], found=True)
    assert history[1]["answer"].found is False


def test_two_guests_do_not_share_a_conversation(tmp_path):
    anna, bruno = new_guest_id(), new_guest_id()

    add_turn(tmp_path, anna, "Anna's question?", answer())

    assert len(load_history(tmp_path, anna)) == 1
    assert load_history(tmp_path, bruno) == []


def test_only_the_last_turns_are_kept(tmp_path):
    guest = new_guest_id()

    for number in range(1, MAX_TURNS + 6):
        add_turn(tmp_path, guest, f"Question {number}?", answer())

    questions = [turn["question"] for turn in load_history(tmp_path, guest)]
    assert len(questions) == MAX_TURNS == 20
    assert questions[0] == "Question 6?"
    assert questions[-1] == f"Question {MAX_TURNS + 5}?"


def test_damaged_file_is_treated_as_an_empty_conversation(tmp_path):
    guest = new_guest_id()
    (tmp_path / f"{guest}.json").write_text("{not json", encoding="utf-8")

    assert load_history(tmp_path, guest) == []


def test_clear_history_deletes_only_that_guest(tmp_path):
    anna, bruno = new_guest_id(), new_guest_id()
    add_turn(tmp_path, anna, "Anna?", answer())
    add_turn(tmp_path, bruno, "Bruno?", answer())

    clear_history(tmp_path, anna)
    clear_history(tmp_path, new_guest_id())  # a guest with no file: no error

    assert load_history(tmp_path, anna) == []
    assert len(load_history(tmp_path, bruno)) == 1


# ---------- Atomic writing ----------

def test_saving_leaves_no_temporary_files(tmp_path):
    guest = new_guest_id()

    add_turn(tmp_path, guest, "Question?", answer())
    add_turn(tmp_path, guest, "Another?", answer())

    assert [path.name for path in tmp_path.iterdir()] == [f"{guest}.json"]


def test_failed_save_keeps_the_old_conversation(tmp_path, monkeypatch):
    guest = new_guest_id()
    add_turn(tmp_path, guest, "First question?", answer())

    def broken_replace(source, target):
        raise OSError("disk full")
    monkeypatch.setattr(conversations.os, "replace", broken_replace)

    with pytest.raises(OSError):
        add_turn(tmp_path, guest, "Second question?", answer())

    monkeypatch.undo()
    assert [turn["question"] for turn in load_history(tmp_path, guest)] == ["First question?"]
    assert [path.name for path in tmp_path.iterdir()] == [f"{guest}.json"]  # temporary file removed


# ---------- Deleting old conversations ----------

def test_conversations_older_than_24_hours_are_deleted(tmp_path):
    old, recent = new_guest_id(), new_guest_id()
    add_turn(tmp_path, old, "Old?", answer())
    add_turn(tmp_path, recent, "Recent?", answer())
    now = os.path.getmtime(tmp_path / f"{recent}.json")
    a_day_and_a_minute_ago = now - 24 * 60 * 60 - 60
    os.utime(tmp_path / f"{old}.json", (a_day_and_a_minute_ago, a_day_and_a_minute_ago))

    deleted = delete_old_conversations(tmp_path, now=now)

    assert deleted == 1
    assert load_history(tmp_path, old) == []
    assert len(load_history(tmp_path, recent)) == 1


def test_deleting_old_conversations_when_the_folder_does_not_exist_yet(tmp_path):
    assert delete_old_conversations(tmp_path / "conversas") == 0
