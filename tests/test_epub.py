"""Tests for EPUB dictionary output."""

import csv
import zipfile
from pathlib import Path

import ebooklib
import pytest
from ebooklib import epub
from lxml import etree

from scripts.build import build_csv
from scripts.epub_builder import build_epub
from scripts.models import Entry, select_definition

XHTML_NS = "http://www.w3.org/1999/xhtml"
EPUB_NS = "http://www.idpf.org/2007/ops"

DICTENTRY_ATTRIB = f"{{{EPUB_NS}}}type"


def make_entry(**overrides) -> Entry:
    base = {
        "term": "GUPPI",
        "first_appears": 1,
        "tags": ["ai"],
        "definitions": [{"safe_after_book": 1, "text": "An AI assistant."}],
    }
    base.update(overrides)
    return Entry.model_validate(base)


def _count_epub_entries(epub_path: Path) -> list[str]:
    """Return sorted list of glossterm text nodes from the EPUB dictionary."""
    book = epub.read_epub(str(epub_path), options={"ignore_ncx": True})
    docs = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
    assert docs, "No XHTML documents in EPUB"

    terms = []
    for doc in docs:
        root = etree.fromstring(doc.get_content())
        for article in root.iter(f"{{{XHTML_NS}}}article"):
            if article.get(DICTENTRY_ATTRIB) == "dictentry":
                for dfn in article.iter(f"{{{XHTML_NS}}}dfn"):
                    if dfn.get(DICTENTRY_ATTRIB) == "glossterm":
                        terms.append(dfn.text_content() if hasattr(dfn, "text_content") else (dfn.text or ""))
    return terms


def _dfn_texts(epub_path: Path) -> list[str]:
    """Parse EPUB zip directly — avoids ebooklib XHTML parsing quirks."""
    with zipfile.ZipFile(epub_path) as zf:
        xhtml_names = [n for n in zf.namelist() if n.endswith(".xhtml")]
        assert xhtml_names, "No .xhtml in EPUB zip"
        terms = []
        for name in xhtml_names:
            root = etree.fromstring(zf.read(name))
            for dfn in root.iter(f"{{{XHTML_NS}}}dfn"):
                if dfn.get(DICTENTRY_ATTRIB) == "glossterm":
                    terms.append(dfn.text or "")
        return terms


# ---------------------------------------------------------------------------
# Valid ZIP
# ---------------------------------------------------------------------------

def test_epub_is_valid_zip(tmp_path):
    entries = [make_entry()]
    out = tmp_path / "test.epub"
    build_epub(entries, 1, out)
    assert zipfile.is_zipfile(out)


def test_epub_mimetype_first(tmp_path):
    entries = [make_entry()]
    out = tmp_path / "test.epub"
    build_epub(entries, 1, out)
    with zipfile.ZipFile(out) as zf:
        assert zf.namelist()[0] == "mimetype"
        assert zf.read("mimetype") == b"application/epub+zip"


def test_epub_contains_required_files(tmp_path):
    entries = [make_entry()]
    out = tmp_path / "test.epub"
    build_epub(entries, 1, out)
    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
    assert "META-INF/container.xml" in names
    assert "OEBPS/content.opf" in names
    assert "OEBPS/dictionary.xhtml" in names
    assert "OEBPS/toc.ncx" in names


# ---------------------------------------------------------------------------
# Entry count matches CSV
# ---------------------------------------------------------------------------

def test_epub_entry_count_matches_csv(tmp_path):
    entries = [
        make_entry(term="Alpha", first_appears=1, definitions=[{"safe_after_book": 1, "text": "A."}]),
        make_entry(term="Beta", first_appears=1, definitions=[{"safe_after_book": 1, "text": "B."}]),
        make_entry(term="Gamma", first_appears=2, definitions=[{"safe_after_book": 2, "text": "C."}]),
    ]
    epub_path = tmp_path / "test.epub"
    csv_path = tmp_path / "test.csv"
    target_book = 1

    build_epub(entries, target_book, epub_path)
    build_csv(entries, target_book, csv_path)

    terms = _dfn_texts(epub_path)
    csv_rows = list(csv.DictReader(csv_path.open()))

    assert len(terms) == len(csv_rows)


def test_epub_all_entry_count_matches_csv(tmp_path):
    entries = [
        make_entry(term="Alpha", first_appears=1, definitions=[{"safe_after_book": 1, "text": "A."}]),
        make_entry(term="Beta", first_appears=2, definitions=[{"safe_after_book": 2, "text": "B."}]),
        make_entry(term="Gamma", first_appears=3, definitions=[{"safe_after_book": 3, "text": "C."}]),
    ]
    epub_path = tmp_path / "all.epub"
    csv_path = tmp_path / "all.csv"

    build_epub(entries, 999, epub_path)
    build_csv(entries, 999, csv_path)

    terms = _dfn_texts(epub_path)
    csv_rows = list(csv.DictReader(csv_path.open()))

    assert len(terms) == len(csv_rows) == 3


# ---------------------------------------------------------------------------
# No entries beyond target book
# ---------------------------------------------------------------------------

def test_epub_excludes_future_entries(tmp_path):
    entries = [
        make_entry(term="Early", first_appears=1, definitions=[{"safe_after_book": 1, "text": "Early def."}]),
        make_entry(term="Late", first_appears=3, definitions=[{"safe_after_book": 3, "text": "Late def."}]),
    ]
    out = tmp_path / "book1.epub"
    build_epub(entries, 1, out)

    terms = _dfn_texts(out)
    assert "Early" in terms
    assert "Late" not in terms


def test_epub_excludes_spoiler_definitions(tmp_path):
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
    out = tmp_path / "book1.epub"
    build_epub(entries, 1, out)

    with zipfile.ZipFile(out) as zf:
        xhtml = zf.read("OEBPS/dictionary.xhtml").decode()
    assert "Alive." in xhtml
    assert "Killed." not in xhtml


# ---------------------------------------------------------------------------
# Alphabetical sort
# ---------------------------------------------------------------------------

def test_epub_entries_sorted_alphabetically(tmp_path):
    entries = [
        make_entry(term="Zebra", first_appears=1, definitions=[{"safe_after_book": 1, "text": "Z."}]),
        make_entry(term="Apple", first_appears=1, definitions=[{"safe_after_book": 1, "text": "A."}]),
        make_entry(term="Mango", first_appears=1, definitions=[{"safe_after_book": 1, "text": "M."}]),
    ]
    out = tmp_path / "sorted.epub"
    build_epub(entries, 1, out)

    terms = _dfn_texts(out)
    assert terms == sorted(terms, key=str.lower)


# ---------------------------------------------------------------------------
# Integration: build.py CLI → dist file exists
# ---------------------------------------------------------------------------

def test_build_py_produces_epub(tmp_path, monkeypatch):
    """Smoke test: build_epub called with real dictionary produces a valid ZIP."""
    from pathlib import Path
    import yaml
    from scripts.build import load_dictionary

    dict_path = Path(__file__).parent.parent / "dictionary.yaml"
    dictionary = load_dictionary(dict_path)

    epub_path = tmp_path / "bobiverse-book-1.epub"
    build_epub(dictionary.entries, 1, epub_path)

    assert epub_path.exists()
    assert zipfile.is_zipfile(epub_path)

    terms = _dfn_texts(epub_path)
    assert len(terms) > 0

    # Verify no entry from beyond book 1
    for entry in dictionary.entries:
        if entry.first_appears > 1:
            assert entry.term not in terms
