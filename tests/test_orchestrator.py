import json
from pathlib import Path
from src.permit.orchestrator import identity
def test_cache_identity_changes_with_model_and_content():
    assert identity(b'a','m1') != identity(b'a','m2')
    assert identity(b'a','m1') != identity(b'b','m1')
def test_checkpoint_manifest_is_resumable_shape():
    path=Path('tests/fixtures/orchestrator_manifest.json'); path.write_text(json.dumps({'pages':{'3':{'status':'COMPLETE'}}}))
    assert json.loads(path.read_text())['pages']['3']['status']=='COMPLETE'
