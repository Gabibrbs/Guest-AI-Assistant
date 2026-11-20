"""Put the pieces together: documents + question -> prompt -> Gemini -> answer with sources."""

from .gemini_client import ask_gemini
from .prompt import build_prompt, parse_answer

BUSINESS_NAME = "Casa da Ribeira Example"


def answer_question(client, model, documents, question):
    """Answer a guest's question using only `documents` ({file name: text})."""
    prompt = build_prompt(documents, question, BUSINESS_NAME)
    raw_text = ask_gemini(client, model, prompt)
    return parse_answer(raw_text, document_names=list(documents))
