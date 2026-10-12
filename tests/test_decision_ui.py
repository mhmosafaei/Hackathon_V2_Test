from pathlib import Path
from src.permit.decision_ui import readiness, demonstration

def test_real_belfast_readiness_does_not_silently_authorize_unreviewed_conditions():
 view=readiness(Path('.'))
 assert view['document_id']=='ML2025054'
 assert view['confirmed_executable']==0 and view['awaiting_review']==59
 assert all(not row['executable'] for row in view['conditions'])

def test_demonstration_is_synthetic_and_has_explainable_outcomes_without_belfast_ids():
 results=demonstration()
 assert len(results)==3
 assert all(result['condition_id'].startswith('TEST-FIXTURE') for result in results)
 assert {result['outcome'] for result in results}=={'FAIL','UNKNOWN'}
 assert all(result['source_text'].startswith('Synthetic') for result in results)

def test_administrative_obligations_remain_visible():
 rows=readiness(Path('.'))['conditions']
 assert any(row['administrative'] and row['required_action'] in {'REPORT','NOTIFY','REQUEST_APPROVAL','MANUAL_CONFIRMATION'} for row in rows)
