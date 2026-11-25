"""Put the pieces together: documents + question -> prompt -> Gemini -> answer with sources."""

from .gemini_client import ask_with_fallback
from .prompt import build_prompt, parse_answer


def answer_question(client, model, documents, question, business_name="this holiday rental",
                    not_found_message="Please contact the host.", sleep=None, fallback_model=None):
    """Answer a guest's question using only `documents` ({file name: text}).

    `business_name` and `not_found_message` come from the property's settings (config.toml).
    `sleep` is passed on to ask_gemini; the evaluation script uses it to count the time
    spent waiting between new attempts.
    `fallback_model` answers once if `model` is busy (None: no fallback, as in the evaluation,
    which measures one model at a time).
    """
    prompt = build_prompt(documents, question, business_name, not_found_message)
    raw_text = ask_with_fallback(client, model, fallback_model, prompt, sleep=sleep)
    return parse_answer(raw_text, document_names=list(documents))
