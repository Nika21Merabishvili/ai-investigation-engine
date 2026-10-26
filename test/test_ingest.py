# tests/test_ingest.py
from app.ingest import content_hash


def test_whitespace_differences_give_the_same_hash():
    assert content_hash("Payments  failed.\n\nAt 9:00") == content_hash(" Payments failed. At 9:00 ")


def test_different_text_gives_a_different_hash():
    assert content_hash("refund") != content_hash("refunds")
