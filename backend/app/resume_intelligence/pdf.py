from __future__ import annotations

from io import BytesIO
import textwrap


_PAGE_WIDTH = 612
_PAGE_HEIGHT = 792
_MARGIN_LEFT = 54
_MARGIN_TOP = 72
_LINE_HEIGHT = 15
_MAX_CHARS_PER_LINE = 92
_LINES_PER_PAGE = 44


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap_lines(text: str) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines():
        normalized = paragraph.rstrip()
        if not normalized:
            lines.append("")
            continue
        wrapped = textwrap.wrap(
            normalized,
            width=_MAX_CHARS_PER_LINE,
            break_long_words=False,
            break_on_hyphens=False,
        )
        lines.extend(wrapped or [""])
    return lines


def _page_chunks(lines: list[str]) -> list[list[str]]:
    if not lines:
        return [[]]
    return [lines[index : index + _LINES_PER_PAGE] for index in range(0, len(lines), _LINES_PER_PAGE)]


def _page_stream(lines: list[str]) -> bytes:
    commands = ["BT", "/F1 11 Tf", f"1 0 0 1 {_MARGIN_LEFT} {_PAGE_HEIGHT - _MARGIN_TOP} Tm", f"{_LINE_HEIGHT} TL"]
    for index, line in enumerate(lines):
        if index > 0:
            commands.append("T*")
        commands.append(f"({_pdf_escape(line)}) Tj")
    commands.append("ET")
    return "\n".join(commands).encode("latin-1", errors="replace")


def generate_resume_pdf_bytes(text: str) -> bytes:
    lines = _wrap_lines(text)
    pages = _page_chunks(lines)

    objects: list[bytes] = []

    def add_object(payload: bytes) -> int:
        objects.append(payload)
        return len(objects)

    catalog_id = add_object(b"<< /Type /Catalog /Pages 2 0 R >>")
    pages_placeholder_id = add_object(b"<< >>")
    font_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_ids: list[int] = []
    content_ids: list[int] = []
    for page_lines in pages:
        stream = _page_stream(page_lines)
        content_id = add_object(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")
        page_id = add_object(
            (
                f"<< /Type /Page /Parent {pages_placeholder_id} 0 R /MediaBox [0 0 {_PAGE_WIDTH} {_PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
            ).encode("ascii")
        )
        content_ids.append(content_id)
        page_ids.append(page_id)

    pages_object = (
        f"<< /Type /Pages /Count {len(page_ids)} /Kids [{' '.join(f'{page_id} 0 R' for page_id in page_ids)}] >>"
    ).encode("ascii")
    objects[pages_placeholder_id - 1] = pages_object
    objects[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_placeholder_id} 0 R >>".encode("ascii")

    buffer = BytesIO()
    buffer.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, payload in enumerate(objects, start=1):
        offsets.append(buffer.tell())
        buffer.write(f"{index} 0 obj\n".encode("ascii"))
        buffer.write(payload)
        buffer.write(b"\nendobj\n")
    xref_offset = buffer.tell()
    buffer.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    buffer.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    buffer.write(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_offset}\n%%EOF"
        ).encode("ascii")
    )
    return buffer.getvalue()
