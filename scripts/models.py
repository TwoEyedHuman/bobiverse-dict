"""Pydantic models for dictionary.yaml."""

from pydantic import BaseModel, field_validator, model_validator


class Definition(BaseModel):
    safe_after_book: int
    text: str


class Entry(BaseModel):
    term: str
    first_appears: int
    tags: list[str]
    definitions: list[Definition]

    @field_validator("tags")
    @classmethod
    def tags_non_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("tags must be non-empty")
        return v

    @model_validator(mode="after")
    def validate_definitions_order_and_first_appears(self) -> "Entry":
        books = [d.safe_after_book for d in self.definitions]
        for i in range(1, len(books)):
            if books[i] <= books[i - 1]:
                raise ValueError(
                    f"safe_after_book must be strictly increasing; got {books}"
                )
        if books and self.first_appears > min(books):
            raise ValueError(
                f"first_appears ({self.first_appears}) must be <= "
                f"minimum safe_after_book ({min(books)})"
            )
        return self


def select_definition(entry: "Entry", target_book: int) -> str | None:
    if entry.first_appears > target_book:
        return None
    safe = [d for d in entry.definitions if d.safe_after_book <= target_book]
    if not safe:
        return None
    return safe[-1].text.strip()


class Dictionary(BaseModel):
    entries: list[Entry]

    @model_validator(mode="after")
    def validate_no_duplicate_terms(self) -> "Dictionary":
        seen: set[str] = set()
        for entry in self.entries:
            key = entry.term.lower()
            if key in seen:
                raise ValueError(f"duplicate term (case-insensitive): {entry.term!r}")
            seen.add(key)
        return self
