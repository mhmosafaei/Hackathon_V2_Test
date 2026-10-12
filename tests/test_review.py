import json
from pathlib import Path
import pytest
from src.permit.review import save_decision

def fixture_root() -> Path:
    root=Path('tests/fixtures/review_runtime')
    target=root/'cache/extractions/ml2025054'; target.mkdir(parents=True,exist_ok=True)
    (target/'aggregate.json').write_text((Path('tests/fixtures/review/aggregate.json')).read_text())
    return root

def test_confirmed_decision_persists():
    root=fixture_root(); save_decision(root,'ok','CONFIRMED','test')
    assert json.loads((root/'cache/extractions/ml2025054/review_decisions.json').read_text())['ok']['decision']=='CONFIRMED'

def test_unverified_condition_cannot_be_generically_confirmed():
    with pytest.raises(ValueError): save_decision(fixture_root(),'bad','CONFIRMED','test')
