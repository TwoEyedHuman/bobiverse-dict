"""Build script for Bobiverse Dictionary."""

import argparse
import sys
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError


class Definition(BaseModel):
    safe_after_book: int
    text: str


class Entry(BaseModel):
    term: str
    first_appears: int
    tags: list[str]
    definitions: list[Definition]


class Dictionary(BaseModel):
    entries: list[Entry]


def load_dictionary(path: Path) -> Dictionary:
    with path.open() as f:
        raw = yaml.safe_load(f)
    return Dictionary.model_validate(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bobiverse Dictionary build tool")
    parser.add_argument("--validate-only", action="store_true", help="Validate dictionary.yaml and exit")
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


if __name__ == "__main__":
    main()
