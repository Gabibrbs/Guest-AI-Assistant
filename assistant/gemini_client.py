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
TIMEOUT_SECONDS = 60        # the longest one request may take
TEMPORARY_ERROR_CODES = (429, 500, 503, 504)  # 429: too many requests; 5xx: server problems

# The guest never waits longer than this for an answer (GEMINI_MAX_WAIT_SECONDS in .env).
# Without it, the worst case was 3 x 60 s + 5 s + 10 s of waits + 60 s for the fallback = 255 s.
DEFAULT_MAX_WAIT_SECONDS = 40
FALLBACK_RESERVE_SECONDS = 15   # of that time, kept for the fallback model
MIN_REQUEST_SECONDS = 5         # no new request starts with less time than this left

BUSY_MESSAGE = "The assistant is busy right now. Please try again in a minute."

# Low "thinking": looking up a short guide does not need long reasoning, and answers come faster.
# Automatic function calling is off: the app gives the model no tools, and with it on the
# library writes "AFC is enabled with max remote calls: 10" in the log for every question.
GENERATION_CONFIG = types.GenerateContentConfig(
    thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
)


logger = logging.getLogger(__name__)


class GeminiError(Exception):
    """The model could not give an answer.

    The message (English) is for logs and the evaluation CSV. `kind` chooses the message
    the guest sees, in their language: "busy", "failed", "empty" or "not_set_up"
    (see guest_messages.py). `temporary` is True when the service was busy
    (worth trying another model).
    """

    def __init__(self, message, temporary=False, kind="failed"):
        super().__init__(message)
        self.temporary = temporary
        self.kind = "busy" if temporary else kind


def create_client():
    """Create the Gemini client with the key from the GEMINI_API_KEY environment variable."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise GeminiError("GEMINI_API_KEY is not set. Copy .env.example to .env and add your key.",
                          kind="not_set_up")

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


def request_config(timeout_seconds):
    """The generation settings plus this request's time limit (the library wants milliseconds)."""
    return GENERATION_CONFIG.model_copy(update={"http_options": types.HttpOptions(
        timeout=int(timeout_seconds * 1000),
        retry_options=types.HttpRetryOptions(attempts=1),  # still no retries inside the library
    )})


def ask_gemini(client, model, prompt, sleep=None, max_attempts=MAX_ATTEMPTS, deadline=None, clock=None):
    """Send the prompt and return the model's text.

    `deadline` (a moment on `clock`) is when the guest must stop waiting: each request
    only gets the time that is left, and no new attempt starts without at least
    MIN_REQUEST_SECONDS. None means no limit (the evaluation script measures the API as is).
    `client`, `sleep` and `clock` are parameters so the tests can pass fake ones
    (no real API calls and no real waiting).
    """
    if sleep is None:
        sleep = time.sleep  # looked up at call time, so tests can also replace time.sleep
    if clock is None:
        clock = time.monotonic
    wait_seconds = FIRST_WAIT_SECONDS

    for attempt in range(1, max_attempts + 1):
        timeout_seconds = TIMEOUT_SECONDS
        if deadline is not None:
            time_left = deadline - clock()
            if time_left < MIN_REQUEST_SECONDS:
                raise GeminiError(BUSY_MESSAGE, temporary=True)  # out of time before asking
            timeout_seconds = min(TIMEOUT_SECONDS, time_left)

        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=request_config(timeout_seconds),
            )
        except Exception as error:
            if not is_temporary(error):
                raise GeminiError("The assistant could not answer (error from the AI service).") from error
            time_for_another = deadline is None or deadline - clock() - wait_seconds >= MIN_REQUEST_SECONDS
            if attempt < max_attempts and time_for_another:
                sleep(wait_seconds)
                wait_seconds = wait_seconds * 2
                continue
            raise GeminiError(BUSY_MESSAGE, temporary=True) from error

        text = (response.text or "").strip()
        if not text:
            # For example, a reply blocked by the safety filters
            raise GeminiError("The assistant returned an empty answer. Please rephrase the question.",
                              kind="empty")
        return text


def ask_with_fallback(client, model, fallback_model, prompt, sleep=None, max_wait_seconds=None, clock=None):
    """Ask the main model; if it is still busy after the new attempts, ask the fallback once.

    Only temporary errors (the service is busy) go to the fallback. A permanent error,
    such as 400 (a bad request), would fail the same way there, so it is shown at once.
    The log says only which model was used, never the question.

    `max_wait_seconds` is the longest the guest waits in total. The main model must finish
    FALLBACK_RESERVE_SECONDS before the end, so the fallback still has time to answer.
    """
    if clock is None:
        clock = time.monotonic
    use_fallback = bool(fallback_model) and fallback_model != model
    deadline = None if max_wait_seconds is None else clock() + max_wait_seconds
    main_deadline = deadline
    if deadline is not None and use_fallback:
        main_deadline = deadline - FALLBACK_RESERVE_SECONDS

    try:
        return ask_gemini(client, model, prompt, sleep=sleep, deadline=main_deadline, clock=clock)
    except GeminiError as error:
        if not error.temporary or not use_fallback:
            raise
        main_error = error

    try:
        text = ask_gemini(client, fallback_model, prompt, sleep=sleep, max_attempts=1,
                          deadline=deadline, clock=clock)
    except GeminiError:
        logger.warning("The main model %s was busy and the fallback model %s also failed.", model, fallback_model)
        raise main_error from None
    logger.warning("The main model %s was busy; the fallback model %s answered.", model, fallback_model)
    return text
