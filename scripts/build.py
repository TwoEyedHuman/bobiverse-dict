"""Build script for Bobiverse Dictionary."""

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on sys.path when run directly as a script.
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from pydantic import ValidationError

from scripts.models import Dictionary, Entry, select_definition
from scripts.kindle_builder import build_kindle
from scripts.stardict_builder import build_stardict


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


def _parse_dist_file(path: Path, dist_dir: Path) -> dict | None:
    name = path.name
    if name.endswith(".kindle.zip"):
        fmt = "kindle"
    elif name.endswith(".stardict.zip"):
        fmt = "stardict"
    elif name.endswith(".csv"):
        fmt = "csv"
    else:
        return None
    book_part = path.parent.name.removeprefix("book-")
    try:
        book: int | str = int(book_part)
    except ValueError:
        book = book_part
    return {"book": book, "format": fmt, "filename": str(path.relative_to(dist_dir))}


def build_manifest(dist_dir: Path, output_path: Path) -> None:
    entries = []
    for path in sorted(dist_dir.rglob("bobiverse-book-*")):
        if path.is_file():
            entry = _parse_dist_file(path, dist_dir)
            if entry is not None:
                entries.append(entry)
    entries.sort(key=lambda e: (
        (0, e["book"]) if isinstance(e["book"], int) else (1, 0),
        e["format"],
    ))
    manifest = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": entries,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    print(f"Wrote {output_path}")


def build_target(entries: list[Entry], target_book: int, dir_name: str, stem: str, fmt: str) -> None:
    dist_dir = ROOT / "dist" / dir_name
    if fmt in ("csv", "all"):
        path = dist_dir / f"{stem}.csv"
        build_csv(entries, target_book, path)
        print(f"Wrote {path}")
    if fmt in ("kindle", "all"):
        path = dist_dir / f"{stem}.kindle.zip"
        build_kindle(entries, target_book, path)
        print(f"Wrote {path}")
    if fmt in ("stardict", "all"):
        path = dist_dir / f"{stem}.stardict.zip"
        build_stardict(entries, target_book, path)
        print(f"Wrote {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bobiverse Dictionary build tool")
    parser.add_argument("--validate-only", action="store_true", help="Validate dictionary.yaml and exit")
    parser.add_argument("--target-book", metavar="N|all", help="Build output for book N (or 'all')")
    parser.add_argument("--all", action="store_true", help="Build all book targets (1..max first_appears) plus book-all")
    parser.add_argument("--format", choices=["csv", "kindle", "stardict", "all"], default="all",
                        help="Output format (default: all)")
    parser.add_argument("--manifest", action="store_true", help="Generate dist/manifest.json from existing dist/ files")
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

    if args.manifest:
        build_manifest(ROOT / "dist", ROOT / "dist" / "manifest.json")
        return

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
