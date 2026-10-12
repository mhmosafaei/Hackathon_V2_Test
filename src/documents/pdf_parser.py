"""Physical-page PDF extraction with a conservative text-layer health check."""
from dataclasses import dataclass
from pathlib import Path
import pymupdf

@dataclass(frozen=True)
class PdfPage:
    page_number: int
    text: str
    printed_label: str | None = None

@dataclass(frozen=True)
class ParsedPdf:
    document_id: str
    pages: list[PdfPage]
    needs_ocr: bool

def parse_pdf(path: str | Path, minimum_chars: int = 40) -> ParsedPdf:
    source = Path(path)
    with pymupdf.open(source) as document:
        pages = [PdfPage(i + 1, page.get_text("text"), page.get_label() or None)
                 for i, page in enumerate(document)]
    counts = sorted(len(page.text.strip()) for page in pages)
    median = counts[len(counts) // 2] if counts else 0
    empty = sum(count == 0 for count in counts)
    return ParsedPdf(source.stem, pages, median < minimum_chars or empty > len(pages) * .25)

def parse_pdf_bytes(content: bytes, document_id: str = "uploaded_contract", minimum_chars: int = 40) -> ParsedPdf:
    """Parse an uploaded PDF without persisting its bytes in the source tree."""
    with pymupdf.open(stream=content, filetype="pdf") as document:
        pages=[PdfPage(i+1,page.get_text("text"),page.get_label() or None) for i,page in enumerate(document)]
    counts=sorted(len(page.text.strip()) for page in pages); median=counts[len(counts)//2] if counts else 0
    return ParsedPdf(document_id,pages,median<minimum_chars or sum(count==0 for count in counts)>len(pages)*.25)
