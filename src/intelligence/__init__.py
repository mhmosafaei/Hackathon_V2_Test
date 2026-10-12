"""Permit intelligence orchestration built on the existing evidence pipeline.

This package deliberately has no import-time OpenAI client or network side
effects.  Callers inject a transport at the edge, which makes every stage
resumable and testable with source-backed fixtures.
"""

from .service import build_intelligence_analysis, run_intelligence_pipeline

__all__ = ["build_intelligence_analysis", "run_intelligence_pipeline"]
