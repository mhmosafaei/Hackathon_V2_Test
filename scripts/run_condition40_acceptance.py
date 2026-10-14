"""One-request, explicitly scoped Condition 40 environmental acceptance run.

This is an operator-invoked acceptance utility, not the normal environmental
fetch path.  It reuses the production router, service and Copernicus adapter,
but scopes evaluation to condition 40 and writes to a separate cache namespace.
No request is made unless --live is supplied.
"""
import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.environmental.models import EvaluationInput
from src.environmental.service import evaluate

RUN_ID = '2b2e047e0db14583bb27d828c0579284'
START = '2026-10-13T00:00:00+00:00'
END = '2026-10-15T00:00:00+00:00'


def find_analysis(root: Path):
    matches = list((root / 'cache' / 'simple_analysis').glob(f'*/{RUN_ID}/analysis.json'))
    if len(matches) != 1:
        raise RuntimeError(f'Expected exactly one persisted analysis for run {RUN_ID}; found {len(matches)}')
    analysis = json.loads(matches[0].read_text(encoding='utf-8'))
    if analysis.get('analysis_id') != RUN_ID:
        raise RuntimeError('Persisted analysis run identity mismatch')
    return analysis


def preflight_worker_dependencies():
    if importlib.util.find_spec('copernicusmarine') is None:
        raise SystemExit(
            'Preflight failed: copernicusmarine is unavailable in the acceptance interpreter; '
            'no provider dispatch attempted.'
        )


def main():
    parser = argparse.ArgumentParser(description='Explicit Condition 40-only acceptance fetch')
    parser.add_argument('--live', action='store_true', help='Dispatch the one authorized provider request')
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    if not args.live:
        raise SystemExit('Refusing provider dispatch: rerun with --live only after explicit authorization.')

    preflight_worker_dependencies()
    # The production runtime may load .env through python-dotenv.  Keep this
    # operator utility dependency-light for offline preflight; an environment
    # already prepared by the application is valid without the optional import.
    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None
    if load_dotenv is not None:
        load_dotenv(args.root / '.env')
    analysis = find_analysis(args.root)
    candidates = [item for item in analysis.get('environmental_requirements', [])
                  if str(item.get('condition_id')) == '40']
    if len(candidates) != 1 or candidates[0].get('canonical_variable') not in {'turbidity', 'turbidity_fnu'}:
        raise RuntimeError('Accepted analysis does not contain exactly one FNU turbidity Condition 40 requirement')
    if str(candidates[0].get('unit', '')).upper() != 'FNU':
        raise RuntimeError('Condition 40 is not explicitly FNU; refusing scoped dispatch')
    output = (args.root / 'cache' / 'simple_environment' / 'condition40_acceptance' /
              RUN_ID / uuid4().hex)
    inputs = EvaluationInput(analysis_id=RUN_ID, latitude=54.023, longitude=-5.9275,
        start_time=START, end_time=END, point_scope_confirmed=True)
    from src.environmental.copernicus import retrieve
    result = evaluate(analysis, inputs, output, transports={'COPERNICUS_MARINE': retrieve},
                      condition_ids={'40'})
    output.mkdir(parents=True, exist_ok=True)
    (output / 'result.json').write_text(json.dumps({
        'run_id': RUN_ID, 'condition_scope': ['40'],
        'created_at': datetime.now(timezone.utc).isoformat(), 'result': result},
        indent=2, allow_nan=False), encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
