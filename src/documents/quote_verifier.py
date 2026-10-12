"""Deterministic source-quote verification; failed quotes remain review-required."""
import re
import unicodedata
from dataclasses import dataclass
from .pdf_parser import PdfPage

@dataclass(frozen=True)
class QuoteMatch:
    verified: bool
    page_number: int | None
    detail: str

def normalise(text: str) -> str:
    return normalise_variant(text, dehyphenate=True)

def normalise_variant(text: str, dehyphenate: bool) -> str:
    value = unicodedata.normalize("NFKC", text)
    value = value.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    value = re.sub(r"[\u2010-\u2015]", "-", value)
    if dehyphenate:
        value = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", value)
    else:
        value = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1-\2", value)
    value = re.sub(r"[•●▪◦]", " ", value)
    return re.sub(r"\s+", " ", value).strip().casefold()

def verify_quote(source_text: str, pages: list[PdfPage], page_number: int) -> QuoteMatch:
    quotes = {normalise_variant(source_text, True), normalise_variant(source_text, False)}
    candidate_numbers = {page_number - 1, page_number, page_number + 1}
    for page in pages:
        page_forms = {normalise_variant(page.text, True), normalise_variant(page.text, False)}
        if page.page_number in candidate_numbers and any(quote in text for quote in quotes for text in page_forms):
            return QuoteMatch(True, page.page_number, "exact normalized match")
    return QuoteMatch(False, None, "quote not found on claimed or adjacent physical page")
