"""Exact, read-only restoration of persisted simple-permit analyses."""
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from src.environmental.service import map_requirements
from src.permit.simple_analysis import apply_source_verification


_PAGE_MARKER = re.compile(r'^--- PAGE (\d+) ---\s*$', re.MULTILINE)


@dataclass(frozen=True)
class _PersistedPage:
    page_number: int
    text: str


def _load_persisted_pages(path: Path) -> list[_PersistedPage] | None:
    """Reconstruct pages from the immutable, page-marked analysis input."""
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding='utf-8')
    except (OSError, UnicodeError):
        return None
    markers = list(_PAGE_MARKER.finditer(text))
    if not markers or markers[0].start() != 0:
        return None
    pages = []
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        page_text = text[marker.end():end]
        page_number = int(marker.group(1))
        if index and page_number <= pages[-1].page_number:
            return None
        pages.append(_PersistedPage(page_number=page_number, text=page_text.strip()))
    return pages or None


def load_persisted_analysis(root: Path, document_sha256: str, analysis_run_id: str) -> dict:
    """Load one exact persisted run; never select by filename or recency."""
    if not re.fullmatch(r'[0-9a-fA-F]{64}', document_sha256) or not re.fullmatch(r'[0-9a-fA-F]{32,64}', analysis_run_id):
        raise ValueError('INVALID_ANALYSIS_REFERENCE')
    folder = root / 'cache' / 'simple_analysis' / document_sha256.lower() / analysis_run_id.lower()
    manifest_path, analysis_path = folder / 'manifest.json', folder / 'analysis.json'
    if not manifest_path.is_file() or not analysis_path.is_file():
        raise FileNotFoundError('PERSISTED_ANALYSIS_NOT_FOUND')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if not isinstance(manifest, dict):
        raise ValueError('MALFORMED_PERSISTED_MANIFEST')
    if manifest.get('document_sha256', '').lower() != document_sha256.lower():
        raise ValueError('DOCUMENT_HASH_MISMATCH')
    if manifest.get('run_id', '').lower() != analysis_run_id.lower():
        raise ValueError('ANALYSIS_RUN_ID_MISMATCH')
    analysis = json.loads(analysis_path.read_text(encoding='utf-8'))
    if not isinstance(analysis, dict):
        raise ValueError('MALFORMED_PERSISTED_ANALYSIS')
    if analysis.get('analysis_id') != analysis_run_id:
        raise ValueError('ANALYSIS_ARTIFACT_ID_MISMATCH')
    # Work on a deep in-memory copy: reconciliation updates nested records,
    # while the persisted JSON remains strictly read-only.
    restored = deepcopy(analysis)
    restored['document_sha256'] = document_sha256.lower()
    restored['restored_from_persistence'] = True
    restored['restoration_status'] = 'COMPLETE' if restored.get('environmental_extraction', {}).get('complete') else 'INCOMPLETE'
    restored['missing_count'] = restored.get('environmental_extraction', {}).get('missing_count', 0)
    # Reconcile source attribution and verification from immutable page-marked
    # input before rebuilding derived routing/mapping. Missing or malformed
    # input fails closed by leaving persisted verification fields unchanged.
    pages = _load_persisted_pages(folder / 'input.txt')
    if pages is not None:
        apply_source_verification(restored, pages, reset_review_state=False)
        restored['restoration_source_verification'] = 'RECONCILED_FROM_PERSISTED_INPUT'
    else:
        restored['restoration_source_verification'] = 'SOURCE_TEXT_UNAVAILABLE'
    # Rebuild only derived routing/mapping in memory.  Raw model output, audit
    # fields and persisted analysis.json remain immutable.
    restored['environmental_mapping'] = map_requirements(restored)
    return restored
