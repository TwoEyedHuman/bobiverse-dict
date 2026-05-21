"""Build script for Bobiverse Dictionary."""

import argparse
import csv
import sys
from pathlib import Path

# Ensure project root is on sys.path when run directly as a script.
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from pydantic import ValidationError

from scripts.models import Dictionary, Entry, select_definition
from scripts.epub_builder import build_epub
from scripts.kindle_builder import build_kindle


def load_dictionary(path: Path) -> Dictionary:
    with path.open() as f:
        raw = yaml.safe_load(f)
    return Dictionary.model_validate(raw)


def build_csv(entries: list[Entry], target_book: int, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for entry in entries:
        text = select_definition(entry, target_book)
        if text is not None:
            rows.append({"term": entry.term, "definition": text})
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["term", "definition"])
        writer.writeheader()
        writer.writerows(rows)


ROOT = Path(__file__).parent.parent


def build_target(entries: list[Entry], target_book: int, dir_name: str, stem: str, fmt: str) -> None:
    dist_dir = ROOT / "dist" / dir_name
    if fmt in ("csv", "all"):
        path = dist_dir / f"{stem}.csv"
        build_csv(entries, target_book, path)
        print(f"Wrote {path}")
    if fmt in ("epub", "all"):
        path = dist_dir / f"{stem}.epub"
        build_epub(entries, target_book, path)
        print(f"Wrote {path}")
    if fmt in ("kindle", "all"):
        path = dist_dir / f"{stem}.kindle.zip"
        build_kindle(entries, target_book, path)
        print(f"Wrote {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bobiverse Dictionary build tool")
    parser.add_argument("--validate-only", action="store_true", help="Validate dictionary.yaml and exit")
    parser.add_argument("--target-book", metavar="N|all", help="Build output for book N (or 'all')")
    parser.add_argument("--all", action="store_true", help="Build all book targets (1..max first_appears) plus book-all")
    parser.add_argument("--format", choices=["csv", "epub", "kindle", "all"], default="all",
                        help="Output format (default: all)")
    args = parser.parse_args()

    dict_path = ROOT / "dictionary.yaml"

    try:
        dictionary = load_dictionary(dict_path)
    except (yaml.YAMLError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"dictionary.yaml: {len(dictionary.entries)} entries")

    if args.validate_only:
        sys.exit(0)

    if args.all:
        max_book = max(e.first_appears for e in dictionary.entries)
        for book_num in range(1, max_book + 1):
            build_target(dictionary.entries, book_num, f"book-{book_num}", f"bobiverse-book-{book_num}", args.format)
        build_target(dictionary.entries, 999, "book-all", "bobiverse-book-all", args.format)
    elif args.target_book:
        raw = args.target_book
        if raw == "all":
            build_target(dictionary.entries, 999, "book-all", "bobiverse-book-all", args.format)
        else:
            try:
                book_num = int(raw)
            except ValueError:
                print(f"Error: --target-book must be an integer or 'all', got {raw!r}", file=sys.stderr)
                sys.exit(1)
            build_target(dictionary.entries, book_num, f"book-{raw}", f"bobiverse-book-{raw}", args.format)


if __name__ == "__main__":
    main()
