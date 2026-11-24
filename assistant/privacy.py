"""The privacy notice for guests, in the language their browser asks for (or English).

A short line sits under the question box, with a "Privacy" link to the full notice.
The full notice says who is responsible (the property's name and contact, from
config.toml), that questions go to Google's Gemini API, not to write personal data, and
that conversations are deleted 24 hours after the last message.

What it says about Google follows the Gemini API terms for Paid Services: Google does
not use the content to improve its products and logs it for a limited time only to
detect abuse. The terms allow only Paid Services for apps used by people in the EEA,
Switzerland or the UK (https://aistudio.google.com/docs/terms, effective March 23, 2026,
read on 24 Nov 2026), so every installation
must use an API key from a project with billing turned on.
"""

from .limits import LANGUAGES

NOTICES = {
    "en": {
        "line": "Questions are sent to Google's Gemini AI. Please do not include personal data.",
        "link": "Privacy",
        "title": "Privacy",
        "provider": "This assistant is provided by {name}.",
        "contact": "Contact: {contact}.",
        "google": "To answer, your questions and the house guide are sent to the Gemini API, a Google service. "
                  "Google does not use them to improve its products and keeps them for a limited time only, "
                  "to detect abuse.",
        "personal": "Please do not write personal data in your questions: no names, ID or passport numbers, "
                    "card details or health information.",
        "deleted": "Your conversation is saved so you can see it on this page, and it is deleted 24 hours "
                   "after your last message. It is linked only to a cookie in your browser, not to your name.",
        "logs": "The app records only counts and errors, never the text of your questions.",
        "back": "Back to the assistant",
    },
    "pt": {
        "line": "As perguntas são enviadas à IA Gemini da Google. Não escreva dados pessoais.",
        "link": "Privacidade",
        "title": "Privacidade",
        "provider": "Este assistente é disponibilizado por {name}.",
        "contact": "Contacto: {contact}.",
        "google": "Para responder, as suas perguntas e o guia da casa são enviados à API Gemini, um serviço "
                  "da Google. A Google não os usa para melhorar os seus produtos e guarda-os apenas durante "
                  "um período limitado, para detetar abusos.",
        "personal": "Não escreva dados pessoais nas perguntas: nomes, números de documentos de identificação "
                    "ou passaporte, dados de cartões ou informação de saúde.",
        "deleted": "A sua conversa fica guardada para a poder ver nesta página e é apagada 24 horas depois "
                   "da sua última mensagem. Está ligada apenas a um cookie no seu browser, não ao seu nome.",
        "logs": "A aplicação regista apenas contagens e erros, nunca o texto das perguntas.",
        "back": "Voltar ao assistente",
    },
    "es": {
        "line": "Las preguntas se envían a la IA Gemini de Google. No escribas datos personales.",
        "link": "Privacidad",
        "title": "Privacidad",
        "provider": "Este asistente lo ofrece {name}.",
        "contact": "Contacto: {contact}.",
        "google": "Para responder, tus preguntas y la guía de la casa se envían a la API de Gemini, un "
                  "servicio de Google. Google no los usa para mejorar sus productos y solo los guarda durante "
                  "un tiempo limitado, para detectar abusos.",
        "personal": "No escribas datos personales en tus preguntas: nombres, números de DNI o pasaporte, "
                    "datos de tarjetas ni información de salud.",
        "deleted": "Tu conversación se guarda para que puedas verla en esta página y se borra 24 horas "
                   "después de tu último mensaje. Solo está vinculada a una cookie de tu navegador, no a tu nombre.",
        "logs": "La aplicación solo registra recuentos y errores, nunca el texto de tus preguntas.",
        "back": "Volver al asistente",
    },
    "fr": {
        "line": "Les questions sont envoyées à l'IA Gemini de Google. N'indiquez pas de données personnelles.",
        "link": "Confidentialité",
        "title": "Confidentialité",
        "provider": "Cet assistant est proposé par {name}.",
        "contact": "Contact : {contact}.",
        "google": "Pour répondre, vos questions et le guide du logement sont envoyés à l'API Gemini, un "
                  "service de Google. Google ne les utilise pas pour améliorer ses produits et ne les conserve "
                  "que pendant une durée limitée, afin de détecter les abus.",
        "personal": "N'écrivez pas de données personnelles dans vos questions : noms, numéros de pièce "
                    "d'identité ou de passeport, données de carte bancaire ou informations de santé.",
        "deleted": "Votre conversation est enregistrée pour que vous puissiez la voir sur cette page, et elle "
                   "est supprimée 24 heures après votre dernier message. Elle est liée uniquement à un cookie "
                   "de votre navigateur, pas à votre nom.",
        "logs": "L'application n'enregistre que des compteurs et des erreurs, jamais le texte de vos questions.",
        "back": "Retour à l'assistant",
    },
    "de": {
        "line": "Fragen werden an die KI Gemini von Google gesendet. Bitte keine persönlichen Daten eingeben.",
        "link": "Datenschutz",
        "title": "Datenschutz",
        "provider": "Dieser Assistent wird von {name} bereitgestellt.",
        "contact": "Kontakt: {contact}.",
        "google": "Um zu antworten, werden Ihre Fragen und der Hausführer an die Gemini-API, einen Dienst "
                  "von Google, gesendet. Google verwendet sie nicht zur Verbesserung seiner Produkte und "
                  "speichert sie nur für begrenzte Zeit, um Missbrauch zu erkennen.",
        "personal": "Bitte schreiben Sie keine persönlichen Daten in Ihre Fragen: keine Namen, Ausweis- oder "
                    "Passnummern, Kartendaten oder Gesundheitsinformationen.",
        "deleted": "Ihre Unterhaltung wird gespeichert, damit Sie sie auf dieser Seite sehen können, und "
                   "24 Stunden nach Ihrer letzten Nachricht gelöscht. Sie ist nur mit einem Cookie in Ihrem "
                   "Browser verknüpft, nicht mit Ihrem Namen.",
        "logs": "Die Anwendung protokolliert nur Zählungen und Fehler, niemals den Text Ihrer Fragen.",
        "back": "Zurück zum Assistenten",
    },
    "it": {
        "line": "Le domande vengono inviate all'IA Gemini di Google. Non scrivere dati personali.",
        "link": "Privacy",
        "title": "Privacy",
        "provider": "Questo assistente è offerto da {name}.",
        "contact": "Contatto: {contact}.",
        "google": "Per rispondere, le tue domande e la guida della casa vengono inviate all'API Gemini, un "
                  "servizio di Google. Google non le usa per migliorare i suoi prodotti e le conserva solo "
                  "per un periodo limitato, per individuare abusi.",
        "personal": "Non scrivere dati personali nelle domande: nomi, numeri di documenti d'identità o "
                    "passaporto, dati di carte o informazioni sulla salute.",
        "deleted": "La tua conversazione viene salvata per poterla vedere in questa pagina e viene cancellata "
                   "24 ore dopo il tuo ultimo messaggio. È collegata solo a un cookie del tuo browser, non al "
                   "tuo nome.",
        "logs": "L'applicazione registra solo conteggi ed errori, mai il testo delle tue domande.",
        "back": "Torna all'assistente",
    },
}


def notice_language(accept_languages):
    """The browser's language if there is a notice in it, otherwise English."""
    return accept_languages.best_match(LANGUAGES, default="en")


def privacy_notice(prop, accept_languages):
    """The notice for this property, in the guest's language.

    Returns the language code, the short texts (line, link, title, back) and the
    paragraphs of the full notice, with the property's name and contact filled in.
    """
    language = notice_language(accept_languages)
    texts = NOTICES[language]
    responsible = texts["provider"].format(name=prop.name)
    if prop.host_contact:
        responsible += " " + texts["contact"].format(contact=prop.host_contact)
    return {
        "language": language,
        "line": texts["line"],
        "link": texts["link"],
        "title": texts["title"],
        "back": texts["back"],
        "paragraphs": [responsible, texts["google"], texts["personal"], texts["deleted"], texts["logs"]],
    }
