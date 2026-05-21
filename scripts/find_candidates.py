"""Find candidate terms for the Bobiverse Dictionary from local EPUBs."""

import argparse
import re
from collections import Counter
from pathlib import Path

import ebooklib
import yaml
from bs4 import BeautifulSoup
from ebooklib import epub
from wordfreq import word_frequency

EPSILON = 1e-9


def extract_text(epub_path: Path) -> str:
    book = epub.read_epub(str(epub_path), options={"ignore_ncx": True})
    parts = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        parts.append(soup.get_text(separator=" "))
    return " ".join(parts)


def tokenize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)
    text = re.sub(r"[0-9_]", "", text)
    tokens = re.split(r"\s+", text)
    return [t for t in tokens if len(t) >= 2]


def load_existing_terms(dictionary_path: Path) -> set[str]:
    with dictionary_path.open() as f:
        data = yaml.safe_load(f)
    return {entry["term"].lower() for entry in data.get("entries", [])}


def score_candidates(tokens: list[str], existing_terms: set[str]) -> list[dict]:
    counts = Counter(tokens)
    total = sum(counts.values())

    candidates = []
    for term, count in counts.items():
        if term in existing_terms:
            continue
        if len(term) <= 1:
            continue
        if term.isnumeric():
            continue

        corpus_freq = count / total
        baseline_freq = word_frequency(term, "en")
        score = corpus_freq / (baseline_freq + EPSILON)

        candidates.append(
            {
                "term": term,
                "score": score,
                "corpus_count": count,
                "definitions": [],
            }
        )

    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract tokens from Bobiverse EPUBs")
    parser.add_argument(
        "--epub-dir",
        type=Path,
        default=Path("~/books/bobiverse/").expanduser(),
        help="Directory containing EPUB files (default: ~/books/bobiverse/)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=50,
        metavar="N",
        help="Number of top candidates to output (default: 50)",
    )
    parser.add_argument(
        "--dictionary",
        type=Path,
        default=Path("dictionary.yaml"),
        help="Path to dictionary.yaml (default: dictionary.yaml)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("candidates.yaml"),
        help="Output path (default: candidates.yaml)",
    )
    args = parser.parse_args()

    epub_dir: Path = args.epub_dir.expanduser().resolve()
    if not epub_dir.exists():
        parser.error(f"Directory not found: {epub_dir}")

    epubs = sorted(epub_dir.glob("*.epub"))
    if not epubs:
        print(f"No .epub files found in {epub_dir}")
        return

    existing_terms = load_existing_terms(args.dictionary)
    print(f"Loaded {len(existing_terms)} existing terms from {args.dictionary}")

    all_tokens: list[str] = []
    for epub_path in epubs:
        text = extract_text(epub_path)
        tokens = tokenize(text)
        print(f"{epub_path.name}: {len(tokens):,} tokens")
        all_tokens.extend(tokens)

    print(f"Total tokens: {len(all_tokens):,}")

    candidates = score_candidates(all_tokens, existing_terms)
    top = candidates[: args.top]

    with args.output.open("w") as f:
        yaml.dump(
            {"candidates": top},
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )

    print(f"Wrote {len(top)} candidates to {args.output}")


if __name__ == "__main__":
    main()
