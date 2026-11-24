"""Put the pieces together: documents + question -> prompt -> Gemini -> answer with sources."""

from .gemini_client import ask_gemini
from .prompt import build_prompt, parse_answer


def answer_question(client, model, documents, question, business_name="this holiday rental",
                    not_found_message="Please contact the host.", sleep=None):
    """Answer a guest's question using only `documents` ({file name: text}).

    `business_name` and `not_found_message` come from the property's settings (config.toml).
    `sleep` is passed on to ask_gemini; the evaluation script uses it to count the time
    spent waiting between new attempts.
    """
    prompt = build_prompt(documents, question, business_name, not_found_message)
    raw_text = ask_gemini(client, model, prompt, sleep=sleep)
    return parse_answer(raw_text, document_names=list(documents))
