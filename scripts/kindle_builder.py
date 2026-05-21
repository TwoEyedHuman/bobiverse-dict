"""Build Kindle dictionary ZIP from entries."""

import zipfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from scripts.models import Entry, select_definition

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "kindle"


def build_kindle(entries: list[Entry], target_book: int, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = sorted(
        (
            {"term": e.term, "definition": text}
            for e in entries
            if (text := select_definition(e, target_book)) is not None
        ),
        key=lambda r: r["term"].lower(),
    )

    env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=True)

    target_book_label = "All" if target_book == 999 else str(target_book)
    ctx = {
        "entries": rows,
        "target_book": target_book,
        "target_book_label": target_book_label,
    }

    content_opf = env.get_template("content.opf.jinja").render(**ctx)
    dictionary_html = env.get_template("dictionary.html.jinja").render(**ctx)

    _EPOCH = (1980, 1, 1, 0, 0, 0)

    def _zi(name: str) -> zipfile.ZipInfo:
        zi = zipfile.ZipInfo(name, date_time=_EPOCH)
        zi.compress_type = zipfile.ZIP_DEFLATED
        return zi

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(_zi("content.opf"), content_opf)
        zf.writestr(_zi("dictionary.html"), dictionary_html)
