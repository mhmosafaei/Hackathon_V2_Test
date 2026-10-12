"""Synthetic test-only fixtures; not Belfast operational evidence."""
from datetime import datetime, timezone, timedelta
from src.models.common import AutomationStatus, QualityStatus, RuleOutcome, SourceRole, SourceType, OperationalStatus
from src.models.environmental import SourceBinding
from src.models.executable_rule import ExecutableRule, RuleGroup, GroupOperator, RuleKind
from src.permit.evaluator import EvidenceSample, evaluate_rule, combine_results, merge_compatible

T=datetime(2026,4,15,12,tzinfo=timezone.utc)
def rule(kind=RuleKind.INSTANT,source=SourceType.CALENDAR,automatic=True,**extra):
 data=dict(rule_id='r',source_condition_id='c',kind=kind,variable='wave',operator='<=',threshold=1.0,unit='m',
           source_bindings=[SourceBinding(source_type=source,role=SourceRole.PRIMARY_COMPLIANCE,deciding=True)],
           automation_status=AutomationStatus.AUTOMATIC if automatic else AutomationStatus.EXTERNAL_DATA_REQUIRED,
           confirmed_by_user='test',confirmed_at=T,source_page=1,source_text='Synthetic fixture only')
 data.update(extra); return ExecutableRule.model_validate(data)
def sample(value=0.5,source=SourceType.CALENDAR,at=T,quality=QualityStatus.AVAILABLE): return EvidenceSample(source,SourceRole.PRIMARY_COMPLIANCE,at,value,'m',quality,'e1')

def test_calendar_and_confirmation_eligible_rule():
 r=rule(kind=RuleKind.CALENDAR,applicable_start_date='2026-04-01',applicable_end_date='2026-05-31')
 result=evaluate_rule(r,T,T,[])
 assert result.outcome is RuleOutcome.FAIL and result.required_actions[0].value=='NONE'

def test_immediate_threshold_duration_and_stale_evidence():
 assert evaluate_rule(rule(),T,T,[sample(2)]).outcome is RuleOutcome.FAIL
 duration=rule(kind=RuleKind.DURATION,duration_hours=2)
 assert evaluate_rule(duration,T,T+timedelta(hours=2),[sample(2,at=T),sample(2,at=T+timedelta(hours=1)),sample(2,at=T+timedelta(hours=2))]).outcome is RuleOutcome.FAIL
 stale=evaluate_rule(rule(),T,T,[sample(.5,at=T-timedelta(hours=3))])
 assert stale.outcome is RuleOutcome.UNKNOWN and 'stale' in stale.detail

def test_state_hysteresis_and_external_evidence_gate():
 state=rule(kind=RuleKind.STATE,operator='<=',threshold=1,threshold_upper=.5)
 assert evaluate_rule(state,T,T,[sample(1.2)],OperationalStatus.YES).operational_status is OperationalStatus.STOP
 assert evaluate_rule(state,T,T,[sample(.4)],OperationalStatus.STOP).operational_status is OperationalStatus.RESUME
 missing=evaluate_rule(rule(source=SourceType.LOCAL_SENSOR,automatic=False),T,T,[])
 assert missing.outcome is RuleOutcome.UNKNOWN and missing.required_actions[0].value=='PROVIDE_EXTERNAL_EVIDENCE'

def test_manual_ais_and_authority_gates_never_pass_without_authorized_evidence():
 ais=evaluate_rule(rule(source=SourceType.AIS_GNSS,automatic=False),T,T,[])
 approval=evaluate_rule(rule(kind=RuleKind.MANUAL_GATE,source=SourceType.AUTHORITY_APPROVAL,automatic=True),T,T,[])
 assert ais.outcome is RuleOutcome.UNKNOWN and approval.outcome is RuleOutcome.UNKNOWN

def test_and_or_conflict_logic_and_signature_window_merging():
 yes=evaluate_rule(rule(rule_id='a'),T,T,[sample(.5)])
 no=evaluate_rule(rule(rule_id='b'),T,T,[sample(2)])
 unknown=evaluate_rule(rule(rule_id='c'),T,T,[sample(.5,at=T-timedelta(hours=3))])
 assert combine_results(RuleGroup(group_id='and',operator=GroupOperator.AND,members=['a','c']),[yes,unknown]).outcome is RuleOutcome.UNKNOWN
 assert combine_results(RuleGroup(group_id='or',operator=GroupOperator.OR,members=['b','c']),[no,unknown]).outcome is RuleOutcome.UNKNOWN
 first=yes.model_copy(update={'t_end':T+timedelta(hours=1)})
 second=yes.model_copy(update={'t_start':T+timedelta(hours=1),'t_end':T+timedelta(hours=2)})
 merged=merge_compatible([first,second])
 assert len(merged)==1 and merged[0].t_end==T+timedelta(hours=2)
