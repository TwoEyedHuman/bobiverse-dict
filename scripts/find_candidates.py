"""Find candidate terms for the Bobiverse Dictionary from local EPUBs."""

import argparse
from collections import Counter, defaultdict
from pathlib import Path

import ebooklib
import spacy
import yaml
from bs4 import BeautifulSoup
from ebooklib import epub
from wordfreq import word_frequency

EPSILON = 1e-9

_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])
        _nlp.max_length = 10_000_000
    return _nlp


def extract_text(epub_path: Path) -> str:
    book = epub.read_epub(str(epub_path), options={"ignore_ncx": True})
    parts = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        parts.append(soup.get_text(separator=" "))
    return " ".join(parts)


def tokenize(text: str) -> list[tuple[str, str]]:
    """Return (lemma, surface_form) pairs for alphabetic tokens >= 2 chars."""
    nlp = _get_nlp()
    doc = nlp(text)
    result = []
    for token in doc:
        if not token.is_alpha:
            continue
        surface = token.lower_
        lemma = token.lemma_.lower()
        if len(lemma) < 2:
            continue
        result.append((lemma, surface))
    return result


def load_existing_terms(dictionary_path: Path) -> set[str]:
    with dictionary_path.open() as f:
        data = yaml.safe_load(f)
    return {entry["term"].lower() for entry in data.get("entries", [])}


def score_candidates(
    token_pairs: list[tuple[str, str]], existing_terms: set[str]
) -> list[dict]:
    lemma_counts: Counter[str] = Counter(lemma for lemma, _ in token_pairs)
    total = sum(lemma_counts.values())

    forms_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for lemma, surface in token_pairs:
        forms_counts[lemma][surface] += 1

    candidates = []
    for lemma, count in lemma_counts.items():
        if lemma in existing_terms:
            continue
        if len(lemma) <= 1:
            continue
        if lemma.isnumeric():
            continue

        corpus_freq = count / total
        baseline_freq = word_frequency(lemma, "en")
        score = corpus_freq / (baseline_freq + EPSILON)

        forms = [form for form, _ in forms_counts[lemma].most_common()]

        candidates.append(
            {
                "term": lemma,
                "score": score,
                "corpus_count": count,
                "forms": forms,
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

    all_pairs: list[tuple[str, str]] = []
    for epub_path in epubs:
        text = extract_text(epub_path)
        pairs = tokenize(text)
        print(f"{epub_path.name}: {len(pairs):,} tokens")
        all_pairs.extend(pairs)

    print(f"Total tokens: {len(all_pairs):,}")

    candidates = score_candidates(all_pairs, existing_terms)
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
