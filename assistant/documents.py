"""Read the host's documents (.md, .txt, .pdf) into plain text."""

import io
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError

SUPPORTED_EXTENSIONS = (".md", ".txt", ".pdf")


class DocumentError(ValueError):
    """A file that cannot be used as a document. The message is shown to the user."""


def read_document(filename, data):
    """Turn the bytes of one file into text.

    Works the same for files in the documents folder and for files uploaded on the page.
    Raises DocumentError if the type is not supported, the file is broken or it has no text.
    """
    extension = Path(filename).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise DocumentError(f"{filename}: only .md, .txt and .pdf files are supported.")

    if extension == ".pdf":
        text = _read_pdf(filename, data)
    else:
        try:
            # "utf-8-sig" also removes the invisible BOM that some Windows editors add
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise DocumentError(f"{filename}: the text is not UTF-8. Save it as UTF-8 and try again.")

    text = text.strip()
    if not text:
        raise DocumentError(f"{filename}: the file has no text.")
    return text


def _read_pdf(filename, data):
    """Extract the text of every page of a PDF."""
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise DocumentError(f"{filename}: the PDF is password-protected.")
        pages = [page.extract_text() or "" for page in reader.pages]
    except PyPdfError:
        raise DocumentError(f"{filename}: the PDF could not be read.")
    # Scanned PDFs (images only) have no text: read_document reports them as empty
    return "\n\n".join(pages)


def load_folder(folder):
    """Read every supported file in a folder, sorted by name.

    Returns a dictionary {file name: text}. Other files (such as .gitkeep) are ignored.
    """
    documents = {}
    for path in sorted(Path(folder).iterdir()):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            documents[path.name] = read_document(path.name, path.read_bytes())
    return documents
