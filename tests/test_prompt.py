"""Building the prompt and reading the model's answer (sources and "not in the documents")."""

import pytest

from assistant.prompt import build_prompt, parse_answer

DOCUMENTS = {
    "the-house.md": "Wi-Fi password: azulejo2026",
    "house-rules.md": "Quiet hours from 22:00 to 08:00.",
}
NAMES = list(DOCUMENTS)


# ---------- build_prompt ----------

def test_prompt_has_every_document_delimited_with_its_name():
    prompt = build_prompt(DOCUMENTS, "What is the Wi-Fi password?", "Casa Test")

    for name, text in DOCUMENTS.items():
        assert f'<document name="{name}">\n{text}\n</document>' in prompt


def test_prompt_has_question_business_name_and_rules():
    prompt = build_prompt(DOCUMENTS, "  Há berço?  ", "Casa Test")

    assert "Question: Há berço?\nAnswer:" in prompt  # question without the extra spaces, at the end
    assert "Casa Test" in prompt
    assert "SOURCE: none" in prompt                   # the "not in the documents" rule
    assert "same language as the question" in prompt


def test_real_documents_come_after_the_examples():
    prompt = build_prompt(DOCUMENTS, "Question?", "Casa Test")
    assert prompt.index("example-guide.md") < prompt.index("the-house.md")


def test_braces_in_documents_or_question_do_not_break_the_prompt():
    prompt = build_prompt({"code.txt": "Door code {1234}"}, "What is {this}?", "Casa Test")
    assert "Door code {1234}" in prompt
    assert "What is {this}?" in prompt


# ---------- parse_answer ----------

def test_answer_with_one_source():
    answer = parse_answer("The password is azulejo2026.\nSOURCE: the-house.md", NAMES)

    assert answer.text == "The password is azulejo2026."
    assert answer.sources == ["the-house.md"]
    assert answer.found is True


def test_answer_with_several_sources():
    answer = parse_answer("Text.\nSOURCE: the-house.md, house-rules.md", NAMES)
    assert answer.sources == ["the-house.md", "house-rules.md"]


@pytest.mark.parametrize("source_line", ["SOURCE: none", "SOURCE: None", "source: none", "  SOURCE:none  "])
def test_answer_not_in_the_documents(source_line):
    answer = parse_answer(f"Essa informação não consta do guia da casa.\n{source_line}", NAMES)

    assert answer.found is False
    assert answer.sources == []
    assert answer.text == "Essa informação não consta do guia da casa."


def test_made_up_source_names_are_dropped():
    answer = parse_answer("Text.\nSOURCE: the-house.md, secret-file.md", NAMES)
    assert answer.sources == ["the-house.md"]


def test_repeated_and_quoted_sources_are_cleaned():
    answer = parse_answer('Text.\nSOURCE: "the-house.md", the-house.md', NAMES)
    assert answer.sources == ["the-house.md"]


def test_answer_without_source_line():
    answer = parse_answer("The password is azulejo2026.", NAMES)

    assert answer.text == "The password is azulejo2026."
    assert answer.sources == []
    assert answer.found is True


def test_multi_line_answer_keeps_its_lines():
    raw = "Check-out is at 11:00.\nBags can stay until 15:00.\n\nSOURCE: the-house.md\n"
    answer = parse_answer(raw, NAMES)
    assert answer.text == "Check-out is at 11:00.\nBags can stay until 15:00."
