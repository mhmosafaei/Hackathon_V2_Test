from src.permit.review_overlays import review_progress


def row(state='UNREVIEWED', applicability='UNASSESSED', note='', conflict=None):
    return {'state': state, 'applicability': applicability,
            'review': {'note': note}, 'conflict': conflict}


def test_review_gate_requires_resolution_and_applicability():
    assert not review_progress([])['complete']
    rows = [row('APPROVED', 'APPLICABLE'), row('CORRECTED', 'NOT_APPLICABLE', 'Reason documented')]
    assert review_progress(rows) == {'total': 2, 'resolved': 2, 'remaining': 0, 'complete': True}
    for unresolved in [row(), row('REJECTED', 'APPLICABLE'), row('APPROVED', 'UNASSESSED'),
                       row('APPROVED', 'NOT_APPLICABLE'), row('APPROVED', 'APPLICABLE', conflict='CONFLICT')]:
        progress = review_progress([rows[0], unresolved])
        assert progress['remaining'] == 1 and not progress['complete']


def test_decision_endpoint_rejects_incomplete_human_review(tmp_path):
    import json
    from fastapi import Request
    from tests.test_review_overlays import fixture
    from src.permit.simple_api import DecisionInput, create_app

    analysis, _ = fixture(tmp_path)
    app = create_app(tmp_path)
    app.state.analyses[analysis['analysis_id']] = analysis
    endpoint = next(route.endpoint for route in app.routes
                    if getattr(route, 'path', None) == '/api/decision/evaluate')
    scope = {'type': 'http', 'scheme': 'http', 'server': ('test', 80),
             'path': '/api/decision/evaluate', 'query_string': b'',
             'headers': [(b'x-session-id', app.state.boot_id.encode())]}
    coroutine = endpoint(DecisionInput(analysis_run_id=analysis['analysis_id'],
                                       document_sha256=analysis['document_sha256']), Request(scope))
    # The route has no awaits; complete it directly so this test needs no socket-based event loop.
    try:
        coroutine.send(None)
    except StopIteration as finished:
        response = finished.value
    else:
        raise AssertionError('Decision route unexpectedly suspended')
    assert response.status_code == 409
    payload = json.loads(response.body)
    assert payload['error'] == 'HUMAN_REVIEW_INCOMPLETE'
    assert payload['review_progress']['remaining'] == 1
    assert analysis['analysis_id'] not in app.state.decisions

    from src.permit.review_overlays import list_reviews, save_review
    row = list_reviews(tmp_path, analysis)['requirements'][0]
    save_review(tmp_path, analysis, row['target_id'], {
        'state': 'APPROVED', 'applicability': 'APPLICABLE', 'reviewer': 'Tester',
        'note': 'Reviewed', 'corrections': {}, 'original_fingerprint': row['original_fingerprint']})
    assert list_reviews(tmp_path, analysis)['review_progress']['complete']
    coroutine = endpoint(DecisionInput(analysis_run_id=analysis['analysis_id'],
                                       document_sha256=analysis['document_sha256']), Request(scope))
    try:
        coroutine.send(None)
    except StopIteration as finished:
        unlocked = finished.value
    else:
        raise AssertionError('Decision route unexpectedly suspended')
    assert unlocked['current_assessment']['status'] == 'UNKNOWN'
    assert analysis['analysis_id'] in app.state.decisions
