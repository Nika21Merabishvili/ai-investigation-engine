# tests/test_chunkers.py
import pytest

from app.ingest import fixed_chunks, paragraph_chunks

TITLE = "Test Doc"

SAMPLES = {
    "empty": "",
    "only_whitespace": "\n\n   \n\n",
    "short": "NovaPay processes card payments.",
    "many_small_paragraphs": "\n\n".join(
        f"Paragraph {i} has a few words in it." for i in range(60)
    ),
    "one_huge_paragraph": " ".join(f"word{i}" for i in range(750)),
    "markdown_with_headings": (
        "# Overview\nNovaPay runs three services.\n\n"
        "## Payments API\n" + "The API validates cards. " * 40 + "\n\n"
        "# Incident\nOn March 12 payments failed for two hours."
    ),
}

CHUNKERS = [
    pytest.param(lambda text: paragraph_chunks(text, TITLE), 200, id="paragraph"),
    pytest.param(lambda text: fixed_chunks(text, TITLE), 100, id="fixed"),
]


def body_words(chunk: str) -> list[str]:
    """Check the 'Title: ...' line, then return the words after it."""
    assert chunk.startswith(f"Title: {TITLE}\n"), "chunk must start with the title line"
    return chunk.split("\n", 1)[1].split()


@pytest.mark.parametrize("chunk_fn, max_words", CHUNKERS)
@pytest.mark.parametrize("sample", list(SAMPLES))
def test_no_chunk_is_empty(chunk_fn, max_words, sample):
    for chunk in chunk_fn(SAMPLES[sample]):
        assert body_words(chunk), f"empty chunk for sample '{sample}'"


@pytest.mark.parametrize("chunk_fn, max_words", CHUNKERS)
@pytest.mark.parametrize("sample", list(SAMPLES))
def test_no_chunk_exceeds_its_size(chunk_fn, max_words, sample):
    for chunk in chunk_fn(SAMPLES[sample]):
        assert len(body_words(chunk)) <= max_words, f"chunk too long for sample '{sample}'"


# Exact outputs for the tiny examples: the tests above would pass a chunker that returns [].

def with_title(*bodies: str) -> list[str]:
    return [f"Title: {TITLE}\n{body}" for body in bodies]


def test_fixed_chunks_exact():
    assert fixed_chunks("a b c d e f g h i j k l", TITLE, size=5, overlap=2) == with_title(
        "a b c d e", "d e f g h", "g h i j k", "j k l"
    )


def test_fixed_chunks_no_redundant_last_window():
    assert fixed_chunks("a b c d e f g h i j", TITLE, size=5, overlap=2) == with_title(
        "a b c d e", "d e f g h", "g h i j"
    )


@pytest.mark.parametrize("overlap", [5, 6])
def test_fixed_chunks_rejects_overlap_not_below_size(overlap):
    with pytest.raises(ValueError):
        fixed_chunks("a b c d e f", TITLE, size=5, overlap=overlap)


def test_paragraph_chunks_exact():
    text = (
        "# Overview\nNovaPay processes card payments.\n\n"
        "It runs three services.\n\n"
        "Each team owns one service.\n\n"
        "# Incident\nPayments failed on March 12."
    )
    assert paragraph_chunks(text, TITLE, max_words=10) == with_title(
        "# Overview\nNovaPay processes card payments.\n\nIt runs three services.",
        "Each team owns one service.",
        "# Incident\nPayments failed on March 12.",
    )


def test_paragraph_chunks_keeps_stacked_headings_with_their_text():
    text = "# Incident Report\n\n## Summary\n\nPayments failed on March 12."
    assert paragraph_chunks(text, TITLE, max_words=10) == with_title(
        "# Incident Report\n\n## Summary\n\nPayments failed on March 12."
    )


def test_paragraph_chunks_cuts_oversized_block():
    words = [f"w{i}" for i in range(25)]
    text = "Short intro here.\n\n" + " ".join(words)
    assert paragraph_chunks(text, TITLE, max_words=10) == with_title(
        "Short intro here.",
        " ".join(words[0:10]),
        " ".join(words[10:20]),
        " ".join(words[20:25]),
    )


@pytest.mark.parametrize("chunker", [fixed_chunks, paragraph_chunks])
def test_empty_input_gives_no_chunks(chunker):
    assert chunker("", TITLE) == []
