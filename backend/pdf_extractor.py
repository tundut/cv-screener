from io import BytesIO

from PyPDF2 import PdfReader


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from a text-based PDF and normalize blank lines."""
    if not pdf_bytes:
        raise ValueError("PDF content is empty")

    reader = PdfReader(BytesIO(pdf_bytes))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    text = "\n\n".join(page for page in pages if page)
    if not text:
        raise ValueError("No selectable text found in PDF")
    return text