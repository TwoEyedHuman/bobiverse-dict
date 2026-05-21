"""Build EPUB 3 dictionary from entries."""

import zipfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from scripts.models import Entry, select_definition

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "epub"

_CONTAINER_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf"
              media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""


def build_epub(entries: list[Entry], target_book: int, output_path: Path) -> None:
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
        "modified": "1980-01-01T00:00:00Z",
    }

    content_opf = env.get_template("content.opf.jinja").render(**ctx)
    dictionary_xhtml = env.get_template("dictionary.xhtml.jinja").render(**ctx)
    toc_ncx = env.get_template("toc.ncx.jinja").render(**ctx)

    _EPOCH = (1980, 1, 1, 0, 0, 0)

    def _zi(name: str, compress_type: int = zipfile.ZIP_DEFLATED) -> zipfile.ZipInfo:
        zi = zipfile.ZipInfo(name, date_time=_EPOCH)
        zi.compress_type = compress_type
        return zi

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # mimetype must be first entry, uncompressed, no extra fields
        zf.writestr(_zi("mimetype", zipfile.ZIP_STORED), "application/epub+zip")
        zf.writestr(_zi("META-INF/container.xml"), _CONTAINER_XML)
        zf.writestr(_zi("OEBPS/content.opf"), content_opf)
        zf.writestr(_zi("OEBPS/dictionary.xhtml"), dictionary_xhtml)
        zf.writestr(_zi("OEBPS/toc.ncx"), toc_ncx)
