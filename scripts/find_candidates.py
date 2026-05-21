"""Find candidate terms for the Bobiverse Dictionary from local EPUBs."""

import argparse
import re
from pathlib import Path

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub


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
    return [t for t in tokens if len(t) >= 3]


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract tokens from Bobiverse EPUBs")
    parser.add_argument(
        "--epub-dir",
        type=Path,
        default=Path("~/books/bobiverse/").expanduser(),
        help="Directory containing EPUB files (default: ~/books/bobiverse/)",
    )
    args = parser.parse_args()

    epub_dir: Path = args.epub_dir.expanduser().resolve()
    if not epub_dir.exists():
        parser.error(f"Directory not found: {epub_dir}")

    epubs = sorted(epub_dir.glob("*.epub"))
    if not epubs:
        print(f"No .epub files found in {epub_dir}")
        return

    for epub_path in epubs:
        text = extract_text(epub_path)
        tokens = tokenize(text)
        print(f"{epub_path.name}: {len(tokens):,} tokens")


if __name__ == "__main__":
    main()
