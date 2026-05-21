"""Tests for find_candidates.py — lemmatization and candidate scoring."""

from scripts.find_candidates import score_candidates, tokenize


def test_tokenize_lemmatizes_common_forms():
    """Inflected forms map to shared lemma, producing fewer unique lemmas than surface forms."""
    pairs = tokenize("The cats chased mice. A cat chases a mouse.")
    lemmas = [lemma for lemma, _ in pairs]
    # "cat" and "cats" both → "cat"
    assert lemmas.count("cat") == 2
    # "chase" and "chases" both → "chase"
    assert lemmas.count("chase") == 2


def test_score_candidates_collapses_inflections():
    """Pairs sharing a lemma produce one entry, not two."""
    pairs = [
        ("gorilloid", "gorilloid"),
        ("gorilloid", "gorilloid"),
        ("gorilloid", "gorilloids"),
    ]
    candidates = score_candidates(pairs, existing_terms=set())
    gorilloid_entries = [c for c in candidates if c["term"] == "gorilloid"]
    assert len(gorilloid_entries) == 1


def test_score_candidates_accumulates_corpus_count():
    """corpus_count sums across all surface forms sharing the lemma."""
    pairs = [
        ("gorilloid", "gorilloid"),
        ("gorilloid", "gorilloid"),
        ("gorilloid", "gorilloids"),
    ]
    candidates = score_candidates(pairs, existing_terms=set())
    entry = next(c for c in candidates if c["term"] == "gorilloid")
    assert entry["corpus_count"] == 3


def test_score_candidates_forms_contains_all_surface_forms():
    """forms includes every distinct surface form seen."""
    pairs = [
        ("gorilloid", "gorilloid"),
        ("gorilloid", "gorilloids"),
    ]
    candidates = score_candidates(pairs, existing_terms=set())
    entry = next(c for c in candidates if c["term"] == "gorilloid")
    assert set(entry["forms"]) == {"gorilloid", "gorilloids"}


def test_score_candidates_forms_sorted_by_frequency():
    """forms is ordered most-frequent first."""
    pairs = [
        ("gorilloid", "gorilloids"),
        ("gorilloid", "gorilloids"),
        ("gorilloid", "gorilloid"),
    ]
    candidates = score_candidates(pairs, existing_terms=set())
    entry = next(c for c in candidates if c["term"] == "gorilloid")
    assert entry["forms"][0] == "gorilloids"


def test_score_candidates_forms_nonempty():
    """Every candidate has at least one form."""
    pairs = [("replicant", "replicant"), ("replicant", "replicants")]
    candidates = score_candidates(pairs, existing_terms=set())
    for c in candidates:
        assert len(c["forms"]) >= 1


def test_score_candidates_filters_existing_terms():
    """Lemmas in existing_terms are excluded from output."""
    pairs = [("replicant", "replicant"), ("guppi", "guppi")]
    candidates = score_candidates(pairs, existing_terms={"replicant"})
    terms = [c["term"] for c in candidates]
    assert "replicant" not in terms
    assert "guppi" in terms
