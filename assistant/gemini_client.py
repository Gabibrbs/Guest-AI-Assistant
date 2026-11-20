"""Call the Gemini API, retrying on temporary errors (429, 500, 503, 504).

Simplified from the pedir_ao_modelo function in my Tokio School notebook.
"""

import os
import time

from google import genai
from google.genai import errors, types

DEFAULT_MODEL = "gemini-3.5-flash"

MAX_ATTEMPTS = 3            # the first request counts as an attempt
FIRST_WAIT_SECONDS = 5      # doubles after each failure: 5 s, then 10 s
TIMEOUT_SECONDS = 60
TEMPORARY_ERROR_CODES = (429, 500, 503, 504)  # 429: too many requests; 5xx: server problems

# Low "thinking": looking up a short guide does not need long reasoning, and answers come faster
GENERATION_CONFIG = types.GenerateContentConfig(
    thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
)


class GeminiError(Exception):
    """The model could not give an answer. The message is shown to the user."""


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


def is_temporary(error):
    """True for errors worth trying again.

    API errors carry an HTTP code. Connection problems and timeouts have no code
    and are treated as temporary, like in the notebook.
    """
    if isinstance(error, errors.APIError):
        return error.code in TEMPORARY_ERROR_CODES
    return True


def ask_gemini(client, model, prompt, sleep=None):
    """Send the prompt and return the model's text.

    `client` and `sleep` are parameters so the tests can pass fake ones
    (no real API calls and no real waiting).
    """
    if sleep is None:
        sleep = time.sleep  # looked up at call time, so tests can also replace time.sleep
    wait_seconds = FIRST_WAIT_SECONDS

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=GENERATION_CONFIG,
            )
        except Exception as error:
            if is_temporary(error) and attempt < MAX_ATTEMPTS:
                sleep(wait_seconds)
                wait_seconds = wait_seconds * 2
                continue
            if is_temporary(error):
                raise GeminiError("The assistant is busy right now. Please try again in a minute.") from error
            raise GeminiError("The assistant could not answer (error from the AI service).") from error

        text = (response.text or "").strip()
        if not text:
            # For example, a reply blocked by the safety filters
            raise GeminiError("The assistant returned an empty answer. Please rephrase the question.")
        return text
