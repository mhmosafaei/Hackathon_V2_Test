"""Pure, deterministic, evidence-authorized Stage 4A rule evaluation."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from src.models.common import ActionRequired, AutomationStatus, OperationalStatus, QualityStatus, RuleOutcome, SourceRole, SourceType
from src.models.executable_rule import ExecutableRule, GroupOperator, RuleGroup, RuleKind
from src.models.decision import RuleResult

@dataclass(frozen=True)
class EvidenceSample:
    source_type: SourceType
    source_role: SourceRole
    timestamp: datetime
    value: float | None = None
    unit: str | None = None
    quality: QualityStatus = QualityStatus.AVAILABLE
    evidence_id: str = 'fixture-evidence'

def _unknown(rule, start, end, detail, action=ActionRequired.PROVIDE_EXTERNAL_EVIDENCE):
    return RuleResult(rule_id=rule.rule_id,t_start=start,t_end=end,outcome=RuleOutcome.UNKNOWN,detail=detail,
                      required_actions=[action],evidence_ids=[],condition_id=rule.source_condition_id,
                      source_text=rule.source_text,source_page=rule.source_page,operational_status=OperationalStatus.UNKNOWN,rule_trace=[detail])

def _compare(value, operator, threshold, upper=None):
    if operator in {'<','<='}: return value <= threshold if operator=='<=' else value < threshold
    if operator in {'>','>='}: return value >= threshold if operator=='>=' else value > threshold
    if operator in {'=','=='}: return value == threshold
    if operator=='BETWEEN' and upper is not None: return threshold <= value <= upper
    raise ValueError(f'unsupported operator: {operator}')

def _authorized(rule, evidence, at):
    binding=next((x for x in rule.source_bindings if x.deciding),None)
    if binding is None: return None,'no legally deciding source binding'
    sample=next((x for x in evidence if x.source_type==binding.source_type and x.source_role==SourceRole.PRIMARY_COMPLIANCE),None)
    if sample is None: return None,f'missing deciding {binding.source_type.value} evidence'
    if sample.quality!=QualityStatus.AVAILABLE: return None,f'deciding evidence quality is {sample.quality.value}'
    if sample.timestamp>at or at-sample.timestamp>timedelta(hours=2): return None,'deciding evidence is stale or not valid for evaluation time'
    return sample,None

def evaluate_rule(rule: ExecutableRule, start: datetime, end: datetime, evidence: list[EvidenceSample],
                  previous_status: OperationalStatus | None=None) -> RuleResult:
    """Evaluate an already-confirmed rule; never upgrades advisory/predictive data to deciding evidence."""
    if not rule.active: return _unknown(rule,start,end,'rule inactive',ActionRequired.MANUAL_CONFIRMATION)
    if rule.automation_status==AutomationStatus.EXTERNAL_DATA_REQUIRED: return _unknown(rule,start,end,'external deciding evidence required')
    if rule.automation_status==AutomationStatus.MANUAL_INPUT_REQUIRED or rule.kind==RuleKind.MANUAL_GATE:
        return _unknown(rule,start,end,'manual approval or input required',ActionRequired.REQUEST_APPROVAL)
    if rule.automation_status!=AutomationStatus.AUTOMATIC: return _unknown(rule,start,end,'rule is not automatically evaluable',ActionRequired.MANUAL_CONFIRMATION)
    if rule.kind==RuleKind.CALENDAR:
        local=start.astimezone(ZoneInfo(rule.timezone)).date(); begin=__import__('datetime').date.fromisoformat(rule.applicable_start_date) if rule.applicable_start_date else None; finish=__import__('datetime').date.fromisoformat(rule.applicable_end_date) if rule.applicable_end_date else None
        restricted=(begin is None or local>=begin) and (finish is None or local<=finish)
        outcome=RuleOutcome.FAIL if restricted else RuleOutcome.PASS
        return RuleResult(rule_id=rule.rule_id,t_start=start,t_end=end,outcome=outcome,detail='calendar restriction active' if restricted else 'outside calendar restriction',required_actions=[ActionRequired.NONE],condition_id=rule.source_condition_id,source_text=rule.source_text,source_page=rule.source_page,operational_status=OperationalStatus.STOP if restricted else OperationalStatus.YES,rule_trace=[f'local_date={local}',f'timezone={rule.timezone}'])
    if rule.kind==RuleKind.DURATION:
        return evaluate_duration_rule(rule,start,end,evidence)
    sample,error=_authorized(rule,evidence,end)
    if error: return _unknown(rule,start,end,error)
    if sample.value is None or rule.threshold is None or not rule.operator: return _unknown(rule,start,end,'numeric value, operator or threshold absent',ActionRequired.MANUAL_CONFIRMATION)
    passed=_compare(sample.value,rule.operator,rule.threshold,rule.threshold_upper)
    if rule.kind==RuleKind.STATE and previous_status==OperationalStatus.STOP and rule.threshold_upper is not None:
        passed=sample.value<=rule.threshold_upper
        status=OperationalStatus.RESUME if passed else OperationalStatus.STOP
    else: status=OperationalStatus.YES if passed else OperationalStatus.STOP
    return RuleResult(rule_id=rule.rule_id,t_start=start,t_end=end,outcome=RuleOutcome.PASS if passed else RuleOutcome.FAIL,
      detail='threshold satisfied' if passed else 'threshold breached',measured_value=sample.value,unit=sample.unit,threshold=rule.threshold,
      required_actions=[ActionRequired.NONE] if passed else [ActionRequired.MANUAL_CONFIRMATION],evidence_ids=[sample.evidence_id],condition_id=rule.source_condition_id,source_text=rule.source_text,source_page=rule.source_page,evidence_timestamp=sample.timestamp,evidence_fresh=True,operational_status=status,rule_trace=[f'{sample.value} {rule.operator} {rule.threshold}'])

def evaluate_duration_rule(rule: ExecutableRule, start: datetime, end: datetime, evidence: list[EvidenceSample]) -> RuleResult:
    """Fail only after a continuous real-evidence breach reaches duration_hours; no gap filling."""
    binding=next((x for x in rule.source_bindings if x.deciding),None)
    samples=sorted([x for x in evidence if binding and x.source_type==binding.source_type and x.source_role==SourceRole.PRIMARY_COMPLIANCE and x.quality==QualityStatus.AVAILABLE and x.value is not None],key=lambda x:x.timestamp)
    if not samples or rule.threshold is None or not rule.operator or rule.duration_hours is None:
        return _unknown(rule,start,end,'duration rule lacks authorized continuous evidence')
    breach_start=None; last=None
    for sample in samples:
        valid_gap=last is None or sample.timestamp-last.timestamp<=timedelta(hours=2)
        failed=not _compare(sample.value,rule.operator,rule.threshold,rule.threshold_upper)
        if failed and valid_gap:
            breach_start=sample.timestamp if breach_start is None else breach_start
            if sample.timestamp-breach_start>=timedelta(hours=rule.duration_hours):
                return RuleResult(rule_id=rule.rule_id,t_start=breach_start,t_end=sample.timestamp,outcome=RuleOutcome.FAIL,detail='continuous threshold exceedance duration reached',measured_value=sample.value,unit=sample.unit,threshold=rule.threshold,required_actions=[ActionRequired.MANUAL_CONFIRMATION],evidence_ids=[x.evidence_id for x in samples],condition_id=rule.source_condition_id,source_text=rule.source_text,source_page=rule.source_page,evidence_timestamp=sample.timestamp,evidence_fresh=True,operational_status=OperationalStatus.STOP,rule_trace=[f'breach_start={breach_start.isoformat()}',f'duration_hours={rule.duration_hours}'])
        else: breach_start=None
        last=sample
    return RuleResult(rule_id=rule.rule_id,t_start=start,t_end=end,outcome=RuleOutcome.PASS,detail='continuous breach duration not reached',required_actions=[ActionRequired.NONE],evidence_ids=[x.evidence_id for x in samples],condition_id=rule.source_condition_id,source_text=rule.source_text,source_page=rule.source_page,operational_status=OperationalStatus.YES,rule_trace=[f'duration_hours={rule.duration_hours}'])

def combine_results(group: RuleGroup, results: list[RuleResult]) -> RuleResult:
    if {x.rule_id for x in results} != set(group.members): raise ValueError('group results must exactly match group members')
    outcomes=[x.outcome for x in results]
    if group.operator==GroupOperator.AND:
        outcome=RuleOutcome.FAIL if RuleOutcome.FAIL in outcomes else RuleOutcome.UNKNOWN if RuleOutcome.UNKNOWN in outcomes else RuleOutcome.PASS
    else: outcome=RuleOutcome.PASS if RuleOutcome.PASS in outcomes else RuleOutcome.UNKNOWN if RuleOutcome.UNKNOWN in outcomes else RuleOutcome.FAIL
    first=results[0]; return RuleResult(rule_id=group.group_id,t_start=first.t_start,t_end=first.t_end,outcome=outcome,detail=f'{group.operator.value} group evaluation',required_actions=sum((x.required_actions for x in results),[]),evidence_ids=sum((x.evidence_ids for x in results),[]),operational_status=OperationalStatus.YES if outcome==RuleOutcome.PASS else OperationalStatus.STOP if outcome==RuleOutcome.FAIL else OperationalStatus.UNKNOWN,rule_trace=[f'{x.rule_id}={x.outcome.value}' for x in results])

def merge_compatible(results: list[RuleResult]) -> list[RuleResult]:
    merged=[]
    for result in sorted(results,key=lambda x:x.t_start):
        signature=(result.rule_id,result.outcome,result.detail,result.required_actions,result.evidence_ids,result.measured_value,result.threshold)
        if merged and merged[-1].t_end==result.t_start and (merged[-1].rule_id,merged[-1].outcome,merged[-1].detail,merged[-1].required_actions,merged[-1].evidence_ids,merged[-1].measured_value,merged[-1].threshold)==signature:
            merged[-1]=merged[-1].model_copy(update={'t_end':result.t_end})
        else: merged.append(result)
    return merged
