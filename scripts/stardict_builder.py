"""Build StarDict dictionary ZIP from entries."""

import gzip
import io
import struct
import zipfile
from pathlib import Path

from scripts.models import Entry, select_definition


def generate_ifo(word_count: int, idx_filesize: int, bookname: str = "Bobiverse Dictionary") -> str:
    lines = [
        "StarDict's dict ifo file",
        "version=2.4.2",
        f"wordcount={word_count}",
        f"idxfilesize={idx_filesize}",
        f"bookname={bookname}",
        "sametypesequence=m",
    ]
    return "\n".join(lines) + "\n"


def generate_idx(headwords_with_offsets: list[tuple[str, int, int]]) -> bytes:
    buf = io.BytesIO()
    for headword, offset, size in headwords_with_offsets:
        buf.write(headword.encode("utf-8"))
        buf.write(b"\x00")
        buf.write(struct.pack(">II", offset, size))
    return buf.getvalue()


def generate_dict(definitions: list[str]) -> bytes:
    raw = "".join(definitions).encode("utf-8")
    return gzip.compress(raw)


def build_stardict(entries: list[Entry], target_book: int, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = sorted(
        (
            {"term": e.term, "definition": text}
            for e in entries
            if (text := select_definition(e, target_book)) is not None
        ),
        key=lambda r: r["term"],
    )

    offset = 0
    headwords_with_offsets: list[tuple[str, int, int]] = []
    definitions: list[str] = []
    for row in rows:
        size = len(row["definition"].encode("utf-8"))
        headwords_with_offsets.append((row["term"], offset, size))
        definitions.append(row["definition"])
        offset += size

    idx_bytes = generate_idx(headwords_with_offsets)
    dict_dz_bytes = generate_dict(definitions)
    ifo_str = generate_ifo(len(rows), len(idx_bytes))

    # Derive inner stem: "bobiverse-book-1.stardict.zip" → "bobiverse-book-1"
    inner_stem = output_path.stem.removesuffix(".stardict")

    _EPOCH = (1980, 1, 1, 0, 0, 0)

    def _zi(name: str) -> zipfile.ZipInfo:
        zi = zipfile.ZipInfo(name, date_time=_EPOCH)
        zi.compress_type = zipfile.ZIP_STORED
        return zi

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr(_zi(f"{inner_stem}.ifo"), ifo_str.encode("utf-8"))
        zf.writestr(_zi(f"{inner_stem}.idx"), idx_bytes)
        zf.writestr(_zi(f"{inner_stem}.dict.dz"), dict_dz_bytes)
