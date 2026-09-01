import pymupdf as fitz


def extract_text_from_pdf(pdf_path) -> str:
    doc = fitz.open(pdf_path)
    try:
        return "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


def extract_intro_text(pdf_path, max_chars: int = 2000) -> str:
    doc = fitz.open(pdf_path)
    buf = ""
    try:
        for page in doc:
            buf += page.get_text()
            if len(buf) > max_chars:
                break
    finally:
        doc.close()
    return buf[:max_chars]


def chunk_text(text: str, min_len: int = 300, max_len: int = 1500) -> list[str]:
    """Paragraph-based chunking with merge rules (ported from the notebook)."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buffer = ""

    for para in paragraphs:
        if len(buffer) + len(para) < max_len:
            buffer += " " + para
        else:
            if len(buffer) > min_len:
                chunks.append(buffer.strip())
            buffer = para

    if len(buffer) > min_len:
        chunks.append(buffer.strip())

    return chunks
