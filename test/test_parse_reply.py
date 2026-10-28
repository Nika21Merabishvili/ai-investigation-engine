# tests/test_parse_reply.py
import pytest

from app.answer import parse_reply

EMPTY = '{"status": "insufficient", "answer": "", "citations": [], "conflicts": [], "missing": []}'


def test_parse_reply_ignores_text_around_the_object():
    assert parse_reply("Here is the answer:\n```\n" + EMPTY + "\n```")["status"] == "insufficient"


def test_parse_reply_rejects_a_reply_without_json():
    with pytest.raises(ValueError):
        parse_reply("")
