"""Run a fixed set of questions against the real Gemini API and save the answers to a CSV.

Not part of pytest: it uses the real API (and its quota). I run it before recording the
video to check the quality of the answers, like the evaluation in my Tokio School notebook.

Run with:  python evaluate.py
Ask again only the questions that failed (for example after reaching the daily quota):
           python evaluate.py --retry-failed resultados_avaliacao_YYYYMMDD_HHMM.csv
"""

import argparse
import csv
import time
from datetime import datetime

from dotenv import load_dotenv

from app import DOCUMENTS_FOLDER
from assistant.answer import answer_question
from assistant.documents import load_folder
from assistant.gemini_client import GeminiError, create_client, get_model_name

PAUSE_SECONDS = 5  # between questions, to stay under the requests-per-minute limit

# expected_found: True = the answer is in the documents, False = it is not,
#                 None = partly (check by hand).
# sources: documents the answer may come from. keywords: at least one must appear in the answer.
QUESTIONS = [
    {"language": "EN", "question": "What is the Wi-Fi password?",
     "expected_found": True, "sources": ["the-house.md"], "keywords": ["azulejo2026"]},
    {"language": "EN", "question": "What time is check-out?",
     "expected_found": True, "sources": ["check-in-and-check-out.md"], "keywords": ["11"]},
    {"language": "EN", "question": "What is the emergency number?",
     "expected_found": True, "sources": ["emergencies-and-contacts.md"], "keywords": ["112"]},
    {"language": "EN", "question": "Do you have a baby cot?",
     "expected_found": False, "sources": [], "keywords": []},
    {"language": "PT", "question": "Qual é a password do Wi-Fi?",
     "expected_found": True, "sources": ["the-house.md"], "keywords": ["azulejo2026"]},
    {"language": "PT", "question": "Quanto é a taxa turística?",
     "expected_found": True, "sources": ["bookings-and-policies.md"], "keywords": ["€3", "3 €", "3€", "3 euros"]},
    {"language": "PT", "question": "Onde fica a farmácia mais próxima?",
     "expected_found": True, "sources": ["neighbourhood.md"], "keywords": ["Largo Novo"]},
    {"language": "PT", "question": "O prédio tem elevador?",
     "expected_found": False, "sources": [], "keywords": []},
    {"language": "PT", "question": "Aceitam cães grandes?",
     "expected_found": None, "sources": ["house-rules.md"], "keywords": []},
    {"language": "ES", "question": "¿A qué hora es el check-in?",
     "expected_found": True, "sources": ["check-in-and-check-out.md"], "keywords": ["15"]},
    {"language": "ES", "question": "¿Se puede fumar en el apartamento?",
     "expected_found": True, "sources": ["house-rules.md"], "keywords": []},
    {"language": "ES", "question": "¿Tienen servicio de traslado desde el aeropuerto?",
     "expected_found": False, "sources": [], "keywords": []},
    {"language": "FR", "question": "Que faire s'il n'y a pas d'eau chaude ?",
     "expected_found": True, "sources": ["emergencies-and-contacts.md"], "keywords": []},
    {"language": "FR", "question": "Est-ce que vous acceptez les grands chiens ?",
     "expected_found": None, "sources": ["house-rules.md"], "keywords": []},
    {"language": "DE", "question": "Kann ich mein Gepäck nach dem Check-out dalassen?",
     "expected_found": True, "sources": ["check-in-and-check-out.md"], "keywords": ["15"]},
    {"language": "IT", "question": "Si possono noleggiare biciclette?",
     "expected_found": False, "sources": [], "keywords": []},
    {"language": "IT", "question": "Quanto costa la cancellazione 10 giorni prima dell'arrivo?",
     "expected_found": True, "sources": ["bookings-and-policies.md"], "keywords": ["50"]},
]

CSV_COLUMNS = [
    "number", "language", "question", "answer", "sources", "found",
    "expected_found", "found_ok", "expected_sources", "source_ok", "keywords", "keywords_ok",
    "has_markdown", "check_by_hand",
    "seconds", "answer_seconds", "retry_wait_seconds", "attempts", "error",
    "language_ok", "invented",  # left empty, filled in by hand after reading the answers
]


def check_answer(item, answer):
    """Compare one answer with what the question expects. Returns the check columns.

    Each check is True, False, or "" when it does not apply to this question.
    """
    if item["expected_found"] is None:
        found_ok = ""
    else:
        found_ok = answer.found == item["expected_found"]

    if item["expected_found"] is False:
        source_ok = answer.sources == []
    elif item["sources"]:
        # At least one expected source, and no source outside the expected ones
        source_ok = bool(answer.sources) and all(s in item["sources"] for s in answer.sources)
    else:
        source_ok = ""

    if item["keywords"]:
        text = answer.text.lower()
        keywords_ok = any(keyword.lower() in text for keyword in item["keywords"])
    else:
        keywords_ok = ""

    return {
        "found_ok": found_ok,
        "source_ok": source_ok,
        "keywords_ok": keywords_ok,
        "has_markdown": "**" in answer.text,
        "check_by_hand": item["expected_found"] is None,
    }


def run_evaluation(client, model, documents, questions, numbers=None,
                   pause_seconds=PAUSE_SECONDS, sleep=time.sleep):
    """Ask the questions and return one row (dictionary) per question.

    `numbers` chooses which questions to ask (1 = the first); None asks them all.
    """
    if numbers is None:
        numbers = list(range(1, len(questions) + 1))

    rows = []
    quota_reached = False
    for number in numbers:
        item = questions[number - 1]
        print(f"[{number}/{len(questions)}] {item['language']}: {item['question']}")
        row = {
            "number": number,
            "language": item["language"],
            "question": item["question"],
            "expected_found": "" if item["expected_found"] is None else item["expected_found"],
            "expected_sources": ", ".join(item["sources"]),
            "keywords": ", ".join(item["keywords"]),
            "language_ok": "",
            "invented": "",
        }

        if quota_reached:
            row["error"] = "not asked: quota reached earlier in this run"
            rows.append(row)
            continue

        # Record the waits between new attempts, to separate them from the model's own time
        retry_waits = []

        def sleep_and_record(seconds):
            retry_waits.append(seconds)
            sleep(seconds)

        start = time.perf_counter()
        try:
            answer = answer_question(client, model, documents, item["question"], sleep=sleep_and_record)
        except GeminiError as error:
            code = error_code(error)
            row.update(timing_columns(start, retry_waits))
            row["error"] = f"{error} [{code}]"
            print(f"   ERROR: {error} [{code}]")
            if code == 429:
                # Still 429 after the new attempts: usually the daily quota. The next questions would fail too.
                print("   Quota reached: the remaining questions are not asked.")
                quota_reached = True
        else:
            row.update({
                "answer": answer.text,
                "sources": ", ".join(answer.sources),
                "found": answer.found,
                "error": "",
            })
            row.update(timing_columns(start, retry_waits))
            row.update(check_answer(item, answer))
            print(f"   {answer.text}\n   sources: {row['sources'] or '-'} | "
                  f"{row['seconds']} s ({row['answer_seconds']} s answering, "
                  f"{row['retry_wait_seconds']} s waiting, {row['attempts']} attempt(s))")

        rows.append(row)
        if number != numbers[-1]:
            sleep(pause_seconds)
    return rows


def timing_columns(start, retry_waits):
    """Total time, time spent waiting between new attempts, and the rest (the API's own time)."""
    total = time.perf_counter() - start
    waited = sum(retry_waits)
    return {
        "seconds": round(total, 1),
        "retry_wait_seconds": round(waited, 1),
        "answer_seconds": round(max(total - waited, 0), 1),  # max(): never negative, even with a fake sleep
        "attempts": len(retry_waits) + 1,
    }


def error_code(error):
    """HTTP code of the API error behind a GeminiError (e.g. 429), or the error type for connection problems."""
    cause = error.__cause__
    return getattr(cause, "code", None) or type(cause).__name__


def save_csv(rows, path):
    # utf-8-sig so that Excel shows the accents correctly
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS, restval="")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def is_true(value):
    # Values are True/False in a new run, and the text "True"/"False" when read back from a CSV
    return value is True or value == "True"


def summary(rows):
    """Short text summary: how many checks passed, out of the questions where they apply."""
    lines = []
    for column in ("found_ok", "source_ok", "keywords_ok"):
        checked = [row[column] for row in rows if row.get(column, "") != ""]
        lines.append(f"{column}: {sum(1 for value in checked if is_true(value))} of {len(checked)}")
    lines.append(f"answers with Markdown: {sum(1 for row in rows if is_true(row.get('has_markdown')))}")
    lines.append(f"errors: {sum(1 for row in rows if row.get('error'))}")
    answered = [row for row in rows if not row.get("error")]
    lines.append(seconds_line("seconds per answer, total", [row["seconds"] for row in answered]))
    # Rows from runs before this column existed have it empty, so they are left out here
    lines.append(seconds_line("seconds per answer, without retry waits",
                              [row.get("answer_seconds", "") for row in answered]))
    measured = [row for row in answered if str(row.get("attempts", "")) != ""]
    with_retries = [row for row in measured if str(row["attempts"]) != "1"]
    lines.append(f"answers that needed new attempts: {len(with_retries)} of {len(measured)} measured")
    lines.append(f"to check by hand: {sum(1 for row in rows if is_true(row.get('check_by_hand')))} "
                 f"(plus the language_ok and invented columns for all)")
    return "\n".join(lines)


def seconds_line(label, values):
    """'label: average X, min Y, max Z (n answers)', ignoring empty values."""
    numbers = [float(value) for value in values if value != ""]
    if not numbers:
        return f"{label}: no data"
    return (f"{label}: average {sum(numbers) / len(numbers):.1f}, "
            f"min {min(numbers):.1f}, max {max(numbers):.1f} ({len(numbers)} answers)")


def main():
    parser = argparse.ArgumentParser(description="Ask the fixed questions to the real Gemini API.")
    parser.add_argument("--retry-failed", metavar="CSV",
                        help="ask again only the questions that failed in this results file")
    args = parser.parse_args()

    old_rows = []
    numbers = None  # None = all questions
    if args.retry_failed:
        old_rows = read_csv(args.retry_failed)
        numbers = [int(row["number"]) for row in old_rows if row["error"]]
        if not numbers:
            print("No failed questions in that file.")
            return

    load_dotenv()
    model = get_model_name()
    documents = load_folder(DOCUMENTS_FOLDER)
    client = create_client()
    print(f"Model: {model} | documents: {len(documents)} | "
          f"questions: {len(numbers) if numbers else len(QUESTIONS)}\n")

    new_rows = run_evaluation(client, model, documents, QUESTIONS, numbers=numbers)

    # Keep the old rows that worked and put the new ones in their place
    asked = {row["number"] for row in new_rows}
    rows = [row for row in old_rows if int(row["number"]) not in asked] + new_rows
    rows.sort(key=lambda row: int(row["number"]))

    path = f"resultados_avaliacao_{datetime.now():%Y%m%d_%H%M}.csv"
    save_csv(rows, path)
    print(f"\nSaved {path}\n")
    print(summary(rows))


if __name__ == "__main__":
    main()
