"""Tools shared by the tests: a fake Gemini client and small test PDFs.

No test ever calls the real API: the code under test receives FakeGeminiClient instead.
"""

import io
from types import SimpleNamespace

from google.genai import errors
from pypdf import PdfWriter


class FakeModels:
    """Stands in for client.models. Returns (or raises) the prepared replies in order."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []  # every request, so the tests can check what was sent

    def generate_content(self, model, contents, config=None):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if not self.replies:
            raise AssertionError("The fake client received more requests than expected.")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(text=reply)  # the real response also has a .text attribute


class FakeGeminiClient:
    """Use like the real client: FakeGeminiClient("reply 1", api_error(503), ...)."""

    def __init__(self, *replies):
        self.models = FakeModels(replies)


def api_error(code):
    """An error like the ones the real API raises, with an HTTP code."""
    return errors.APIError(code, {"error": {"code": code, "message": "test error", "status": "TEST"}})


def make_pdf(text):
    """Build a one-page PDF containing `text`.

    A PDF is a list of numbered objects plus a table (xref) with the byte position
    of each one, so the positions are counted while the file is built.
    """
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
        b" /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    pdf = b"%PDF-1.4\n"
    positions = []
    for number, body in enumerate(objects, start=1):
        positions.append(len(pdf))
        pdf += b"%d 0 obj\n" % number + body + b"\nendobj\n"

    xref_position = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for position in positions:
        pdf += b"%010d 00000 n \n" % position
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref_position)
    return pdf


def make_blank_pdf(password=None):
    """A PDF with one empty page (no text). With a password, the PDF is encrypted."""
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    if password:
        writer.encrypt(password)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
