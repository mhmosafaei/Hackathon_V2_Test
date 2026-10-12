"""Streamlit rendering for the canonical PermitPulse Intelligence contract."""
from __future__ import annotations

import json
from pathlib import Path
from collections import Counter

import plotly.express as px

from src.documents.exports import csv_bytes, excel_bytes, export_json
from src.runtime import runtime_metadata


def _counts(rows: list[dict], key: str, fallback: str = "UNKNOWN") -> list[dict]:
    return [{"label": label or fallback, "count": count} for label, count in Counter(row.get(key) or fallback for row in rows).items()]


def _pie(st, title: str, rows: list[dict], key: str, empty: str) -> None:
    values = _counts(rows, key)
    if not values:
        st.info(empty)
        return
    st.plotly_chart(px.pie(values, names="label", values="count", title=title, hole=.48), width="stretch")


def _bar(st, title: str, values: list[dict], empty: str) -> None:
    if not values:
        st.info(empty)
        return
    st.plotly_chart(px.bar(values, x="label", y="count", title=title), width="stretch")


def _requirements(analysis: dict) -> list[dict]:
    by_id = {item["requirement_id"]: item for item in analysis.get("requirements", [])}
    assessments = {item["requirement_id"]: item for item in analysis.get("operational_assessments", [])}
    rows = []
    for requirement_id, item in by_id.items():
        assessment = assessments.get(requirement_id, {})
        rows.append({**item, "primary_role": assessment.get("primary_role", "UNRESOLVED")})
    return rows


def _evidence_readiness(analysis: dict) -> list[dict]:
    """Join source-derived needs to deterministic feasibility outcomes.

    A missing feasibility result remains explicitly unanalysed; it is never
    converted into a favourable availability status for charting.
    """
    feasibility = {
        item.get("data_need_id"): item
        for item in analysis.get("data_feasibility", [])
        if item.get("data_need_id")
    }
    rows = []
    for need in analysis.get("data_needs", []):
        assessed = feasibility.get(need.get("data_need_id"), {})
        rows.append({
            **need,
            "readiness": assessed.get("status", assessed.get("suitability_status", "DATA_NOT_YET_ANALYZED")),
        })
    return rows


def render_intelligence_dashboard(st, analysis_path: Path) -> None:
    """Render a document-scoped UI from a persisted canonical artifact only."""
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    local_audit_path = analysis_path.parent / 'normalization_audit.json'
    local_audit = json.loads(local_audit_path.read_text(encoding='utf-8')) if local_audit_path.exists() else {}
    evidence_mapping = {row['requirement_id']: row for row in local_audit.get('evidence_mapping', [])}
    document = analysis["document"]
    coverage = analysis["coverage"]
    requirements = _requirements(analysis)
    requirements = [{**row, **evidence_mapping.get(row['requirement_id'], {})} for row in requirements]
    readiness = _evidence_readiness(analysis)
    stage_runs = analysis["stage_runs"]
    status = "REVIEW READY" if all(item["status"] in {"COMPLETED", "NOT_APPLICABLE"} for item in stage_runs) else "PARTIAL"
    st.markdown("### Permit Intelligence · Document Analysis")
    left, right = st.columns([4, 1])
    left.caption(f"{document['title']} · {document['physical_pages']} physical pages · run {analysis['analysis_id'][:16]}")
    right.metric("Status", status)
    stages = {item["stage"]: item for item in stage_runs}
    labels = [("Extraction", "DOCUMENT_EXTRACTION"), ("Operations", "OPERATIONAL_RELEVANCE"),
              ("Environment", "ENVIRONMENTAL_MAPPING"), ("Data check", "DATA_FEASIBILITY")]
    stage_columns = st.columns(len(labels))
    for column, (label, key) in zip(stage_columns, labels):
        item = stages.get(key, {"status": "NOT_STARTED", "batches_completed": 0, "batches_total": 0})
        column.caption(label)
        column.write(f"**{item['status']}**")
        column.caption('Local deterministic mapping' if item.get('processor') == 'DETERMINISTIC' else f"{item.get('batches_completed', 0)}/{item.get('batches_total', 0)} batches")

    tabs = st.tabs(["Overview", "Requirements", "Environmental Intelligence", "Work Windows", "Audit & Exports"])
    with tabs[0]:
        if local_audit:
            st.caption('Deterministic candidate normalization · no additional intelligence LLM calls · all records require human review.')
            st.subheader('Source-condition coverage')
            st.dataframe(local_audit.get('condition_groups', []), hide_index=True, width='stretch')
            gaps = [g for g in local_audit.get('condition_groups', []) if g['status'] != 'CAPTURED']
            if gaps:
                st.warning('Source coverage gaps: ' + ', '.join(f"{g['condition_id']} ({g['status']})" for g in gaps) + '. Source-span matching is not proof of complete legal interpretation.')
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Physical pages / processed", f"{document['physical_pages']} / {coverage['processed_pages']}")
        c2.metric("Numbered source conditions", len(coverage['numbered_conditions']))
        c3.metric("AI requirements", len(requirements))
        c4.metric("Quote-verified requirements", f"{sum(r['source_verification'] == 'SOURCE_VERIFIED' for r in requirements)}/{len(requirements)}")
        c5.metric("Source-inventory records", len(analysis.get("source_inventory", [])))
        c6.metric("Unresolved / failed verification", sum(r['source_verification'] != 'SOURCE_VERIFIED' for r in requirements) + sum(flag["status"] == "OPEN" for flag in analysis["review_flags"]))
        p1, p2, p3 = st.columns(3)
        with p1: _pie(st, "Authority", requirements, "authority_status", "No requirements available.")
        with p2: _pie(st, "Primary operational role", requirements, "primary_role", "Operational classification is unavailable.")
        with p3: _pie(st, "Environmental evidence readiness", readiness, "readiness", "DATA NOT YET ANALYZED — no permit-derived environmental data needs.")
        lifecycle = Counter(phase for row in requirements for phase in row.get("lifecycle_phases", []))
        domains = Counter(need["domain"] for need in analysis["data_needs"])
        b1, b2 = st.columns(2)
        with b1: _bar(st, "Work lifecycle (overlapping requirement counts)", [{"label": k, "count": v} for k, v in lifecycle.items()], "No lifecycle classifications.")
        with b2: _bar(st, "Environmental domains (distinct data needs)", [{"label": k, "count": v} for k, v in domains.items()], "No environmental data needs.")

    with tabs[1]:
        query = st.text_input("Search requirements", key=f"intelligence_query_{analysis['analysis_id']}").strip().lower()
        authority = st.multiselect("Authority", sorted({r["authority_status"] for r in requirements}), default=sorted({r["authority_status"] for r in requirements}), key=f"intelligence_authority_{analysis['analysis_id']}")
        roles = st.multiselect("Operational relevance", sorted({r["primary_role"] for r in requirements}), default=sorted({r["primary_role"] for r in requirements}), key=f"intelligence_role_{analysis['analysis_id']}")
        verification = st.multiselect("Source verification", sorted({r["source_verification"] for r in requirements}), default=sorted({r["source_verification"] for r in requirements}), key=f"intelligence_verification_{analysis['analysis_id']}")
        reviews = st.multiselect("Review status", sorted({r["human_review"] for r in requirements}), default=sorted({r["human_review"] for r in requirements}), key=f"intelligence_review_{analysis['analysis_id']}")
        phases = sorted({phase for r in requirements for phase in r.get("lifecycle_phases", [])})
        lifecycle = st.multiselect("Lifecycle stage", phases, default=phases, key=f"intelligence_lifecycle_{analysis['analysis_id']}")
        pages = st.multiselect("Physical pages", sorted({r["page_start"] for r in requirements}), default=sorted({r["page_start"] for r in requirements}), key=f"intelligence_pages_{analysis['analysis_id']}")
        filtered = [r for r in requirements if r["authority_status"] in authority and r["primary_role"] in roles and r["source_verification"] in verification and r["human_review"] in reviews and r["page_start"] in pages and (not lifecycle or any(phase in lifecycle for phase in r.get("lifecycle_phases", []))) and (not query or query in (r["exact_quote"] + " " + r["summary"]).lower())]
        st.dataframe([{"Condition": r["parent_condition_id"], "Requirement": r["summary"], "Authority": r["authority_status"], "Operational relevance": r["primary_role"], "Evidence": r.get('evidence_source', 'UNKNOWN'), "Automation": r.get('automation_status', 'NOT_EVALUABLE'), "Lifecycle": ", ".join(r.get("lifecycle_phases", [])), "Review": r["human_review"], "Source page": r["page_start"], "Source verified": r["source_verification"], "ID": r["requirement_id"]} for r in filtered], hide_index=True, width="stretch")
        if filtered:
            selected = st.selectbox("Evidence drilldown", [r["requirement_id"] for r in filtered], key=f"intelligence_detail_{analysis['analysis_id']}")
            row = next(r for r in filtered if r["requirement_id"] == selected)
            with st.expander("Immutable source evidence", expanded=True):
                st.code(row["exact_quote"])
                st.caption(f"Pages {row['page_start']}–{row['page_end']} · Source IDs: {', '.join(row['source_ids']) or 'unlinked'}")
                st.json({key: row.get(key, "NOT PROVIDED BY THIS ANALYSIS VERSION") for key in ("temporal_expressions", "numeric_expressions", "exception_texts", "cross_reference_ids", "ambiguity_flags", "authority_basis")})

    with tabs[2]:
        st.caption("Proposed evidence mapping only. Product availability is established only by a verified deterministic adapter.")
        st.subheader("Operational constraints")
        st.dataframe(analysis["constraint_proposals"], hide_index=True, width="stretch")
        st.subheader("Environmental data requirements")
        st.dataframe(analysis["data_needs"], hide_index=True, width="stretch")
        st.subheader("Data feasibility")
        st.dataframe(analysis["data_feasibility"], hide_index=True, width="stretch")
        if local_audit:
            st.warning('DATA REQUIRED — no site/time-matched environmental evidence was fetched or inherited.')
            st.dataframe(local_audit.get('evidence_mapping', []), hide_index=True, width='stretch')
        geographic_or_calendar = [row for row in requirements if row.get("temporal_expressions") or row.get("numeric_expressions")]
        st.subheader("Geographic and calendar restrictions")
        if geographic_or_calendar:
            st.dataframe([{"requirement_id": row["requirement_id"], "page": row["page_start"], "temporal": row.get("temporal_expressions", []), "numeric_or_geographic": row.get("numeric_expressions", []), "source_verified": row["source_verification"]} for row in geographic_or_calendar], hide_index=True, width="stretch")
        else:
            st.info("No normalized geographic/calendar fields are available. Inspect the original requirement quotations; absence of structured fields does not mean absence of restrictions.")
        open_flags = [flag for flag in analysis["review_flags"] if flag["status"] == "OPEN"]
        if open_flags:
            st.warning("Open evidence and authority review flags remain. No rule is activated.")
            st.dataframe(open_flags, hide_index=True, width="stretch")

    with tabs[3]:
        windows = analysis["work_windows"]
        st.warning("Not legally authorized. Forecast favorability cannot grant permit authority.")
        st.write({"status": windows["status"], "evaluation_ready": windows["evaluation_ready"], "blocking_reasons": windows["blocking_reasons"]})
        if windows["windows"]:
            st.dataframe(windows["windows"], hide_index=True, width="stretch")
        else:
            st.info("No work windows have been calculated. Missing evidence is never favorable evidence.")

    with tabs[4]:
        st.subheader("Audit and evidence")
        st.subheader("Runtime identity")
        st.json(runtime_metadata())
        st.dataframe(stage_runs, hide_index=True, width="stretch")
        ledger_path = analysis_path.parent / "live_acceptance_dispatch_ledger.json"
        if local_audit:
            ledger_path = analysis_path.parent.parent / "live_acceptance_dispatch_ledger.json"
            st.subheader('Attribution corrections (original evidence preserved)')
            st.dataframe(local_audit.get('attribution_corrections', []), hide_index=True, width='stretch')
            st.subheader('Duplicate records retained in audit')
            st.dataframe(local_audit.get('duplicates', []), hide_index=True, width='stretch')
        if ledger_path.exists():
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            st.subheader("Live acceptance dispatch ledger")
            st.caption(f"{len(ledger.get('dispatches', []))}/{ledger.get('request_cap')} requests reserved · cap ${ledger.get('budget_cap_usd', 0):.2f}")
            st.dataframe(ledger.get("dispatches", []), hide_index=True, width="stretch")
        raw_paths = analysis.get("audit", {}).get("raw_response_paths", [])
        if raw_paths:
            accountability_path = Path(raw_paths[0]).parent / "stage1_condition_accountability.json"
            if accountability_path.exists():
                accountability = json.loads(accountability_path.read_text(encoding="utf-8"))
                st.subheader("Stage 1 numbered-condition accountability")
                st.write(accountability.get("summary", {}))
                st.dataframe(accountability.get("numbered_conditions", []), hide_index=True, width="stretch")
        st.dataframe(coverage["page_results"], hide_index=True, width="stretch")
        st.caption("Exports contain the same persisted, document-scoped records shown above.")
        st.download_button("Download canonical analysis (JSON)", export_json(analysis), "permitpulse_intelligence.json", "application/json", key=f"intelligence_json_{analysis['analysis_id']}")
        st.download_button("Download requirements (CSV)", csv_bytes(requirements), "permitpulse_requirements.csv", "text/csv", key=f"intelligence_csv_{analysis['analysis_id']}")
        st.download_button("Download intelligence workbook", excel_bytes({**analysis, **local_audit}), "permitpulse_intelligence.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"intelligence_xlsx_{analysis['analysis_id']}")
