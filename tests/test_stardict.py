"""Tests for StarDict dictionary ZIP output."""

import csv
import gzip
import struct
import zipfile
from pathlib import Path

from scripts.build import build_csv
from scripts.models import Entry
from scripts.stardict_builder import build_stardict


def make_entry(**overrides) -> Entry:
    base = {
        "term": "GUPPI",
        "first_appears": 1,
        "tags": ["ai"],
        "definitions": [{"safe_after_book": 1, "text": "An AI assistant."}],
    }
    base.update(overrides)
    return Entry.model_validate(base)


def _parse_ifo(zf: zipfile.ZipFile) -> dict[str, str]:
    ifo_name = next(n for n in zf.namelist() if n.endswith(".ifo"))
    lines = zf.read(ifo_name).decode("utf-8").splitlines()
    assert lines[0] == "StarDict's dict ifo file"
    result = {}
    for line in lines[1:]:
        key, _, val = line.partition("=")
        result[key] = val
    return result


def _parse_idx(zf: zipfile.ZipFile) -> list[str]:
    idx_name = next(n for n in zf.namelist() if n.endswith(".idx"))
    data = zf.read(idx_name)
    headwords = []
    i = 0
    while i < len(data):
        null_pos = data.index(b"\x00", i)
        headword = data[i:null_pos].decode("utf-8")
        headwords.append(headword)
        i = null_pos + 1 + 8  # skip null + 4-byte offset + 4-byte size
    return headwords


# ---------------------------------------------------------------------------
# ZIP structure
# ---------------------------------------------------------------------------

def test_stardict_is_valid_zip(tmp_path):
    out = tmp_path / "test.stardict.zip"
    build_stardict([make_entry()], 1, out)
    assert zipfile.is_zipfile(out)


def test_stardict_contains_three_files(tmp_path):
    out = tmp_path / "test.stardict.zip"
    build_stardict([make_entry()], 1, out)
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    assert len(names) == 3
    exts = {Path(n).suffix for n in names}
    assert ".ifo" in exts
    assert ".idx" in exts
    assert ".dz" in exts


# ---------------------------------------------------------------------------
# .ifo word count matches CSV
# ---------------------------------------------------------------------------

def test_ifo_word_count_matches_csv(tmp_path):
    entries = [
        make_entry(term="Alpha", first_appears=1, definitions=[{"safe_after_book": 1, "text": "A."}]),
        make_entry(term="Beta", first_appears=1, definitions=[{"safe_after_book": 1, "text": "B."}]),
        make_entry(term="Gamma", first_appears=2, definitions=[{"safe_after_book": 2, "text": "C."}]),
    ]
    sd_path = tmp_path / "test.stardict.zip"
    csv_path = tmp_path / "test.csv"
    target_book = 1

    build_stardict(entries, target_book, sd_path)
    build_csv(entries, target_book, csv_path)

    with zipfile.ZipFile(sd_path) as zf:
        ifo = _parse_ifo(zf)
    csv_rows = list(csv.DictReader(csv_path.open()))

    assert int(ifo["wordcount"]) == len(csv_rows)


# ---------------------------------------------------------------------------
# .idx headwords sorted and count matches
# ---------------------------------------------------------------------------

def test_idx_headwords_sorted(tmp_path):
    entries = [
        make_entry(term="Zebra", first_appears=1, definitions=[{"safe_after_book": 1, "text": "Z."}]),
        make_entry(term="Alpha", first_appears=1, definitions=[{"safe_after_book": 1, "text": "A."}]),
        make_entry(term="Mango", first_appears=1, definitions=[{"safe_after_book": 1, "text": "M."}]),
    ]
    out = tmp_path / "sorted.stardict.zip"
    build_stardict(entries, 1, out)
    with zipfile.ZipFile(out) as zf:
        headwords = _parse_idx(zf)
    assert headwords == sorted(headwords)


def test_idx_headword_count_matches_csv(tmp_path):
    entries = [
        make_entry(term="Alpha", first_appears=1, definitions=[{"safe_after_book": 1, "text": "A."}]),
        make_entry(term="Beta", first_appears=1, definitions=[{"safe_after_book": 1, "text": "B."}]),
        make_entry(term="Gamma", first_appears=2, definitions=[{"safe_after_book": 2, "text": "C."}]),
    ]
    sd_path = tmp_path / "test.stardict.zip"
    csv_path = tmp_path / "test.csv"
    target_book = 1

    build_stardict(entries, target_book, sd_path)
    build_csv(entries, target_book, csv_path)

    with zipfile.ZipFile(sd_path) as zf:
        headwords = _parse_idx(zf)
    csv_rows = list(csv.DictReader(csv_path.open()))

    assert len(headwords) == len(csv_rows)


# ---------------------------------------------------------------------------
# .dict.dz decompresses cleanly
# ---------------------------------------------------------------------------

def test_dict_dz_decompresses(tmp_path):
    out = tmp_path / "test.stardict.zip"
    build_stardict([make_entry()], 1, out)
    with zipfile.ZipFile(out) as zf:
        dz_name = next(n for n in zf.namelist() if n.endswith(".dict.dz"))
        compressed = zf.read(dz_name)
    gzip.decompress(compressed)  # raises on error


# ---------------------------------------------------------------------------
# Spoiler filtering
# ---------------------------------------------------------------------------

def test_excludes_future_entries(tmp_path):
    entries = [
        make_entry(term="Early", first_appears=1, definitions=[{"safe_after_book": 1, "text": "Early."}]),
        make_entry(term="Late", first_appears=3, definitions=[{"safe_after_book": 3, "text": "Late."}]),
    ]
    out = tmp_path / "book1.stardict.zip"
    build_stardict(entries, 1, out)
    with zipfile.ZipFile(out) as zf:
        headwords = _parse_idx(zf)
    assert "Early" in headwords
    assert "Late" not in headwords


# ---------------------------------------------------------------------------
# Integration: real dictionary.yaml
# ---------------------------------------------------------------------------

def test_build_py_produces_stardict_zip(tmp_path):
    from scripts.build import load_dictionary

    dict_path = Path(__file__).parent.parent / "dictionary.yaml"
    dictionary = load_dictionary(dict_path)

    sd_path = tmp_path / "bobiverse-book-1.stardict.zip"
    build_stardict(dictionary.entries, 1, sd_path)

    assert sd_path.exists()
    assert zipfile.is_zipfile(sd_path)

    with zipfile.ZipFile(sd_path) as zf:
        headwords = _parse_idx(zf)
    assert len(headwords) > 0
