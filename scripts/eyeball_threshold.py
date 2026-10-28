# scripts/eyeball_threshold.py
"""Print the best dense similarity for answerable vs off-topic questions, to pick MIN_DENSE_SIMILARITY.

1. Replace the <...> placeholders in ANSWERABLE with real questions.
2. Run from the repo root (no LLM calls):  python -m scripts.eyeball_threshold
"""
from app.db import get_conn
from app.search import dense_search

ANSWERABLE = [
    # NovaPay documents (data/company/)
    "What caused customers to be charged twice during the 18 March payment incident?",
    "What went wrong after the fraud-scorer v7 model was deployed on 17 March?",
    "At what time was incident INC-2026-031 resolved?",
    # HotpotQA validation questions; their paragraphs are in the corpus
    "Were Scott Derrickson and Ed Wood of the same nationality?",
    "What government position was held by the woman who portrayed Corliss Archer in the film Kiss and Tell?",
]

OFF_TOPIC = [
    "How long should I boil an egg for a soft yolk?",
    "What is a good name for a golden retriever puppy?",
    "Which gaming laptop under 1000 dollars should I buy?",
    "What time does the nearest pharmacy close tonight?",
    "How do I center a div in CSS?",
]


def best_match(conn, question: str) -> tuple[float, str]:
    """Cosine similarity and title of the single closest chunk."""
    top = dense_search(conn, question, k=1)
    return (top[0]["score"], top[0]["document_title"]) if top else (0.0, "-")


def main() -> None:
    rows = []
    with get_conn() as conn:
        for group, questions in (("answerable", ANSWERABLE), ("off-topic", OFF_TOPIC)):
            for question in questions:
                if question.startswith("<"):
                    print(f"skipped placeholder: {question[:50]}")
                    continue
                score, title = best_match(conn, question)
                rows.append((score, group, question, title))

    print(f"\n{'score':>6}  {'group':<10}  question  ->  closest document")
    for score, group, question, title in sorted(rows, reverse=True):
        print(f"{score:6.3f}  {group:<10}  {question[:60]}  ->  {title[:40]}")

    answerable = [r[0] for r in rows if r[1] == "answerable"]
    off_topic = [r[0] for r in rows if r[1] == "off-topic"]
    if answerable and off_topic:
        low, high = min(answerable), max(off_topic)
        print(f"\nlowest answerable: {low:.3f}   highest off-topic: {high:.3f}")
        if low > high:
            print(f"clean gap: a threshold around {(low + high) / 2:.2f} separates them")
        else:
            print(f"no clean gap: stay safely below the lowest answerable, e.g. {low - 0.05:.2f}")


if __name__ == "__main__":
    main()
