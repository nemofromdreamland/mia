"""Write a minimal text PDF by hand (test-only, no extra dependency).

One page per string; each line becomes a text line in Helvetica (WinAnsi, so
Portuguese accents survive). Offsets in the xref table are computed exactly.
"""

from pathlib import Path


def _escape(line: str) -> bytes:
    raw = line.encode("cp1252")
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _content_stream(text: str) -> bytes:
    parts = [b"BT /F1 11 Tf 14 TL 50 780 Td"]
    for line in text.splitlines():
        parts.append(b"(" + _escape(line) + b") Tj T*")
    parts.append(b"ET")
    return b"\n".join(parts)


def make_text_pdf(pages: list[str]) -> bytes:
    n = len(pages)
    font_id = 3 + 2 * n
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n))
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode(),
    ]
    for i, text in enumerate(pages):
        content_id = 4 + 2 * i
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
            f"/Contents {content_id} 0 R >>".encode()
        )
        stream = _content_stream(text)
        objects.append(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        )
    objects.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    )

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    trailer = f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
    out += f"{trailer}startxref\n{xref_at}\n%%EOF\n".encode()
    return bytes(out)


def write_text_pdf(path: Path, pages: list[str]) -> Path:
    path.write_bytes(make_text_pdf(pages))
    return path
