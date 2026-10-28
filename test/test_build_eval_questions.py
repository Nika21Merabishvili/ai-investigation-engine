# tests/test_build_eval_questions.py
"""The checks in scripts/build_eval_questions.py. No database, no dataset download.

Run: python -m pytest test/test_build_eval_questions.py -q
"""
import pytest

from scripts.build_eval_questions import check_company_question, file_stem, title_for_file

GOOD = {"id": "co_conflict_01", "type": "contradiction", "question": "How many?", "gold_answer": "1,284 vs 1,317",
        "gold_files": ["incident_report_INC-2026-031", "finance_refund_memo"], "expected": "flag_conflict"}


def test_a_correct_question_has_no_problems():
    assert check_company_question(GOOD) == []


def test_expected_must_match_the_type():
    assert "must have expected 'flag_conflict'" in check_company_question({**GOOD, "expected": "answer"})[0]


def test_an_open_check_note_blocks_the_build():
    assert "check" in check_company_question({**GOOD, "check": "confirm the number"})[0]


def test_gold_file_counts_per_type():
    assert check_company_question({**GOOD, "gold_files": ["finance_refund_memo"]})          # contradiction needs 2
    unanswerable = {**GOOD, "type": "unanswerable", "expected": "insufficient"}
    assert check_company_question(unanswerable)                                             # must have none
    assert check_company_question({**unanswerable, "gold_files": []}) == []


def test_file_stem_drops_extension_and_folders():
    assert file_stem("postmortem_INC-2026-031.docx") == "postmortem_INC-2026-031"
    assert file_stem(r"data\company\finance_refund_memo.pdf") == "finance_refund_memo"


DOCS = [("Postmortem INC-2026-031: Duplicate Card Charges", "postmortem_INC-2026-031.docx"),
        ("Incident report INC-2026-031", "incident_report_INC-2026-031.pdf")]


def test_title_for_file_matches_the_whole_file_name():
    assert title_for_file(DOCS, "postmortem_INC-2026-031") == "Postmortem INC-2026-031: Duplicate Card Charges"


def test_title_for_file_stops_on_an_unknown_or_partial_name():
    with pytest.raises(SystemExit):
        title_for_file(DOCS, "postmortem")          # a partial name is not enough
