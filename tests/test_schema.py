"""Table-driven tests for Pydantic schema validation."""

import pytest
from pydantic import ValidationError

from scripts.models import Definition, Dictionary, Entry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_entry(**overrides) -> dict:
    base = {
        "term": "GUPPI",
        "first_appears": 1,
        "tags": ["ai"],
        "definitions": [{"safe_after_book": 1, "text": "An AI assistant."}],
    }
    base.update(overrides)
    return base


def make_dictionary(*entries: dict) -> dict:
    return {"entries": list(entries)}


# ---------------------------------------------------------------------------
# Entry-level valid cases
# ---------------------------------------------------------------------------

VALID_ENTRY_CASES = [
    pytest.param(
        make_entry(),
        id="single-definition",
    ),
    pytest.param(
        make_entry(
            definitions=[
                {"safe_after_book": 1, "text": "First def."},
                {"safe_after_book": 2, "text": "Second def."},
                {"safe_after_book": 3, "text": "Third def."},
            ]
        ),
        id="three-strictly-increasing-definitions",
    ),
    pytest.param(
        make_entry(first_appears=1, definitions=[{"safe_after_book": 1, "text": "x"}]),
        id="first_appears-equals-min-safe_after_book",
    ),
    pytest.param(
        make_entry(tags=["character", "replicant"]),
        id="multiple-tags",
    ),
    pytest.param(
        make_entry(forms=["GUPPIs", "guppy"]),
        id="forms-present-no-duplicate-term",
    ),
    pytest.param(
        make_entry(),
        id="forms-absent-defaults-empty",
    ),
]


@pytest.mark.parametrize("data", VALID_ENTRY_CASES)
def test_valid_entry(data):
    Entry.model_validate(data)


# ---------------------------------------------------------------------------
# Entry-level invalid cases
# ---------------------------------------------------------------------------

INVALID_ENTRY_CASES = [
    pytest.param(
        make_entry(tags=[]),
        "tags must be non-empty",
        id="empty-tags",
    ),
    pytest.param(
        make_entry(forms=["GUPPI"]),
        "forms must not duplicate term",
        id="form-duplicates-term-exact",
    ),
    pytest.param(
        make_entry(forms=["guppi"]),
        "forms must not duplicate term",
        id="form-duplicates-term-case-insensitive",
    ),
    pytest.param(
        make_entry(
            definitions=[
                {"safe_after_book": 2, "text": "Later."},
                {"safe_after_book": 2, "text": "Same book — not strictly increasing."},
            ]
        ),
        "strictly increasing",
        id="safe_after_book-equal-not-increasing",
    ),
    pytest.param(
        make_entry(
            definitions=[
                {"safe_after_book": 3, "text": "Later."},
                {"safe_after_book": 1, "text": "Earlier — decreasing."},
            ]
        ),
        "strictly increasing",
        id="safe_after_book-decreasing",
    ),
    pytest.param(
        make_entry(first_appears=2, definitions=[{"safe_after_book": 1, "text": "x"}]),
        "first_appears",
        id="first_appears-greater-than-min-safe_after_book",
    ),
]


@pytest.mark.parametrize("data,error_fragment", INVALID_ENTRY_CASES)
def test_invalid_entry(data, error_fragment):
    with pytest.raises(ValidationError) as exc_info:
        Entry.model_validate(data)
    assert error_fragment in str(exc_info.value)


# ---------------------------------------------------------------------------
# Dictionary-level: duplicate terms
# ---------------------------------------------------------------------------

DUPLICATE_TERM_CASES = [
    pytest.param(
        make_dictionary(make_entry(term="GUPPI"), make_entry(term="GUPPI")),
        id="exact-duplicate",
    ),
    pytest.param(
        make_dictionary(make_entry(term="Guppi"), make_entry(term="guppi")),
        id="case-insensitive-duplicate",
    ),
    pytest.param(
        make_dictionary(make_entry(term="GUPPI"), make_entry(term="gUpPi")),
        id="mixed-case-duplicate",
    ),
]


@pytest.mark.parametrize("data", DUPLICATE_TERM_CASES)
def test_duplicate_terms_rejected(data):
    with pytest.raises(ValidationError) as exc_info:
        Dictionary.model_validate(data)
    assert "duplicate term" in str(exc_info.value)


def test_unique_terms_accepted():
    data = make_dictionary(make_entry(term="GUPPI"), make_entry(term="Bob"))
    Dictionary.model_validate(data)


# ---------------------------------------------------------------------------
# Full round-trip: valid dictionary with multiple definitions
# ---------------------------------------------------------------------------

def test_multi_definition_entry_round_trip():
    data = make_dictionary(
        {
            "term": "Deltans",
            "first_appears": 1,
            "tags": ["alien", "faction"],
            "definitions": [
                {"safe_after_book": 1, "text": "Hunter-gatherers."},
                {"safe_after_book": 2, "text": "Population crashes."},
                {"safe_after_book": 3, "text": "Develop agriculture."},
            ],
        }
    )
    d = Dictionary.model_validate(data)
    assert len(d.entries[0].definitions) == 3
