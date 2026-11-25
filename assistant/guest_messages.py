"""Messages a guest can see on their page (errors and confirmations), in six languages.

The language is the one the guest's browser asks for, or English, like the limit
messages and the privacy notice. The host's pages stay in English.
"""

from .limits import LANGUAGES

GUEST_MESSAGES = {
    # The AI service is busy, or the time limit ran out (main and fallback model)
    "busy": {
        "en": "The assistant is busy right now. Please try again in a minute.",
        "pt": "O assistente está ocupado neste momento. Tente novamente daqui a um minuto.",
        "es": "El asistente está ocupado en este momento. Inténtalo de nuevo en un minuto.",
        "fr": "L'assistant est occupé pour le moment. Veuillez réessayer dans une minute.",
        "de": "Der Assistent ist gerade ausgelastet. Bitte versuchen Sie es in einer Minute erneut.",
        "it": "L'assistente è occupato in questo momento. Riprova tra un minuto.",
    },
    # A permanent error from the AI service (for example 400 or 403)
    "failed": {
        "en": "The assistant could not answer this time. Please try again, or contact your host.",
        "pt": "O assistente não conseguiu responder desta vez. Tente novamente ou contacte o anfitrião.",
        "es": "El asistente no ha podido responder esta vez. Inténtalo de nuevo o contacta con tu anfitrión.",
        "fr": "L'assistant n'a pas pu répondre cette fois. Veuillez réessayer ou contacter votre hôte.",
        "de": "Der Assistent konnte diesmal nicht antworten. Bitte versuchen Sie es erneut oder wenden Sie sich "
              "an Ihren Gastgeber.",
        "it": "L'assistente non è riuscito a rispondere questa volta. Riprova o contatta il tuo host.",
    },
    # An empty reply, for example blocked by the safety filters
    "empty": {
        "en": "The assistant could not answer this question. Please rephrase it.",
        "pt": "O assistente não conseguiu responder a esta pergunta. Tente escrevê-la de outra forma.",
        "es": "El asistente no ha podido responder a esta pregunta. Intenta formularla de otra manera.",
        "fr": "L'assistant n'a pas pu répondre à cette question. Essayez de la reformuler.",
        "de": "Der Assistent konnte diese Frage nicht beantworten. Bitte formulieren Sie sie anders.",
        "it": "L'assistente non è riuscito a rispondere a questa domanda. Prova a riformularla.",
    },
    # The API key is missing: the details go to the log for the person who set it up
    "not_set_up": {
        "en": "The assistant is not set up yet. Please contact your host.",
        "pt": "O assistente ainda não está configurado. Contacte o anfitrião.",
        "es": "El asistente aún no está configurado. Contacta con tu anfitrión.",
        "fr": "L'assistant n'est pas encore configuré. Veuillez contacter votre hôte.",
        "de": "Der Assistent ist noch nicht eingerichtet. Bitte wenden Sie sich an Ihren Gastgeber.",
        "it": "L'assistente non è ancora configurato. Contatta il tuo host.",
    },
    "empty_question": {
        "en": "Please type a question.",
        "pt": "Escreva uma pergunta.",
        "es": "Escribe una pregunta.",
        "fr": "Veuillez écrire une question.",
        "de": "Bitte geben Sie eine Frage ein.",
        "it": "Scrivi una domanda.",
    },
    "cleared": {
        "en": "Your conversation was cleared.",
        "pt": "A sua conversa foi apagada.",
        "es": "Tu conversación se ha borrado.",
        "fr": "Votre conversation a été effacée.",
        "de": "Ihre Unterhaltung wurde gelöscht.",
        "it": "La tua conversazione è stata cancellata.",
    },
}


def guest_message(kind, accept_languages):
    """The message `kind` in the browser's language (Flask's request.accept_languages), or English."""
    language = accept_languages.best_match(LANGUAGES, default="en")
    return GUEST_MESSAGES[kind][language]
