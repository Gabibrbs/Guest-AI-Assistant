"""The automatic checks of the evaluation script (the script itself uses the real API; these tests do not)."""

from helpers import FakeGeminiClient, api_error

from assistant.prompt import Answer
from evaluate import CSV_COLUMNS, QUESTIONS, check_answer, read_csv, run_evaluation, save_csv, summary

WIFI = {"language": "EN", "question": "Wi-Fi?", "expected_found": True,
        "sources": ["the-house.md"], "keywords": ["azulejo2026"]}
COT = {"language": "EN", "question": "Cot?", "expected_found": False, "sources": [], "keywords": []}
DOGS = {"language": "PT", "question": "Cães grandes?", "expected_found": None,
        "sources": ["house-rules.md"], "keywords": []}


def test_correct_answer_passes_every_check():
    checks = check_answer(WIFI, Answer("The password is azulejo2026.", ["the-house.md"], True))
    assert checks["found_ok"] is True
    assert checks["source_ok"] is True
    assert checks["keywords_ok"] is True
    assert checks["has_markdown"] is False


def test_wrong_source_and_missing_keyword_fail():
    checks = check_answer(WIFI, Answer("The password is on the fridge.", ["house-rules.md"], True))
    assert checks["source_ok"] is False
    assert checks["keywords_ok"] is False


def test_invented_answer_to_a_question_not_in_documents_fails():
    checks = check_answer(COT, Answer("Yes, there is a cot.", ["the-house.md"], True))
    assert checks["found_ok"] is False
    assert checks["source_ok"] is False


def test_not_in_documents_answer_passes():
    checks = check_answer(COT, Answer("This is not in the house guide.", [], False))
    assert checks["found_ok"] is True
    assert checks["source_ok"] is True
    assert checks["keywords_ok"] == ""  # no keyword to check


def test_partial_question_is_left_for_checking_by_hand():
    checks = check_answer(DOGS, Answer("Small pets are welcome; large dogs are not mentioned.", ["house-rules.md"], True))
    assert checks["found_ok"] == ""
    assert checks["check_by_hand"] is True


def test_markdown_is_detected():
    assert check_answer(WIFI, Answer("The password is **azulejo2026**.", ["the-house.md"], True))["has_markdown"] is True


def test_expected_sources_exist_in_the_project_documents():
    from app import DOCUMENTS_FOLDER

    names = {path.name for path in DOCUMENTS_FOLDER.iterdir()}
    for item in QUESTIONS:
        for source in item["sources"]:
            assert source in names, f"{item['question']}: {source} does not exist"


def test_run_evaluation_and_csv_with_fake_client(tmp_path):
    client = FakeGeminiClient("The password is azulejo2026.\nSOURCE: the-house.md", api_error(403))
    waits = []

    rows = run_evaluation(client, "test-model", {"the-house.md": "text"}, [WIFI, COT], sleep=waits.append)

    assert rows[0]["found_ok"] is True and rows[0]["error"] == ""
    assert "could not answer" in rows[1]["error"] and "[403]" in rows[1]["error"]  # the API code is kept
    assert waits == [5]  # one pause between the two questions, none after the last

    path = tmp_path / "results.csv"
    save_csv(rows, path)
    saved = read_csv(path)
    assert list(saved[0]) == CSV_COLUMNS
    assert saved[0]["answer"] == "The password is azulejo2026."
    # The summary gives the same counts for the new rows and for the rows read back from the CSV
    assert summary(saved) == summary(rows)
    assert "found_ok: 1 of 1" in summary(saved)
    assert "errors: 1" in summary(saved)


def test_stops_asking_when_the_quota_is_reached():
    # 3 x 429 = the question fails after all the new attempts
    client = FakeGeminiClient(api_error(429), api_error(429), api_error(429))

    rows = run_evaluation(client, "test-model", {"the-house.md": "text"}, [WIFI, COT, DOGS], sleep=lambda s: None)

    assert len(client.models.calls) == 3  # only the first question was sent
    assert "[429]" in rows[0]["error"]
    assert rows[1]["error"].startswith("not asked") and rows[2]["error"].startswith("not asked")


def test_asks_only_the_chosen_questions():
    client = FakeGeminiClient("Not in the guide.\nSOURCE: none")

    rows = run_evaluation(client, "test-model", {"the-house.md": "text"}, [WIFI, COT, DOGS],
                          numbers=[2], sleep=lambda s: None)

    assert [row["number"] for row in rows] == [2]
    assert rows[0]["question"] == "Cot?"
    assert rows[0]["found_ok"] is True
