"""Call the Gemini API, retrying on temporary errors (429, 500, 503, 504).

Simplified from the pedir_ao_modelo function in my Tokio School notebook.

If the main model is still busy after the new attempts, the same question is sent once
to a fallback model (GEMINI_FALLBACK_MODEL) before the guest sees an error.
"""

import logging
import os
import time

from google import genai
from google.genai import errors, types

DEFAULT_MODEL = "gemini-3.5-flash-lite"      # fast and cheap; answered 17 of 17 in the evaluation
DEFAULT_FALLBACK_MODEL = "gemini-3.6-flash"   # used only when the main model is busy; 17/17 usable answers
NO_FALLBACK = "none"                          # GEMINI_FALLBACK_MODEL=none turns the fallback off

MAX_ATTEMPTS = 3            # the first request counts as an attempt
FIRST_WAIT_SECONDS = 5      # doubles after each failure: 5 s, then 10 s
TIMEOUT_SECONDS = 60
TEMPORARY_ERROR_CODES = (429, 500, 503, 504)  # 429: too many requests; 5xx: server problems

# Low "thinking": looking up a short guide does not need long reasoning, and answers come faster
GENERATION_CONFIG = types.GenerateContentConfig(
    thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
)


logger = logging.getLogger(__name__)


class GeminiError(Exception):
    """The model could not give an answer. The message is shown to the user.

    `temporary` is True when the service was busy (worth trying another model).
    """

    def __init__(self, message, temporary=False):
        super().__init__(message)
        self.temporary = temporary


def create_client():
    """Create the Gemini client with the key from the GEMINI_API_KEY environment variable."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise GeminiError("GEMINI_API_KEY is not set. Copy .env.example to .env and add your key.")

    http_options = types.HttpOptions(
        timeout=TIMEOUT_SECONDS * 1000,  # in milliseconds
        # Turn off the library's own retries: ask_gemini does them, so they can be tested
        retry_options=types.HttpRetryOptions(attempts=1),
    )
    return genai.Client(api_key=api_key, http_options=http_options)


def get_model_name():
    """Model from GEMINI_MODEL in .env, or the default."""
    return os.environ.get("GEMINI_MODEL", "").strip() or DEFAULT_MODEL


def get_fallback_model_name():
    """Model from GEMINI_FALLBACK_MODEL in .env, the default, or None when it is "none"."""
    name = os.environ.get("GEMINI_FALLBACK_MODEL", "").strip() or DEFAULT_FALLBACK_MODEL
    return None if name.lower() == NO_FALLBACK else name


def is_temporary(error):
    """True for errors worth trying again.

    API errors carry an HTTP code. Connection problems and timeouts have no code
    and are treated as temporary, like in the notebook.
    """
    if isinstance(error, errors.APIError):
        return error.code in TEMPORARY_ERROR_CODES
    return True


def ask_gemini(client, model, prompt, sleep=None, max_attempts=MAX_ATTEMPTS):
    """Send the prompt and return the model's text.

    `client` and `sleep` are parameters so the tests can pass fake ones
    (no real API calls and no real waiting).
    """
    if sleep is None:
        sleep = time.sleep  # looked up at call time, so tests can also replace time.sleep
    wait_seconds = FIRST_WAIT_SECONDS

    for attempt in range(1, max_attempts + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=GENERATION_CONFIG,
            )
        except Exception as error:
            if is_temporary(error) and attempt < max_attempts:
                sleep(wait_seconds)
                wait_seconds = wait_seconds * 2
                continue
            if is_temporary(error):
                raise GeminiError("The assistant is busy right now. Please try again in a minute.",
                                  temporary=True) from error
            raise GeminiError("The assistant could not answer (error from the AI service).") from error

        text = (response.text or "").strip()
        if not text:
            # For example, a reply blocked by the safety filters
            raise GeminiError("The assistant returned an empty answer. Please rephrase the question.")
        return text


def ask_with_fallback(client, model, fallback_model, prompt, sleep=None):
    """Ask the main model; if it is still busy after the new attempts, ask the fallback once.

    Only temporary errors (the service is busy) go to the fallback. A permanent error,
    such as 400 (a bad request), would fail the same way there, so it is shown at once.
    The log says only which model was used, never the question.
    """
    try:
        return ask_gemini(client, model, prompt, sleep=sleep)
    except GeminiError as error:
        if not error.temporary or not fallback_model or fallback_model == model:
            raise
        main_error = error

    try:
        text = ask_gemini(client, fallback_model, prompt, sleep=sleep, max_attempts=1)
    except GeminiError:
        logger.warning("The main model %s was busy and the fallback model %s also failed.", model, fallback_model)
        raise main_error from None
    logger.warning("The main model %s was busy; the fallback model %s answered.", model, fallback_model)
    return text
