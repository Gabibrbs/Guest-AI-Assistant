# Guest assistant for a holiday rental

A small web app that answers guests' questions using only the host's own documents (the house guide). It replies in the guest's language, shows which document the answer came from, and says so when the guide doesn't have the answer instead of making something up.

The example business is a fictional holiday rental in Porto, "Casa da Ribeira Example". The same code works for any small business with a few documents: upload your own file and the assistant starts using it.

This is a demo project for my freelance work (Python automation and AI integrations).

![The assistant answering guests in different languages](docs/screenshot.png)

▶ Watch the 64-second demo: https://youtu.be/28QO39AkLzk

## What it does

- Answers from the documents in `documentos/` (seven short house-guide files in English: check-in, the house, house rules, getting here, the neighbourhood, bookings, emergencies).
- Shows the source document under each answer.
- When the answer is not in the documents, it says so and suggests contacting the host.
- Replies in the language of the question, even though the documents are in English.
- Lets you upload your own `.txt`, `.md` or `.pdf` file, which becomes part of the knowledge for the conversation.

## How it works

```
documents (.md/.txt/.pdf) ──► one prompt with every document, each tagged with its name
                                         │
guest question ──────────────────────────┘
                                         ▼
                                Gemini API (google-genai)
                                         │
                                         ▼
           answer text  +  last line "SOURCE: file.md"  (or "SOURCE: none")
                                         │
                                         ▼
               page shows the answer, and the source or "not in the house guide"
```

The code is split into small modules:

| File | What it does |
|---|---|
| `assistant/documents.py` | Reads `.md`, `.txt` and `.pdf` (pypdf) and refuses empty, broken, password-protected or unsupported files with a clear message. |
| `assistant/prompt.py` | Builds the prompt and reads the `SOURCE:` line back from the model's reply. |
| `assistant/gemini_client.py` | Calls Gemini, retrying temporary errors (429, 500, 503, 504 and connection problems) with waits of 5 s and 10 s. |
| `assistant/answer.py` | Puts the three together: question in, answer with sources out. |
| `app.py` | Flask routes: page, ask, upload, start over. |
| `evaluate.py` | Asks a fixed list of questions to the real API and saves the answers to a CSV. |

## Run it locally (Windows, PowerShell)

You need Python 3.12 and a Gemini API key from Google AI Studio.

```powershell
git clone https://github.com/Gabibrbs/guest-ai-assistant.git
cd guest-ai-assistant
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # then open .env and paste your key in GEMINI_API_KEY
python app.py
```

Open http://127.0.0.1:5000.

If PowerShell refuses to run `Activate.ps1`, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

The model is set in `.env` with `GEMINI_MODEL` (default `gemini-3.5-flash`). The API key is only read from `.env`, which is excluded from Git.

## Design decisions

**No vector database.** The house guide is about 1,500 words, so every document fits in the prompt. Search, embeddings and a vector database would add moving parts without improving the answers at this size. For a business with hundreds of pages, retrieval would become worth it.

**How the assistant avoids making things up.**
- The prompt is based on the best of three prompt versions I compared in a course assignment: a clear role, the context between tags, numbered steps, an explicit "if it's not in the documents, say so" rule, and two short examples (one answered, one not).
- One rule was added after testing: the model must not draw conclusions from what the documents leave out. Without it, when asked "do you accept large dogs?", the model answered "no" because the house rules only mention small pets. With the rule, it says what the guide does say and that large dogs are not mentioned.
- Every reply must end with a `SOURCE:` line. The code only accepts names of documents that really exist, so the page can never show an invented source.
- The documents are wrapped as information and the prompt tells the model to ignore instructions inside them, since uploaded files come from outside.
- The sample guide leaves some common questions unanswered on purpose (baby cot, lift, airport transfer, bike rental, large dogs) to test this behaviour.

**Simple on purpose.** Flask, Jinja2 templates and plain CSS. The only JavaScript is a short, commented snippet that shows "Reading the house guide…" while waiting, because an answer can take several seconds. The conversation is kept in memory: this is a single-user demo, not a multi-user product.

## Tests

```powershell
pytest -v
```

89 tests, all passing, in about one second. They never call the real API: the Gemini client is replaced by a fake one that returns prepared replies or raises API errors, and the retry waits are replaced so no test sleeps.

- **Documents:** each file type, accents and the Windows BOM, empty files, wrong encoding, broken, scanned (no text) and password-protected PDFs, folder loading.
- **Prompt and answers:** every document is in the prompt with its name; one or several sources; "not in the documents"; invented source names are dropped; missing `SOURCE:` line.
- **API calls:** retries on 429/500/503/504 and connection errors, doubling waits, giving up after three attempts, no retries on permanent errors (400, 401, 403, 404), empty replies, missing API key.
- **Flask routes:** home page, asking, history, uploading `.txt` and `.pdf` and using them in the next answer, invalid and oversized uploads, cleaning of uploaded file names, starting over.
- **Evaluation script:** its automatic checks and CSV output, with the fake client.

## Evaluation with the real API

`evaluate.py` is kept outside pytest because it uses the real API and its quota. It asks 17 fixed questions in six languages (English, Portuguese, Spanish, French, German, Italian). Four have no answer in the documents and two (large dogs) are only partly answered, so those two are marked for checking by hand. For each answer it checks automatically whether the "found / not found" result, the source and an expected keyword are right, and it leaves two columns to fill in by hand: right language, and anything invented.

```powershell
python evaluate.py
python evaluate.py --retry-failed resultados_avaliacao_YYYYMMDD_HHMM.csv   # ask again only the failed questions
```

Results with `gemini-3.5-flash`, over two days because of the free-tier daily limit (8 questions on 20 November 2026, the other 9 on 21 November):

| Check | Result |
|---|---|
| Questions answered without errors | 17 of 17 |
| "Found / not found" right | 15 of 15 (the two large-dog questions are checked by hand) |
| Source right | 17 of 17 |
| Expected keyword in the answer | 9 of 9 |
| Answers with Markdown | 0 |

- The four questions with no answer in the guide (baby cot, lift, airport transfer, bike rental) all got "this is not in the house guide" with a suggestion to contact the host, and no source.
- The two large-dog questions (Portuguese and French) said that only small pets are mentioned and that large dogs are not covered by the guide, and suggested asking the host. Neither said that large dogs are refused.
- Reading all 17 answers, each one was in the language of the question and I found nothing invented.

## Limitations

- **Speed varies a lot.** In the second evaluation run, which measured the API's own time separately from the retry waits, 6 of 9 answers took under 5 seconds (median 3.2 s), but three took 26, 62 and 70 seconds, and two needed a new attempt after an error. On the first day, with only the total time measured, answers took between 2 and 51 seconds. The slow answers come from the API's response time, not from the app's own code.
- **Free-tier quota:** in my account (free tier, November 2026) Gemini allowed 20 requests per day, which is enough to try the demo but not to use it with real guests. Google changes these limits, so check yours in Google AI Studio.
- **Each question is answered on its own.** The conversation is shown on the page, but earlier questions are not sent to the model, so a follow-up like "and on Sunday?" will not work. Ask complete questions.
- **Demo, not production:** no login, one shared conversation kept in memory, and uploaded documents are lost when the server restarts.
- **The model can still be wrong.** The prompt rules and the source check reduce the risk, and the evaluation script measures it, but they can't remove it completely.

## Background

The prompt and the retry logic come from an assignment in my AI specialisation course at Tokio School, where I compared three prompt versions for answering questions about a text with the Gemini API. The course material itself is not included in this repository.

## Author

Gabriel Barbosa, junior Python developer based in Maia, Porto, Portugal. [github.com/Gabibrbs](https://github.com/Gabibrbs)
