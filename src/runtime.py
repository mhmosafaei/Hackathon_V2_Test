"""Runtime identity and fail-closed pre-dispatch checks for Streamlit.

The browser can remain connected to a long-lived Streamlit worker while source
files change.  A live acceptance run must therefore prove the *loaded*
modules, not merely the files on disk, implement the current safety contract.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
import sys
from typing import Any


RESPONSE_PARSER_VERSION = "candidate-response-parser-v2"
RUNTIME_CONTRACT_VERSION = "live-acceptance-runtime-v1"
_STARTED_AT = datetime.now(timezone.utc).isoformat()
_ROOT = Path(__file__).resolve().parents[1]
_FINGERPRINT_FILES = (
    "src/documents/extractor.py",
    "src/documents/openai_transport.py",
    "src/documents/live_budget.py",
    "src/documents/ai_first.py",
    "src/intelligence/service.py",
    "src/permit/upload_flow.py",
    "src/intelligence/deterministic.py",
)


def build_fingerprint() -> str:
    """Hash the exact safety-critical files, excluding credentials and data."""
    digest = sha256()
    for relative in _FINGERPRINT_FILES:
        path = _ROOT / relative
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


_LOADED_BUILD_FINGERPRINT = build_fingerprint()


def runtime_metadata() -> dict[str, Any]:
    """Safe runtime diagnostics suitable for the local Audit view."""
    return {
        "runtime_contract_version": RUNTIME_CONTRACT_VERSION,
        "build_fingerprint": build_fingerprint(),
        "loaded_build_fingerprint": _LOADED_BUILD_FINGERPRINT,
        "process_id": os.getpid(),
        "python_interpreter": sys.executable,
        "source_directory": str(_ROOT),
        "application_start_time_utc": _STARTED_AT,
        "active_model": os.environ.get("OPENAI_MODEL", "NOT_CONFIGURED"),
        "response_parser_version": RESPONSE_PARSER_VERSION,
    }


def pre_dispatch_runtime_check() -> dict[str, Any]:
    """Prove current loaded modules meet the live acceptance safety contract.

    This intentionally checks imported module capabilities.  It detects the
    failure mode where a Streamlit worker keeps an old imported parser although
    files on disk have been updated.
    """
    from src.documents import ai_first, extractor, live_budget, openai_transport
    from src.intelligence import service

    issues: list[str] = []
    checks = {
        "loaded_source_matches_disk": _LOADED_BUILD_FINGERPRINT == build_fingerprint(),
        "candidate_parser_version": getattr(extractor, "RESPONSE_PARSER_VERSION", None) == RESPONSE_PARSER_VERSION,
        "candidate_finish_reason_before_parse": bool(getattr(extractor, "candidate_response_capabilities", lambda: {})().get("finish_reason_before_json")),
        "candidate_response_metadata": bool(getattr(extractor, "candidate_response_capabilities", lambda: {})().get("response_metadata")),
        "candidate_schema_validation": bool(getattr(extractor, "candidate_response_capabilities", lambda: {})().get("schema_validation")),
        "direct_transport": getattr(openai_transport, "TRANSPORT_VERSION", None) == "direct-https-v1",
        "five_request_budget_cap": bool(getattr(live_budget, "budget_capabilities", lambda: {})().get("request_cap")),
        "cost_reservation": bool(getattr(live_budget, "budget_capabilities", lambda: {})().get("cost_reservation")),
        "failure_stops_dispatch": bool(getattr(live_budget, "budget_capabilities", lambda: {})().get("unknown_outcome_halts")),
        "no_automatic_retry": bool(getattr(live_budget, "budget_capabilities", lambda: {})().get("no_automatic_retry")),
        "orchestration_fail_stop": bool(getattr(ai_first, "orchestration_capabilities", lambda: {})().get("failed_candidate_halts_later_batches")),
        "intelligence_structured_json": bool(getattr(service, "intelligence_transport_capabilities", lambda: {})().get("structured_json")),
        "intelligence_response_metadata": bool(getattr(service, "intelligence_transport_capabilities", lambda: {})().get("response_metadata")),
    }
    for name, passed in checks.items():
        if not passed:
            issues.append(name)
    result = {**runtime_metadata(), "checks": checks, "ready": not issues, "issues": issues}
    if issues:
        raise RuntimeError("STALE_RUNTIME: live dispatch is blocked; restart PermitPulse worker (" + ", ".join(issues) + ")")
    return result
