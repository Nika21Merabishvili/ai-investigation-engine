# scripts/build_hotpot.py
"""Build the HotpotQA corpus and the retrieval question set.

Writes:
  data/hotpot_paragraphs.jsonl    one unique paragraph per line (the 50,000+ documents)
  eval/retrieval_questions.jsonl  200 random validation questions (seed 42) with gold titles

Run from the repo root: python -m scripts.build_hotpot
"""
import json
import random
from pathlib import Path

from datasets import load_dataset

from app.ingest import content_hash

DATASET = "hotpotqa/hotpot_qa"
CONFIG = "distractor"
TARGET_PARAGRAPHS = 50_000
N_QUESTIONS = 200
SEED = 42

PARAGRAPHS_PATH = Path("data/hotpot_paragraphs.jsonl")
QUESTIONS_PATH = Path("eval/retrieval_questions.jsonl")


def paragraphs_of(example: dict):
    """Yield (title, text) for each context paragraph of one HotpotQA question."""
    context = example["context"]
    for title, sentences in zip(context["title"], context["sentences"]):
        text = " ".join(s.strip() for s in sentences if s.strip())
        if text:  # a few paragraphs have no sentences; skip them
            yield title, text


def add_paragraphs(examples, split: str, corpus: dict, limit: int | None = None) -> None:
    """Add each paragraph not seen before to corpus (keyed by content hash).
    With a limit, stop as soon as the corpus holds that many paragraphs."""
    for example in examples:
        for title, text in paragraphs_of(example):
            h = content_hash(text)
            if h not in corpus:
                corpus[h] = {"content_hash": h, "title": title, "text": text, "split": split}
        if limit is not None and len(corpus) >= limit:
            return


def write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8 explicitly: Windows would default to cp1252 and fail on titles like "Pokémon"
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def sample_questions(validation) -> list[dict]:
    """Pick N_QUESTIONS validation questions at random, the same ones on every run."""
    picked = random.Random(SEED).sample(range(len(validation)), N_QUESTIONS)
    questions = []
    for i in picked:
        ex = validation[i]
        questions.append({
            "id": ex["id"],
            "question": ex["question"],
            "answer": ex["answer"],
            "type": ex["type"],    # 'bridge' or 'comparison'
            "level": ex["level"],  # 'easy', 'medium' or 'hard'
            # the paragraphs that hold the answer; dict.fromkeys drops repeats, keeps order
            "gold_titles": list(dict.fromkeys(ex["supporting_facts"]["title"])),
            # all 10 paragraphs of this question, for the Day 2 chunking comparison
            "paragraph_hashes": [content_hash(text) for _, text in paragraphs_of(ex)],
        })
    return questions


def main() -> None:
    validation = load_dataset(DATASET, CONFIG, split="validation")
    corpus: dict[str, dict] = {}
    add_paragraphs(validation, "validation", corpus)
    print(f"validation: {len(validation)} questions -> {len(corpus)} unique paragraphs")

    if len(corpus) < TARGET_PARAGRAPHS:
        # streaming reads train piece by piece instead of downloading all of it
        train = load_dataset(DATASET, CONFIG, split="train", streaming=True)
        add_paragraphs(train, "train", corpus, limit=TARGET_PARAGRAPHS)
        print(f"topped up from train -> {len(corpus)} unique paragraphs")

    write_jsonl(PARAGRAPHS_PATH, corpus.values())
    print(f"wrote {len(corpus)} paragraphs to {PARAGRAPHS_PATH}")

    questions = sample_questions(validation)
    write_jsonl(QUESTIONS_PATH, questions)
    print(f"wrote {len(questions)} questions to {QUESTIONS_PATH}")


if __name__ == "__main__":
    main()
