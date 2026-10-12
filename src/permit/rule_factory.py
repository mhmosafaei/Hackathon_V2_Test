"""The only route from a confirmed document condition to executable logic."""
from datetime import datetime, timezone
from src.models.common import AutomationStatus, ReviewState
from src.models.executable_rule import ExecutableRule, RuleKind
from src.models.extracted_condition import ExtractedCondition
from src.models.environmental import SourceBinding

def make_rule(condition: ExtractedCondition, binding: SourceBinding, user: str) -> ExecutableRule | None:
    if condition.review_state not in {ReviewState.CONFIRMED, ReviewState.EDITED_CONFIRMED} or not condition.quote_verified: return None
    kinds = {"CALENDAR_RESTRICTION": RuleKind.CALENDAR, "TIME_WINDOW": RuleKind.CALENDAR,
             "DOCUMENT_APPROVAL": RuleKind.MANUAL_GATE, "INSTANT_THRESHOLD": RuleKind.INSTANT,
             "RANGE": RuleKind.INSTANT, "DURATION_THRESHOLD": RuleKind.DURATION,
             "STATE_TRANSITION": RuleKind.STATE}
    return ExecutableRule(rule_id=f"rule-{condition.condition_id}", source_condition_id=condition.condition_id,
        variable=condition.variable, operator=condition.operator, threshold=condition.threshold, threshold_upper=condition.threshold_upper, unit=condition.unit,
        kind=kinds.get(condition.condition_type.value, RuleKind.MANUAL_GATE), duration_hours=condition.duration_hours,
        source_bindings=[binding], automation_status=condition.automation_status or AutomationStatus.NOT_EVALUABLE,
        confirmed_by_user=user, confirmed_at=datetime.now(timezone.utc), source_page=condition.page_number,
        source_clause=condition.clause, source_text=condition.source_text, required_evidence=condition.evidence_requirements,
        applicable_start_date=str(condition.start_date) if condition.start_date else None,
        applicable_end_date=str(condition.end_date) if condition.end_date else None)
