# tests/test_build_hotpot.py
from scripts.build_hotpot import add_paragraphs, paragraphs_of

EXAMPLE = {
    "context": {
        "title": ["Radio City", "Empty", "Radio City copy"],
        "sentences": [
            ["Radio City is an FM station.", " It started in 2001."],
            [],
            ["Radio City is an FM station.", "It started in 2001."],  # same text, other spacing
        ],
    }
}


def test_paragraphs_are_joined_and_empty_ones_skipped():
    assert list(paragraphs_of(EXAMPLE)) == [
        ("Radio City", "Radio City is an FM station. It started in 2001."),
        ("Radio City copy", "Radio City is an FM station. It started in 2001."),
    ]


def test_duplicate_paragraphs_are_kept_once():
    corpus = {}
    add_paragraphs([EXAMPLE, EXAMPLE], "validation", corpus)
    assert len(corpus) == 1
    assert next(iter(corpus.values()))["title"] == "Radio City"  # first one wins
