"""Tests for Kindle dictionary ZIP output."""

import csv
import zipfile
from pathlib import Path

import pytest
from lxml import etree

from scripts.build import build_csv
from scripts.kindle_builder import build_kindle
from scripts.models import Entry

IDX_NS = "https://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf"


def make_entry(**overrides) -> Entry:
    base = {
        "term": "GUPPI",
        "first_appears": 1,
        "tags": ["ai"],
        "definitions": [{"safe_after_book": 1, "text": "An AI assistant."}],
    }
    base.update(overrides)
    return Entry.model_validate(base)


def _parse_opf(zf: zipfile.ZipFile) -> etree._Element:
    return etree.fromstring(zf.read("content.opf"))


def _headwords(zf: zipfile.ZipFile) -> list[str]:
    root = etree.fromstring(zf.read("dictionary.html"))
    return [el.get("value") for el in root.iter(f"{{{IDX_NS}}}orth")]


# ---------------------------------------------------------------------------
# ZIP structure
# ---------------------------------------------------------------------------

def test_kindle_is_valid_zip(tmp_path):
    out = tmp_path / "test.kindle.zip"
    build_kindle([make_entry()], 1, out)
    assert zipfile.is_zipfile(out)


def test_kindle_contains_opf_and_html(tmp_path):
    out = tmp_path / "test.kindle.zip"
    build_kindle([make_entry()], 1, out)
    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
    assert "content.opf" in names
    assert "dictionary.html" in names


# ---------------------------------------------------------------------------
# OPF well-formed and correct
# ---------------------------------------------------------------------------

def test_opf_is_well_formed_xml(tmp_path):
    out = tmp_path / "test.kindle.zip"
    build_kindle([make_entry()], 1, out)
    with zipfile.ZipFile(out) as zf:
        _parse_opf(zf)  # raises if not well-formed


def test_opf_references_dictionary_html(tmp_path):
    out = tmp_path / "test.kindle.zip"
    build_kindle([make_entry()], 1, out)
    with zipfile.ZipFile(out) as zf:
        root = _parse_opf(zf)
    OPF_NS = "http://www.idpf.org/2007/opf"
    items = root.findall(f".//{{{OPF_NS}}}item")
    hrefs = {item.get("href") for item in items}
    assert "dictionary.html" in hrefs


def test_opf_has_kindle_language_metadata(tmp_path):
    out = tmp_path / "test.kindle.zip"
    build_kindle([make_entry()], 1, out)
    with zipfile.ZipFile(out) as zf:
        opf_text = zf.read("content.opf").decode()
    assert "DictionaryInLanguage" in opf_text
    assert "DictionaryOutLanguage" in opf_text


# ---------------------------------------------------------------------------
# HTML well-formed and headword count matches CSV
# ---------------------------------------------------------------------------

def test_html_is_well_formed_xml(tmp_path):
    out = tmp_path / "test.kindle.zip"
    build_kindle([make_entry()], 1, out)
    with zipfile.ZipFile(out) as zf:
        etree.fromstring(zf.read("dictionary.html"))  # raises if not well-formed


def test_headword_count_matches_csv(tmp_path):
    entries = [
        make_entry(term="Alpha", first_appears=1, definitions=[{"safe_after_book": 1, "text": "A."}]),
        make_entry(term="Beta", first_appears=1, definitions=[{"safe_after_book": 1, "text": "B."}]),
        make_entry(term="Gamma", first_appears=2, definitions=[{"safe_after_book": 2, "text": "C."}]),
    ]
    kindle_path = tmp_path / "test.kindle.zip"
    csv_path = tmp_path / "test.csv"
    target_book = 1

    build_kindle(entries, target_book, kindle_path)
    build_csv(entries, target_book, csv_path)

    with zipfile.ZipFile(kindle_path) as zf:
        words = _headwords(zf)
    csv_rows = list(csv.DictReader(csv_path.open()))

    assert len(words) == len(csv_rows)


def test_headword_count_matches_csv_all(tmp_path):
    entries = [
        make_entry(term="Alpha", first_appears=1, definitions=[{"safe_after_book": 1, "text": "A."}]),
        make_entry(term="Beta", first_appears=2, definitions=[{"safe_after_book": 2, "text": "B."}]),
        make_entry(term="Gamma", first_appears=3, definitions=[{"safe_after_book": 3, "text": "C."}]),
    ]
    kindle_path = tmp_path / "all.kindle.zip"
    csv_path = tmp_path / "all.csv"

    build_kindle(entries, 999, kindle_path)
    build_csv(entries, 999, csv_path)

    with zipfile.ZipFile(kindle_path) as zf:
        words = _headwords(zf)
    csv_rows = list(csv.DictReader(csv_path.open()))

    assert len(words) == len(csv_rows) == 3


# ---------------------------------------------------------------------------
# Spoiler filtering
# ---------------------------------------------------------------------------

def test_excludes_future_entries(tmp_path):
    entries = [
        make_entry(term="Early", first_appears=1, definitions=[{"safe_after_book": 1, "text": "Early."}]),
        make_entry(term="Late", first_appears=3, definitions=[{"safe_after_book": 3, "text": "Late."}]),
    ]
    out = tmp_path / "book1.kindle.zip"
    build_kindle(entries, 1, out)
    with zipfile.ZipFile(out) as zf:
        words = _headwords(zf)
    assert "Early" in words
    assert "Late" not in words


# ---------------------------------------------------------------------------
# Integration: build.py → dist file exists
# ---------------------------------------------------------------------------

def test_build_py_produces_kindle_zip(tmp_path):
    from pathlib import Path
    import yaml
    from scripts.build import load_dictionary

    dict_path = Path(__file__).parent.parent / "dictionary.yaml"
    dictionary = load_dictionary(dict_path)

    kindle_path = tmp_path / "bobiverse-book-1.kindle.zip"
    build_kindle(dictionary.entries, 1, kindle_path)

    assert kindle_path.exists()
    assert zipfile.is_zipfile(kindle_path)

    with zipfile.ZipFile(kindle_path) as zf:
        words = _headwords(zf)
    assert len(words) > 0
