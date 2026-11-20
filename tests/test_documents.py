"""Reading documents: .md, .txt, .pdf, and files that must be refused."""

from pathlib import Path

import pytest
from helpers import make_blank_pdf, make_pdf

from assistant.documents import DocumentError, load_folder, read_document

PROJECT_DOCUMENTS = Path(__file__).parent.parent / "documentos"


# ---------- Valid files ----------

def test_reads_markdown():
    assert read_document("guide.md", b"# Wi-Fi\nPassword: abc") == "# Wi-Fi\nPassword: abc"


def test_reads_text_with_accents():
    text = read_document("notas.txt", "Pequeno-almoço às 8h".encode("utf-8"))
    assert text == "Pequeno-almoço às 8h"


def test_removes_windows_bom_and_outer_spaces():
    data = "﻿  Check-in from 15:00  \n\n".encode("utf-8")
    assert read_document("guide.txt", data) == "Check-in from 15:00"


def test_extension_is_not_case_sensitive():
    assert read_document("GUIDE.TXT", b"Quiet hours from 22:00") == "Quiet hours from 22:00"


def test_reads_pdf_text():
    assert read_document("guide.pdf", make_pdf("Check-out is at 11:00")) == "Check-out is at 11:00"


# ---------- Invalid or empty files ----------

@pytest.mark.parametrize("filename", ["guide.docx", "photo.jpg", "no_extension"])
def test_refuses_unsupported_types(filename):
    with pytest.raises(DocumentError, match="only .md, .txt and .pdf"):
        read_document(filename, b"some content")


@pytest.mark.parametrize("data", [b"", b"   \n\t  "])
def test_refuses_empty_text_files(data):
    with pytest.raises(DocumentError, match="no text"):
        read_document("empty.txt", data)


def test_refuses_text_that_is_not_utf8():
    latin1_bytes = "Pequeno-almoço".encode("latin-1")
    with pytest.raises(DocumentError, match="not UTF-8"):
        read_document("old.txt", latin1_bytes)


@pytest.mark.parametrize("data", [b"", b"this is not a pdf", b"%PDF-1.4 broken file"])
def test_refuses_broken_pdf(data):
    with pytest.raises(DocumentError, match="could not be read"):
        read_document("broken.pdf", data)


def test_refuses_pdf_without_text():
    # For example a scanned PDF: pages with images only
    with pytest.raises(DocumentError, match="no text"):
        read_document("scan.pdf", make_blank_pdf())


def test_refuses_password_protected_pdf():
    with pytest.raises(DocumentError, match="password-protected"):
        read_document("secret.pdf", make_blank_pdf(password="1234"))


# ---------- Folder ----------

def test_load_folder_reads_supported_files_sorted_by_name(tmp_path):
    (tmp_path / "b-rules.md").write_text("No parties.", encoding="utf-8")
    (tmp_path / "a-wifi.txt").write_text("Password: abc", encoding="utf-8")
    (tmp_path / "c-map.pdf").write_bytes(make_pdf("Metro 5 minutes away"))
    (tmp_path / ".gitkeep").write_text("", encoding="utf-8")
    (tmp_path / "photo.jpg").write_bytes(b"not a document")

    documents = load_folder(tmp_path)

    assert list(documents) == ["a-wifi.txt", "b-rules.md", "c-map.pdf"]
    assert documents["c-map.pdf"] == "Metro 5 minutes away"


def test_load_folder_stops_on_an_invalid_document(tmp_path):
    # A broken file in the documents folder is a mistake of the host: better to see it at once
    (tmp_path / "empty.md").write_text("", encoding="utf-8")
    with pytest.raises(DocumentError):
        load_folder(tmp_path)


def test_project_documents_load():
    documents = load_folder(PROJECT_DOCUMENTS)
    assert len(documents) == 7
    assert all(name.endswith(".md") for name in documents)
