# Bobiverse Dictionary

> Build tooling and source data for spoiler-aware e-reader dictionaries covering the Bobiverse series by Dennis E. Taylor.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Repository Structure](#repository-structure)
3. [Technology Stack](#technology-stack)
4. [Schema Reference](#schema-reference)
5. [Output Formats](#output-formats)
6. [Pre-Flight Checklist](#pre-flight-checklist)
7. [Implementation Stories](#implementation-stories)
8. [Definition of Done](#definition-of-done)

---

## Architecture Overview

```
dictionary.yaml  ←  single source of truth (hand-authored)
      │
      ▼
 build.py  ─────────────────────────────────────────────────────┐
      │                                                          │
      ├── per-book spoiler filter                                │
      │      └── picks highest safe_after_book ≤ target         │
      │                                                          │
      ├── dist/book-1/                                           │
      │     ├── bobiverse-book-1.kindle.zip   (Kindle MOBI dict) │
      │     ├── bobiverse-book-1.epub         (Boox / EPUB dict) │
      │     └── bobiverse-book-1.csv                             │
      │                                                          │
      ├── dist/book-2/  (same structure)                         │
      ├── dist/book-3/  ...                                      │
      └── dist/all/     (full spoilers, all books)               │
                                                                 │
 find_candidates.py  ←  local utility (not part of build)       │
      │  reads EPUBs from ~/books/bobiverse/                     │
      │  scores words by series-frequency vs English baseline    │
      └── outputs candidates.yaml  (blank definitions, ranked)  ┘
```

### Key Design Decisions

- **Single source of truth:** All entries live in `dictionary.yaml`. No per-book files to keep in sync. The build script slices the data; you never duplicate a definition.
- **Versioned definitions:** Each entry carries an array of definitions, each tagged with `safe_after_book`. The build script selects the richest definition that doesn't exceed the target book, enabling the same term to have meaningfully different definitions for different audiences without separate entries.
- **Open-ended book numbering:** The schema uses integer book numbers with no upper bound. Supporting a new book requires only new entries (or new definition tiers on existing entries) in `dictionary.yaml` — no code changes.
- **Build-time output, no server:** All outputs are static files committed to `dist/` or produced locally. Distribution is a matter of uploading files; no backend is required.

---

## Repository Structure

```
bobiverse-dictionary/
├── README.md
├── dictionary.yaml          ← source of truth; all entries and definitions
├── pyproject.toml           ← uv-managed project
├── uv.lock
│
├── scripts/
│   ├── build.py             ← generates all dist/ outputs from dictionary.yaml
│   └── find_candidates.py  ← local utility: scans EPUBs, suggests missing terms
│
├── templates/
│   ├── kindle/              ← Kindle dictionary XML/OPF templates
│   └── epub/                ← EPUB dictionary content.opf + XHTML templates
│
├── dist/                    ← generated; gitignored (or committed if used as release assets)
│   ├── book-1/
│   │   ├── bobiverse-book-1.kindle.zip
│   │   ├── bobiverse-book-1.epub
│   │   └── bobiverse-book-1.csv
│   ├── book-2/
│   ├── book-3/
│   └── all/
│
└── tests/
    └── test_build.py
```

---

## Technology Stack

| Component | Technology | Reason |
|---|---|---|
| Language | Python 3.12 | Strong EPUB/XML library support |
| Package manager | uv | Fast, reproducible, single tool for venv + deps |
| EPUB parsing (find_candidates) | `ebooklib` | Mature EPUB read/write |
| XML generation | `lxml` | Required for well-formed Kindle OPF and EPUB dict markup |
| English frequency baseline | `wordfreq` | Multilingual word frequency data, pip-installable |
| Schema validation | `pydantic` | Validates `dictionary.yaml` on load; catches schema errors early |
| Testing | `pytest` | Standard; used for build output validation |
| Distribution | Static files | No server required; files hosted on personal site |

---

## Schema Reference

### Entry structure (`dictionary.yaml`)

```yaml
entries:
  - term: "Milo"
    first_appears: 1              # book number where term first appears
    tags: [character, replicant]  # see Tags below
    definitions:
      - safe_after_book: 1
        text: >
          A replicant of Bob, instantiated in 2157. Focuses on
          exploration and is among the first generation of Bobs.
      - safe_after_book: 2
        text: >
          A replicant of Bob, instantiated in 2157. Killed during
          the Pav evacuation in Book 1 when his ship is destroyed
          by a Medeiros drone.

  - term: "GUPPI"
    first_appears: 1
    tags: [ai, acronym]
    definitions:
      - safe_after_book: 1
        text: >
          General Unit Primary Peripheral Intelligence. The AI
          assistant assigned to each Bob replicant's ship.
```

### Field reference

| Field | Type | Required | Notes |
|---|---|---|---|
| `term` | string | yes | Display form, case-sensitive |
| `first_appears` | int | yes | Book number (1-based). Used to exclude terms from earlier-book dictionaries entirely. |
| `tags` | list[string] | yes | At least one. See tag list below. |
| `definitions` | list | yes | At least one element. |
| `definitions[].safe_after_book` | int | yes | Reader has finished this book and can see this definition without spoilers. |
| `definitions[].text` | string | yes | The definition text shown to the reader. |

### Definition selection logic

For a target dictionary covering through book N, the build script selects:

```
max(d for d in entry.definitions if d.safe_after_book <= N)
```

If no definition satisfies the condition (i.e. `first_appears > N`), the entry is omitted entirely. For the all-spoilers dictionary, N is set to `999`.

### Tags

Tags are free-form strings but the following are canonical:

`character`, `replicant`, `ai`, `alien`, `faction`, `technology`, `location`, `acronym`, `concept`, `ship`, `weapon`

---

## Output Formats

### Kindle (`.kindle.zip`)

A ZIP containing the OPF manifest, XHTML headword file, and cover image required for sideloading a custom dictionary via Kindle's dictionary format. Entries are sorted alphabetically. Requires sideloading via USB or Send-to-Kindle; cannot be pushed to the store.

### EPUB dictionary (`.epub`)

A valid EPUB 3 file using `epub:type="dictionary"` semantics, compatible with Boox and any reader that supports EPUB dictionaries. This is the most portable format.

### CSV (`.csv`)

Plain `term,definition` CSV. Useful as a fallback for any reader that supports custom word lists, or for importing into other tools. Includes only the selected definition text, no tags or metadata.

---

## Pre-Flight Checklist

Run once after cloning or after changing Python version:

```bash
# uv is installed
uv --version && echo "✓ uv found" || echo "✗ install uv: https://docs.astral.sh/uv/getting-started/installation/"

# Install dependencies and confirm
uv sync
uv run python -c "import ebooklib, lxml, wordfreq, pydantic; print('✓ deps ok')"

# Schema validates
uv run python scripts/build.py --validate-only && echo "✓ dictionary.yaml valid"

# For find_candidates only: EPUBs present
ls ~/books/bobiverse/*.epub && echo "✓ EPUBs found" || echo "✗ place Bobiverse EPUBs in ~/books/bobiverse/"
```

---

## Implementation Stories

### Story Template

Each story is one Claude session. Keep them tight.

```
#### Story X.Y — Title

**Context:** What already exists. What this story builds on. (2-3 sentences max)

**Assumptions:**
- Explicit prerequisites — files, installed tools, local data
- If an assumption is wrong, the story will fail; fix the assumption first

**Tasks:**
- Imperative, specific, one action per bullet
- Include file paths

**Out of Scope:**
- Anything that might tempt scope creep

**Acceptance Criteria:**
- [ ] Specific, verifiable checks
- [ ] At least one end-to-end output check (file exists, content is correct)
```

---

### EPIC 1 — Project Scaffold & Schema

**Epic Goal:** Repo structure in place, `dictionary.yaml` schema defined and validated, `build.py` skeleton runs without error.

---

#### Story 1.1 — Initialize Repository

**Context:** Starting from scratch.

**Assumptions:**
- `uv` is installed
- Python 3.12 is available

**Tasks:**
- Initialize project with `uv init --python 3.12`
- Add dependencies: `ebooklib`, `lxml`, `wordfreq`, `pydantic`, `pyyaml`, `pytest`
- Create directory structure per [Repository Structure](#repository-structure)
- `.gitignore` — `dist/`, `__pycache__/`, `.venv/`, `*.pyc`, `candidates.yaml`
- `dictionary.yaml` with schema comment header and 3 sample entries (one with a single definition, one with two tiers, one with 3+ tags)
- `scripts/build.py` stub — loads and validates `dictionary.yaml` via Pydantic, prints entry count, exits cleanly
- `scripts/find_candidates.py` stub — prints "not yet implemented"

**Out of Scope:** Any actual output generation, EPUB/Kindle formatting.

**Acceptance Criteria:**
- [ ] `uv sync` completes without error
- [ ] `uv run python scripts/build.py --validate-only` prints entry count and exits 0
- [ ] Introducing a schema error in `dictionary.yaml` (e.g. missing `term`) causes build to exit non-zero with a clear message
- [ ] `git status` shows `dist/` is not tracked

---

#### Story 1.2 — Pydantic Schema & Validation

**Context:** Story 1.1 complete. `build.py` loads YAML but validation is minimal.

**Assumptions:**
- `dictionary.yaml` has at least 3 entries including one multi-definition entry

**Tasks:**
- `scripts/models.py` — Pydantic models: `Definition`, `Entry`, `Dictionary`
- Validate: `safe_after_book` values within an entry must be strictly increasing
- Validate: `first_appears` must be ≤ the minimum `safe_after_book` in that entry's definitions
- Validate: `tags` list must be non-empty
- Validate: no duplicate `term` values across entries (case-insensitive)
- Update `build.py` to use models
- `tests/test_schema.py` — table-driven tests for valid and invalid entries

**Acceptance Criteria:**
- [ ] `uv run pytest tests/test_schema.py` → all pass
- [ ] Each validation rule has at least one failing-case test
- [ ] `uv run python scripts/build.py --validate-only` → passes on valid `dictionary.yaml`

---

### EPIC 1 Integration Gate

- [ ] `uv run python scripts/build.py --validate-only` → passes
- [ ] `uv run pytest` → all tests pass
- [ ] `dictionary.yaml` has at least 3 well-formed entries including one with multiple definition tiers

---

### EPIC 2 — Build Pipeline

**Epic Goal:** `build.py` produces correct CSV, EPUB, and Kindle outputs for all target book levels.

---

#### Story 2.1 — Definition Selection & CSV Output

**Context:** Epic 1 complete. Schema validates. No output generation yet.

**Assumptions:**
- `dictionary.yaml` has at least one entry with multiple definition tiers

**Tasks:**
- `scripts/build.py` — implement `select_definition(entry, target_book: int) -> str | None`
- Implement `build_csv(entries, target_book, output_path)`
- CLI: `uv run python scripts/build.py --target-book 1` writes `dist/book-1/bobiverse-book-1.csv`
- `--target-book all` sets N=999
- `tests/test_build.py` — unit tests for `select_definition` covering: single definition, multi-tier selection, term excluded (first_appears > target), all-spoilers passthrough

**Acceptance Criteria:**
- [ ] `uv run pytest tests/test_build.py` → all pass
- [ ] `uv run python scripts/build.py --target-book 1` → `dist/book-1/bobiverse-book-1.csv` exists
- [ ] CSV for book-1 does not contain any entry whose `first_appears > 1`
- [ ] For a multi-tier entry, book-1 CSV shows tier-1 definition; book-2 CSV shows tier-2 definition
- [ ] `uv run python scripts/build.py --target-book all` → all entries present with final definition tier

---

#### Story 2.2 — EPUB Dictionary Output

**Context:** Story 2.1 complete. CSV output works and verified.

**Assumptions:**
- EPUB 3 dictionary spec: entries use `epub:type="glossterm"` / `epub:type="glossdef"` semantics
- Target readers: Boox (primary), any EPUB3-compliant reader

**Tasks:**
- `templates/epub/` — `content.opf.jinja`, `dictionary.xhtml.jinja`, `toc.ncx.jinja`
- `scripts/epub_builder.py` — `build_epub(entries, target_book, output_path)` using `lxml` + template rendering
- Entries sorted alphabetically within the EPUB
- Add EPUB output to `build.py` CLI alongside CSV
- `tests/test_epub.py` — open generated EPUB with `ebooklib`, assert entry count matches CSV, assert no entries from beyond target book

**Out of Scope:** Cover image, custom fonts, styling beyond what readers require.

**Acceptance Criteria:**
- [ ] `uv run python scripts/build.py --target-book 1` → `dist/book-1/bobiverse-book-1.epub` exists and is valid ZIP
- [ ] `uv run pytest tests/test_epub.py` → all pass
- [ ] EPUB opens without errors in Boox emulator or calibre
- [ ] Entry count in EPUB matches entry count in CSV for same target book

---

#### Story 2.3 — Kindle Dictionary Output

**Context:** Story 2.2 complete. EPUB output works.

**Assumptions:**
- Kindle custom dictionary format: ZIP of OPF manifest + XHTML content file
- Sideloading via USB; no KDP publishing

**Tasks:**
- `templates/kindle/` — `content.opf.jinja`, `dictionary.html.jinja`
- `scripts/kindle_builder.py` — `build_kindle(entries, target_book, output_path)` producing a `.zip`
- Add Kindle output to `build.py` CLI
- `tests/test_kindle.py` — open ZIP, parse OPF, assert headword count matches CSV

**Acceptance Criteria:**
- [ ] `uv run python scripts/build.py --target-book 1` → `dist/book-1/bobiverse-book-1.kindle.zip` exists
- [ ] `uv run pytest tests/test_kindle.py` → all pass
- [ ] ZIP contains OPF and XHTML files, both well-formed XML

---

#### Story 2.4 — Build All Targets

**Context:** Story 2.3 complete. All three formats build for a single target.

**Tasks:**
- `build.py` — `--all` flag: iterates book numbers 1 through `max(first_appears across all entries)`, builds all three formats for each, plus `all/`
- `Makefile` with targets: `build`, `build-all`, `validate`, `test`, `clean`
- `make clean` removes `dist/`

**Acceptance Criteria:**
- [ ] `make build-all` → `dist/` contains subdirectories for each book number present in data, plus `all/`, each with three output files
- [ ] `make test` → all pytest tests pass
- [ ] `make clean && make build-all` → reproducible (output identical on repeat runs)
- [ ] Adding a new entry to `dictionary.yaml` and re-running `make build-all` → new term appears in appropriate outputs

---

### EPIC 2 Integration Gate

- [ ] `make build-all` completes without error
- [ ] `dist/` contains correct structure for all book levels
- [ ] Multi-tier entry: verify by inspection that book-N CSV/EPUB shows the correct definition tier
- [ ] `make test` → all pass
- [ ] `make clean && make build-all` → identical output (deterministic)

---

### EPIC 3 — Word Candidate Finder

**Epic Goal:** `find_candidates.py` reads local EPUBs, scores words by Bobiverse-uniqueness, and outputs a ranked draft YAML for manual review.

---

#### Story 3.1 — EPUB Text Extraction

**Context:** Epic 2 complete. `find_candidates.py` is a stub.

**Assumptions:**
- Bobiverse EPUBs are stored at `~/books/bobiverse/` (path configurable via `--epub-dir`)
- EPUBs are DRM-free

**Tasks:**
- `scripts/find_candidates.py` — `extract_text(epub_path) -> str` using `ebooklib`; strips HTML tags, normalizes whitespace
- `tokenize(text) -> list[str]` — lowercases, strips punctuation, filters tokens under 3 chars
- Accept `--epub-dir` CLI arg (default `~/books/bobiverse/`)
- Print token count per file on load

**Out of Scope:** Scoring, filtering against existing dictionary, output file.

**Acceptance Criteria:**
- [ ] `uv run python scripts/find_candidates.py --epub-dir ~/books/bobiverse/` → prints per-file token counts, exits 0
- [ ] Extracted text visually contains prose (spot-check a known passage)
- [ ] Tokens are lowercase, no punctuation

---

#### Story 3.2 — Scoring & Candidate Output

**Context:** Story 3.1 complete. Text extraction works.

**Assumptions:**
- `wordfreq` is installed (from Epic 1)
- `dictionary.yaml` is present and valid

**Tasks:**
- `score_candidates(tokens, existing_terms: set[str]) -> list[dict]`
  - Count term frequency in corpus
  - Fetch English baseline frequency via `wordfreq.word_frequency(word, 'en')`
  - Score = `corpus_freq / (baseline_freq + epsilon)` — high score means common in Bobiverse, rare in English
  - Filter out terms already in `dictionary.yaml` (case-insensitive)
  - Filter out terms that are purely numeric or single characters
- `--top N` CLI arg (default 50)
- Output `candidates.yaml` — list of dicts with `term`, `score`, `corpus_count`, and blank `definitions: []` stub
- `candidates.yaml` is gitignored

**Acceptance Criteria:**
- [ ] `uv run python scripts/find_candidates.py --top 50` → `candidates.yaml` written with 50 entries
- [ ] No entry in `candidates.yaml` has a `term` already in `dictionary.yaml`
- [ ] Top results are visually plausible Bobiverse-specific terms (replicant names, alien names, acronyms) — spot-check manually
- [ ] `candidates.yaml` is not tracked by git

---

### EPIC 3 Integration Gate

- [ ] `uv run python scripts/find_candidates.py --top 100` → `candidates.yaml` with 100 entries
- [ ] All entries have blank `definitions` stubs ready to fill in
- [ ] No overlap with existing `dictionary.yaml` terms
- [ ] Re-running after adding entries to `dictionary.yaml` → previously-added terms no longer appear in candidates

---

### EPIC 4 — Content & Distribution

**Epic Goal:** `dictionary.yaml` has meaningful coverage (≥ 50 entries). Distribution page on personal site lists all download files.

---

#### Story 4.1 — Initial Content Pass

**Context:** Build pipeline and candidate finder complete.

**Tasks:**
- Run `find_candidates.py --top 100`, review output, fill in definitions for top candidates
- Aim for ≥ 50 entries with real definitions in `dictionary.yaml`
- Ensure at least 10 entries have multi-tier definitions (book 1 vs book 2+)
- Run `make build-all` and verify outputs

**Out of Scope:** Perfect coverage; this is a first pass.

**Acceptance Criteria:**
- [ ] `dictionary.yaml` has ≥ 50 entries with non-empty definitions
- [ ] ≥ 10 entries have at least 2 definition tiers
- [ ] `make build-all` → all outputs produced without error
- [ ] Spot-check: open `dist/book-1/bobiverse-book-1.epub` in calibre; at least 10 entries visible

---

#### Story 4.2 — Distribution Page on Personal Site

**Context:** Story 4.1 complete. `dist/` has populated outputs.

**Assumptions:**
- Personal site has a Projects page or equivalent
- Site is static or supports uploading files to `public/`

**Tasks:**
- Copy `dist/` outputs to `public/bobiverse-dictionary/` on personal site (or reference via GitHub release assets)
- Add a `manifest.json` generated by `build.py --manifest` listing all available files with book number, format, and filename — personal site reads this to render download buttons dynamically
- Add `make manifest` target
- Document the publish workflow in this README under a "Publishing" section

**Acceptance Criteria:**
- [ ] `make manifest` → `dist/manifest.json` lists all output files
- [ ] Download links on personal site resolve to correct files
- [ ] Spoiler warning visible on distribution page before any download links

---

### EPIC 4 Integration Gate

- [ ] `make build-all && make manifest` → complete dist tree with manifest
- [ ] All download links on site resolve correctly
- [ ] At least one full download tested: file opens correctly in target reader (Boox or Kindle)

---

## Definition of Done

A story is complete when:

- [ ] All acceptance criteria pass
- [ ] `make test` still passes after the change
- [ ] New non-trivial logic has unit tests
- [ ] `dictionary.yaml` remains valid (`make validate` passes)
- [ ] `dist/` outputs are reproducible (`make clean && make build-all` produces identical results)
- [ ] Epic integration gate passes before moving to next epic
