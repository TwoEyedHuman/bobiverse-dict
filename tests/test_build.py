"""Unit tests for select_definition and build_csv."""

import csv
import json
import pytest
from pathlib import Path

from scripts.models import Entry, select_definition
from scripts.build import build_csv, build_manifest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_entry(**overrides) -> Entry:
    base = {
        "term": "GUPPI",
        "first_appears": 1,
        "tags": ["ai"],
        "definitions": [{"safe_after_book": 1, "text": "An AI assistant."}],
    }
    base.update(overrides)
    return Entry.model_validate(base)


# ---------------------------------------------------------------------------
# select_definition
# ---------------------------------------------------------------------------

def test_single_definition_selected():
    entry = make_entry()
    assert select_definition(entry, 1) == "An AI assistant."


def test_multi_tier_book1_returns_tier1():
    entry = make_entry(definitions=[
        {"safe_after_book": 1, "text": "Tier 1."},
        {"safe_after_book": 2, "text": "Tier 2."},
    ])
    assert select_definition(entry, 1) == "Tier 1."


def test_multi_tier_book2_returns_tier2():
    entry = make_entry(definitions=[
        {"safe_after_book": 1, "text": "Tier 1."},
        {"safe_after_book": 2, "text": "Tier 2."},
    ])
    assert select_definition(entry, 2) == "Tier 2."


def test_term_excluded_when_first_appears_after_target():
    entry = make_entry(
        first_appears=3,
        definitions=[{"safe_after_book": 3, "text": "Only in book 3+."}],
    )
    assert select_definition(entry, 1) is None
    assert select_definition(entry, 2) is None
    assert select_definition(entry, 3) == "Only in book 3+."


def test_all_spoilers_passthrough():
    entry = make_entry(definitions=[
        {"safe_after_book": 1, "text": "Tier 1."},
        {"safe_after_book": 2, "text": "Tier 2."},
        {"safe_after_book": 3, "text": "Tier 3."},
    ])
    assert select_definition(entry, 999) == "Tier 3."


def test_no_safe_definition_returns_none():
    # first_appears=1 but earliest safe_after_book=3; reader at book 1 has no safe def
    entry = make_entry(
        first_appears=1,
        definitions=[{"safe_after_book": 3, "text": "Spoiler."}],
    )
    assert select_definition(entry, 1) is None
    assert select_definition(entry, 2) is None
    assert select_definition(entry, 3) == "Spoiler."


# ---------------------------------------------------------------------------
# build_csv
# ---------------------------------------------------------------------------

def test_build_csv_creates_file(tmp_path):
    entries = [make_entry()]
    out = tmp_path / "book-1" / "test.csv"
    build_csv(entries, 1, out)
    assert out.exists()


def test_build_csv_excludes_future_entries(tmp_path):
    entries = [
        make_entry(term="Early", first_appears=1, definitions=[{"safe_after_book": 1, "text": "Def."}]),
        make_entry(term="Late", first_appears=3, definitions=[{"safe_after_book": 3, "text": "Late def."}]),
    ]
    out = tmp_path / "test.csv"
    build_csv(entries, 1, out)
    rows = list(csv.DictReader(out.open()))
    terms = [r["term"] for r in rows]
    assert "Early" in terms
    assert "Late" not in terms


def test_build_csv_multi_tier_book1_vs_book2(tmp_path):
    entries = [
        make_entry(
            term="Milo",
            first_appears=1,
            definitions=[
                {"safe_after_book": 1, "text": "Alive."},
                {"safe_after_book": 2, "text": "Killed."},
            ],
        )
    ]
    out1 = tmp_path / "b1.csv"
    out2 = tmp_path / "b2.csv"
    build_csv(entries, 1, out1)
    build_csv(entries, 2, out2)

    def read_def(path):
        return list(csv.DictReader(path.open()))[0]["definition"]

    assert read_def(out1) == "Alive."
    assert read_def(out2) == "Killed."


def test_build_csv_all_entries_present(tmp_path):
    entries = [
        make_entry(term="A", first_appears=1, definitions=[{"safe_after_book": 1, "text": "a"}]),
        make_entry(term="B", first_appears=2, definitions=[{"safe_after_book": 2, "text": "b"}]),
        make_entry(term="C", first_appears=4, definitions=[{"safe_after_book": 4, "text": "c"}]),
    ]
    out = tmp_path / "all.csv"
    build_csv(entries, 999, out)
    rows = list(csv.DictReader(out.open()))
    assert {r["term"] for r in rows} == {"A", "B", "C"}


# ---------------------------------------------------------------------------
# build_manifest
# ---------------------------------------------------------------------------

def _make_dist(root: Path, book: str, formats: list[str]) -> None:
    d = root / f"book-{book}"
    d.mkdir(parents=True, exist_ok=True)
    for fmt in formats:
        ext = "kindle.zip" if fmt == "kindle" else ("stardict.zip" if fmt == "stardict" else fmt)
        (d / f"bobiverse-book-{book}.{ext}").write_bytes(b"x")


def test_build_manifest_creates_file(tmp_path):
    _make_dist(tmp_path, "1", ["stardict", "csv"])
    out = tmp_path / "manifest.json"
    build_manifest(tmp_path, out)
    assert out.exists()
    data = json.loads(out.read_text())
    assert "generated" in data
    assert len(data["files"]) == 2


def test_build_manifest_all_formats(tmp_path):
    _make_dist(tmp_path, "1", ["stardict", "csv", "kindle"])
    out = tmp_path / "manifest.json"
    build_manifest(tmp_path, out)
    data = json.loads(out.read_text())
    formats = {e["format"] for e in data["files"]}
    assert formats == {"stardict", "csv", "kindle"}


def test_build_manifest_book_types(tmp_path):
    _make_dist(tmp_path, "1", ["stardict"])
    _make_dist(tmp_path, "all", ["stardict"])
    out = tmp_path / "manifest.json"
    build_manifest(tmp_path, out)
    data = json.loads(out.read_text())
    books = [e["book"] for e in data["files"]]
    assert books == [1, "all"]
    assert isinstance(books[0], int)
    assert isinstance(books[1], str)


def test_build_manifest_numeric_books_sorted_before_all(tmp_path):
    for book in ["all", "2", "1", "3"]:
        _make_dist(tmp_path, book, ["stardict"])
    out = tmp_path / "manifest.json"
    build_manifest(tmp_path, out)
    data = json.loads(out.read_text())
    books = [e["book"] for e in data["files"]]
    assert books == [1, 2, 3, "all"]


def test_build_manifest_filename_relative(tmp_path):
    _make_dist(tmp_path, "1", ["stardict"])
    out = tmp_path / "manifest.json"
    build_manifest(tmp_path, out)
    data = json.loads(out.read_text())
    filename = data["files"][0]["filename"]
    assert filename == "book-1/bobiverse-book-1.stardict.zip"


def test_build_manifest_empty_dist(tmp_path):
    out = tmp_path / "manifest.json"
    build_manifest(tmp_path, out)
    data = json.loads(out.read_text())
    assert data["files"] == []
