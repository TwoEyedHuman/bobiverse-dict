"""Build script for Bobiverse Dictionary."""

import argparse
import csv
import sys
from pathlib import Path

# Ensure project root is on sys.path when run directly as a script.
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from pydantic import ValidationError

from scripts.models import Dictionary, Entry


def load_dictionary(path: Path) -> Dictionary:
    with path.open() as f:
        raw = yaml.safe_load(f)
    return Dictionary.model_validate(raw)


def select_definition(entry: Entry, target_book: int) -> str | None:
    if entry.first_appears > target_book:
        return None
    safe = [d for d in entry.definitions if d.safe_after_book <= target_book]
    if not safe:
        return None
    return safe[-1].text.strip()


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Bobiverse Dictionary build tool")
    parser.add_argument("--validate-only", action="store_true", help="Validate dictionary.yaml and exit")
    parser.add_argument("--target-book", metavar="N|all", help="Build CSV for book N (or 'all')")
    args = parser.parse_args()

    dict_path = Path(__file__).parent.parent / "dictionary.yaml"

    try:
        dictionary = load_dictionary(dict_path)
    except (yaml.YAMLError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"dictionary.yaml: {len(dictionary.entries)} entries")

    if args.validate_only:
        sys.exit(0)

    if args.target_book:
        raw = args.target_book
        if raw == "all":
            target_book = 999
            output_path = Path(__file__).parent.parent / "dist" / "book-all" / "bobiverse-book-all.csv"
        else:
            try:
                target_book = int(raw)
            except ValueError:
                print(f"Error: --target-book must be an integer or 'all', got {raw!r}", file=sys.stderr)
                sys.exit(1)
            output_path = Path(__file__).parent.parent / "dist" / f"book-{raw}" / f"bobiverse-book-{raw}.csv"

        build_csv(dictionary.entries, target_book, output_path)
        print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
