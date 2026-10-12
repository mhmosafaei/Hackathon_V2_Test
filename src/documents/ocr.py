"""OCR contract only; no OCR engine is bundled in this MVP stage."""
from typing import Protocol
from .pdf_parser import PdfPage
class OcrProvider(Protocol):
    def extract_pages(self, file_path: str) -> list[PdfPage]: ...
