"""Keyword matching with adjacent-page retention for split clauses."""
import re
from .pdf_parser import PdfPage
def select_relevant_pages(pages: list[PdfPage], keywords: list[str]) -> list[PdfPage]:
    terms = [term.casefold() for term in keywords]
    hits = {page.page_number for page in pages if any(term in page.text.casefold() for term in terms)}
    included = hits | {number - 1 for number in hits} | {number + 1 for number in hits}
    return [page for page in pages if page.page_number in included]

def select_pages_with_numbered_conditions(pages: list[PdfPage]) -> list[PdfPage]:
    """Prefer the explicit conditions section; avoid numbered particulars/coordinates."""
    section_start=next((p.page_number for p in pages if re.search(r'(?i)\bpart\s*2\s*[-–]?\s*conditions\b',p.text)),None)
    if section_start is not None:
        section_end=next((p.page_number for p in pages if p.page_number>section_start and re.search(r'(?im)^\s*notes\s*$',p.text)),len(pages)+1)
        return [p for p in pages if section_start<=p.page_number<section_end]
    # Environmental permits commonly use a standalone Conditions heading followed
    # by hierarchical clauses, then binding Schedules 1-5.  Require both signals
    # so an introductory reference to "conditions" cannot start extraction.
    standalone=next((p.page_number for p in pages if re.search(r'(?im)^\s*conditions\s*$',p.text)
                     and re.search(r'(?m)^\s*\d+(?:\.\d+){1,}\s*$',p.text)),None)
    if standalone is not None:
        end=next((p.page_number for p in pages if p.page_number>standalone and re.search(r'(?im)^\s*schedule\s*[67]\b',p.text)),len(pages)+1)
        return [p for p in pages if standalone<=p.page_number<end]
    """Fallback for licences without a labelled conditions section."""
    starts={p.page_number for p in pages if re.search(r'(?m)^\s*\d{1,2}\.\s+',p.text)}
    selected=starts | {n+1 for n in starts}
    return [p for p in pages if p.page_number in selected]
