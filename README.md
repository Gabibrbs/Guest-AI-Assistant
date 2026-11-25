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
| `assistant/gemini_client.py` | Calls Gemini, retrying temporary errors (429, 500, 503, 504 and connection problems) with waits of 5 s and 10 s, then asking the fallback model once. |
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

The model is set in `.env` with `GEMINI_MODEL` (default `gemini-3.5-flash-lite`), and the fallback model with `GEMINI_FALLBACK_MODEL` (default `gemini-3.6-flash`; `none` turns it off). `GEMINI_MAX_WAIT_SECONDS` (default 40, at least 20) is the longest a guest waits for an answer. The API key is only read from `.env`, which is excluded from Git.

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

Results with the main model, `gemini-3.5-flash-lite`, on 25 November 2026 (free tier, current prompt):

| Check | Result |
|---|---|
| Questions answered | 17 of 17 (3 needed a second run after "busy" errors, see below) |
| "Found / not found" right | 15 of 15 (the two large-dog questions are checked by hand) |
| Source right | 17 of 17 |
| Expected keyword in the answer | 9 of 9 |
| Answers in the language of the question | 17 of 17 |
| Answers with Markdown | 0 |
| Time per answer, without retry waits | median 3.0 s, average 4.5 s, slowest 16.3 s |

- The four questions with no answer in the guide (baby cot, lift, airport transfer, bike rental) all got "this is not in the house guide" with the host's suggestion from `config.toml`, translated, and no source.
- Large dogs: the French answer said that small pets are welcome and that large dogs are not in the guide, and suggested contacting the host. The Portuguese answer was weaker: it said only small pets are welcome and suggested contacting the host, but did not say that large dogs are not covered. Neither said that large dogs are refused.
- The cancellation question (10 days before arrival, in Italian) said that between 14 and 7 days there is a 50% refund, so 50% is kept.
- Reading all 17 answers against the guide, I found no invented facts. The host is called "the host" in the guest's language, or by the name given in the guide (Inês).
- On the first pass, 6 of the 17 questions got a 503 "busy" error at least once, and 3 still failed after three attempts. Asked again with `--retry-failed`, they were answered.

**The host's gender.** The prompt now tells the model not to assume the host's gender, not even from their name, and to say "the host" in the guest's language or use the name in the guide. A first version of this rule gave examples in several languages ("o anfitrião", "el anfitrión"...). With it, two Italian answers came out partly in Portuguese and in English, so the examples were removed and the evaluation run again: the table above is from that second run.

**Fallback model.** Because of those busy errors, the app has a second model. If the main model is still busy after its three attempts, the same question is sent once to the fallback model (`GEMINI_FALLBACK_MODEL`, default `gemini-3.6-flash`) before the guest sees an error. Only temporary errors go to the fallback: a permanent error such as 400 would fail there too. The log records that the fallback was used, never the question. I first chose `gemini-3.8-flash`, but it answered "high demand" (503) to all three test requests on 25 November, so I evaluated `gemini-3.6-flash` instead, the same day:

- 17 of 17 answered, with no errors and one new attempt. No practical fact was invented: the extra details it added (Wi-Fi network name, router reset, late check-out price) are all in the guide.
- The automatic "found / not found" check gave 13 of 15. For the lift and the airport transfer, the answer correctly said the information is not in the guide, but it cited a related document (the floor, the airport metro), so the check counted it as "found".
- In three answers (Portuguese, Spanish, German) it called the host a woman ("anfitriã", "anfitriona", "Gastgeberin"), probably from the host's name in the guide. This led to the gender rule above; the fallback has not been evaluated again with it yet.
- It was slower: median 4.1 s, average 9.5 s, slowest 63 s.

**Longest wait for a guest.** Each request may take up to 60 seconds, so without a limit the worst case was 3 attempts of 60 s, plus 5 s and 10 s of waits, plus 60 s for the fallback: 255 seconds. Now the guest waits at most `GEMINI_MAX_WAIT_SECONDS` (default 40 s). The main model must finish 15 s before the end, so the fallback still has time; each request gets only the time that is left, and no new attempt starts with less than 5 s. When the time runs out, the guest sees "The assistant is busy right now" instead of waiting.

## Limitations

- **Speed and "busy" errors depend on Google's service.** With `gemini-3.5-flash-lite`, 11 of 17 answers took under 5 seconds, but the slowest took 16 seconds, and on the free tier many requests first got a "busy" error. The fallback model reduces, but cannot remove, the chance that a guest sees "The assistant is busy right now", and the 40-second limit means a very slow answer is cut off. The slow answers come from the API's response time, not from the app's own code.
- **Free-tier quota:** in my account (free tier, November 2026) Google AI Studio showed 500 requests per day for `gemini-3.5-flash-lite` and 20 per day for the Flash models. Google changes these limits, so check yours in Google AI Studio. The free tier is only for trying the app: Google's terms allow only paid services for apps used by people in the EEA, Switzerland or the UK.
- **Each question is answered on its own.** The conversation is shown on the page, but earlier questions are not sent to the model, so a follow-up like "and on Sunday?" will not work. Ask complete questions.
- **Demo, not production:** no login, one shared conversation kept in memory, and uploaded documents are lost when the server restarts.
- **The model can still be wrong.** The prompt rules and the source check reduce the risk, and the evaluation script measures it, but they can't remove it completely.

## Background

The prompt and the retry logic come from an assignment in my AI specialisation course at Tokio School, where I compared three prompt versions for answering questions about a text with the Gemini API. The course material itself is not included in this repository.

## Author

Gabriel Barbosa, junior Python developer based in Maia, Porto, Portugal. [github.com/Gabibrbs](https://github.com/Gabibrbs)
