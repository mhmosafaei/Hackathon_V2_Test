"""Read-only Stage 4B view models; synthetic demonstrations never touch review storage."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from src.models.common import AutomationStatus, ConditionType, ReviewState, SourceRole, SourceType
from src.models.environmental import SourceBinding
from src.models.executable_rule import ExecutableRule, RuleKind
from src.permit.classification import classify
from src.permit.evaluator import EvidenceSample, evaluate_rule

ADMIN_TYPES={ConditionType.REPORTING_DEADLINE.value,ConditionType.DOCUMENT_APPROVAL.value,ConditionType.OPERATING_METHOD.value,ConditionType.EVENT_TRIGGER.value}

def readiness(root: Path) -> dict:
    conditions=json.loads((root/'cache/extractions/ml2025054/aggregate.json').read_text())['conditions']
    decision_path=root/'cache/extractions/ml2025054/review_decisions.json'
    decisions=json.loads(decision_path.read_text()) if decision_path.exists() else {}
    rows=[]
    for condition in conditions:
        binding, derived=classify(condition.get('variable'),condition['condition_type'],condition.get('evidence_requirements',[]))
        status=condition.get('automation_status') or derived.value
        decision=decisions.get(condition['condition_id'],{}).get('decision','UNREVIEWED')
        executable=decision=='CONFIRMED' and condition['quote_verified']
        rows.append({'condition_id':condition['condition_id'],'page':condition['page_number'],'type':condition['condition_type'],
          'source_text':condition['source_text'],'quote_verified':condition['quote_verified'],'review_status':decision,
          'executable':executable,'automation_status':status,'required_source':binding.source_type.value,
          'required_action':condition['required_action'],'evidence_requirements':'; '.join(condition.get('evidence_requirements',[])) or 'Not structured',
          'administrative':condition['condition_type'] in ADMIN_TYPES})
    return {'document_id':conditions[0]['document_id'] if conditions else None,'conditions':rows,
      'confirmed_executable':sum(x['executable'] for x in rows),'awaiting_review':sum(not x['executable'] for x in rows),
      'external_evidence':sum(x['automation_status']==AutomationStatus.EXTERNAL_DATA_REQUIRED.value for x in rows),
      'manual_evidence':sum(x['automation_status']==AutomationStatus.MANUAL_INPUT_REQUIRED.value for x in rows),
      'unsupported':sum(x['automation_status']==AutomationStatus.NOT_EVALUABLE.value for x in rows)}

def demonstration() -> list[dict]:
    """No Belfast IDs, no persisted decisions, no live evidence: isolated engine demonstration."""
    now=datetime(2026,6,1,12,tzinfo=timezone.utc)
    binding=SourceBinding(source_type=SourceType.CALENDAR,role=SourceRole.PRIMARY_COMPLIANCE,deciding=True)
    calendar=ExecutableRule(rule_id='fixture-calendar',source_condition_id='TEST-FIXTURE-CALENDAR',kind=RuleKind.CALENDAR,
      applicable_start_date='2026-06-01',applicable_end_date='2026-06-30',source_bindings=[binding],automation_status=AutomationStatus.AUTOMATIC,confirmed_by_user='fixture',confirmed_at=now,source_text='Synthetic calendar fixture')
    threshold=ExecutableRule(rule_id='fixture-threshold',source_condition_id='TEST-FIXTURE-THRESHOLD',kind=RuleKind.INSTANT,variable='synthetic_wave',operator='<=',threshold=1,unit='m',source_bindings=[binding],automation_status=AutomationStatus.AUTOMATIC,confirmed_by_user='fixture',confirmed_at=now,source_text='Synthetic threshold fixture')
    stale=EvidenceSample(SourceType.CALENDAR,SourceRole.PRIMARY_COMPLIANCE,now-timedelta(hours=3),.5,'m')
    fresh=EvidenceSample(SourceType.CALENDAR,SourceRole.PRIMARY_COMPLIANCE,now,1.2,'m')
    return [result.model_dump(mode='json') for result in [evaluate_rule(calendar,now,now,[]),evaluate_rule(threshold,now,now,[fresh]),evaluate_rule(threshold,now,now,[stale])]]
