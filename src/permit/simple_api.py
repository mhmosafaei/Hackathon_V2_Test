"""Loopback React host. No active analysis is restored or shared between sessions."""
import argparse
import os
import base64
import binascii
import secrets
import asyncio
import logging
import json
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
from urllib.parse import unquote
from pydantic import BaseModel, ConfigDict, Field

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from .simple_analysis import ExtractionIncompleteError, analyze
from src.environmental.models import EvaluationInput
from src.environmental.service import evaluate, provider_status
from src.environmental.capabilities import capability_matrix
from .persisted_analysis import load_persisted_analysis
from .review_overlays import list_reviews, save_review, bulk_approve

ROOT = Path(__file__).resolve().parents[2]


class CoordinateInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    analysis_id: str
    location_index: int = Field(ge=0)
    force: bool = False


class RestoreInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    document_sha256: str = Field(pattern=r'^[0-9a-fA-F]{64}$')
    analysis_run_id: str = Field(pattern=r'^[0-9a-fA-F]{32,64}$')


class DecisionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    analysis_run_id: str
    document_sha256: str
    start: str | None = None
    horizon_hours: int = 72
    duration_hours: int = 4
    include_conditional: bool = False
    ranking: str = 'earliest'




def create_app(root=ROOT, *, transport=None, dist=None, environmental_transports=None, coordinate_transport=None):
    app = FastAPI(docs_url=None, redoc_url=None)
    # Private demo only: one shared operator identity, not multi-tenant access.
    @app.middleware('http')
    async def demo_access(request: Request, call_next):
        if request.url.path == '/api/health':
            return await call_next(request)
        if os.environ.get('PERMITPULSE_PRIVATE_DEMO') != '1':
            return await call_next(request)
        username = os.environ.get('PERMITPULSE_DEMO_USERNAME', '')
        password = os.environ.get('PERMITPULSE_DEMO_PASSWORD', '')
        if not username or not password:
            return JSONResponse({'error': 'DEMO_ACCESS_NOT_CONFIGURED'}, status_code=503)
        auth = request.headers.get('authorization', '')
        authorized = False
        if auth.startswith('Basic '):
            try:
                raw = base64.b64decode(auth[6:], validate=True).decode('utf-8')
                supplied_user, supplied_password = raw.split(':', 1)
                authorized = (secrets.compare_digest(supplied_user, username)
                              and secrets.compare_digest(supplied_password, password))
            except (ValueError, UnicodeError, binascii.Error):
                pass
        if not authorized:
            return JSONResponse({'error': 'AUTHENTICATION_REQUIRED'}, status_code=401,
                headers={'WWW-Authenticate': 'Basic realm="PermitPulse private demo"',
                         'Cache-Control': 'no-store'})
        return await call_next(request)
    @app.get('/api/health')
    async def health():
        return {'status': 'ok'}

    def allowed_origin(request: Request):
        origin = request.headers.get('origin')
        if not origin:
            return True
        expected = os.environ.get('PERMITPULSE_ALLOWED_ORIGIN', '').rstrip('/')
        return origin == str(request.base_url).rstrip('/') or bool(expected and origin == expected)
    app.state.boot_id = uuid4().hex
    app.state.busy = False
    app.state.analyses = {}
    # Environmental retrieval results are session-scoped derived state. They
    # are intentionally separate from immutable permit analysis artifacts.
    app.state.environmental_results = {}
    app.state.conversions = {}
    app.state.decisions = {}
    app.state.invalidated_decisions = {}

    @app.post('/api/decision/evaluate')
    async def decision(inputs: DecisionInput, request: Request):
        origin = request.headers.get('origin')
        if not allowed_origin(request):
            return JSONResponse({'error': 'Request origin rejected.'}, status_code=403)
        if request.headers.get('x-session-id') != app.state.boot_id:
            return JSONResponse({'error': 'STALE_SESSION'}, status_code=409)
        analysis = app.state.analyses.get(inputs.analysis_run_id)
        if not analysis or analysis.get('document_sha256') != inputs.document_sha256:
            return JSONResponse({'error': 'ACTIVE_ANALYSIS_IDENTITY_MISMATCH'}, status_code=409)
        try:
            from .decision_engine import assess
            reviews = list_reviews(root, analysis)
            if not reviews['review_progress']['complete']:
                return JSONResponse({'error': 'HUMAN_REVIEW_INCOMPLETE',
                                     'review_progress': reviews['review_progress']}, status_code=409)
            result = assess(reviews, app.state.environmental_results.get(inputs.analysis_run_id),
                start=inputs.start, horizon_hours=inputs.horizon_hours, duration_hours=inputs.duration_hours,
                include_conditional=inputs.include_conditional, ranking=inputs.ranking)
            app.state.decisions[inputs.analysis_run_id] = result
            app.state.invalidated_decisions.pop(inputs.analysis_run_id, None)
            return result
        except (ValueError, OSError, TypeError, KeyError):
            return JSONResponse({'error': 'DECISION_INPUT_OR_REVIEW_INVALID'}, status_code=422)

    @app.get('/api/reviews')
    async def reviews(analysis_id: str, request: Request):
        if request.headers.get('x-session-id') != app.state.boot_id:
            return JSONResponse({'error': 'STALE_SESSION'}, status_code=409)
        analysis = app.state.analyses.get(analysis_id)
        if not analysis:
            return JSONResponse({'error': 'ACTIVE_ANALYSIS_REQUIRED'}, status_code=404)
        try:
            return list_reviews(root, analysis)
        except (ValueError, OSError) as exc:
            return JSONResponse({'error': str(exc) if isinstance(exc, ValueError) else 'REVIEW_STORE_UNAVAILABLE'}, status_code=409)

    @app.put('/api/reviews/bulk-approve')
    async def approve_all(request: Request):
        origin = request.headers.get('origin')
        if not allowed_origin(request):
            return JSONResponse({'error': 'Request origin rejected.'}, status_code=403)
        if request.headers.get('x-session-id') != app.state.boot_id:
            return JSONResponse({'error': 'STALE_SESSION'}, status_code=409)
        try:
            body = await request.json()
            if not isinstance(body, dict) or set(body) != {'analysis_run_id', 'document_sha256', 'reviewer', 'targets'}:
                raise ValueError('INVALID_BULK_REQUEST')
            if not isinstance(body['analysis_run_id'], str) or not isinstance(body['document_sha256'], str):
                raise ValueError('INVALID_REVIEW_IDENTITY')
            analysis = app.state.analyses.get(body['analysis_run_id'])
            if not analysis or analysis.get('document_sha256') != body['document_sha256']:
                return JSONResponse({'error': 'ACTIVE_ANALYSIS_IDENTITY_MISMATCH'}, status_code=409)
            return bulk_approve(root, analysis, body['reviewer'], body['targets'])
        except (ValueError, OSError) as exc:
            return JSONResponse({'error': str(exc) if isinstance(exc, ValueError) else 'REVIEW_STORE_UNAVAILABLE'}, status_code=422)

    @app.put('/api/reviews/{target_id}')
    async def review(target_id: str, request: Request):
        origin = request.headers.get('origin')
        if not allowed_origin(request):
            return JSONResponse({'error': 'Request origin rejected.'}, status_code=403)
        if request.headers.get('x-session-id') != app.state.boot_id:
            return JSONResponse({'error': 'STALE_SESSION'}, status_code=409)
        try:
            body = await request.json()
            if not isinstance(body, dict) or set(body) != {'analysis_run_id', 'document_sha256', 'review'}:
                raise ValueError('INVALID_REVIEW_REQUEST')
            if not isinstance(body['analysis_run_id'], str) or not isinstance(body['document_sha256'], str):
                raise ValueError('INVALID_REVIEW_IDENTITY')
            analysis = app.state.analyses.get(body['analysis_run_id'])
            if not analysis or analysis.get('document_sha256') != body['document_sha256']:
                return JSONResponse({'error': 'ACTIVE_ANALYSIS_IDENTITY_MISMATCH'}, status_code=409)
            if not isinstance(body['review'], dict):
                raise ValueError('INVALID_REVIEW_REQUEST')
            return save_review(root, analysis, target_id, body['review'])
        except (ValueError, OSError) as exc:
            return JSONResponse({'error': str(exc) if isinstance(exc, ValueError) else 'REVIEW_STORE_UNAVAILABLE'}, status_code=422)

    @app.post('/api/coordinates/convert')
    async def coordinates(inputs: CoordinateInput, request: Request):
        origin = request.headers.get('origin')
        if not allowed_origin(request):
            return JSONResponse({'error':'Request origin rejected.'}, status_code=403)
        if request.headers.get('x-session-id') != app.state.boot_id:
            return JSONResponse({'error':'Application restarted. Select your PDF again.'}, status_code=409)
        analysis = app.state.analyses.get(inputs.analysis_id)
        locations = analysis.get('spatial_context', []) if analysis else []
        if inputs.location_index >= len(locations):
            return JSONResponse({'error':'Source location not available.'}, status_code=404)
        location = locations[inputs.location_index]
        if not location.get('source_verified') or location.get('geometry_type') != 'point':
            return JSONResponse({'error':'Verified source point required. Review source coordinates.'}, status_code=422)
        if app.state.busy:
            return JSONResponse({'error':'A request is already running.'}, status_code=409)
        if transport and coordinate_transport is None:
            return JSONResponse({'error':'Mock conversion transport is not configured. No live request made.'}, status_code=409)
        key = (inputs.analysis_id, location.get('coordinates_original'), location.get('coordinate_system'))
        if key in app.state.conversions and not inputs.force:
            return app.state.conversions[key]
        app.state.busy = True
        try:
            from .coordinate_conversion import convert
            result = await asyncio.to_thread(convert, location,
                root/'cache'/'coordinate_conversions'/inputs.analysis_id, transport=coordinate_transport)
            app.state.conversions[key] = result
            return result
        except Exception:
            return JSONResponse({'error':'Coordinate conversion could not be verified. Review the source coordinate system or enter a confirmed WGS84 location manually. No automatic retry.'}, status_code=422)
        finally:
            app.state.busy = False

    @app.get('/api/session')
    async def session():
        active_analysis_id = next(iter(app.state.analyses), None)
        saved = app.state.decisions.get(active_analysis_id)
        if saved:
            from .decision_engine import input_fingerprint
            try:
                current = input_fingerprint(list_reviews(root, app.state.analyses[active_analysis_id]),
                    app.state.environmental_results.get(active_analysis_id))
            except (ValueError, OSError, KeyError, TypeError):
                current = None
            if current is None or saved.get('audit', {}).get('input_fingerprint') != current:
                app.state.invalidated_decisions[active_analysis_id] = saved.get('assessment_id')
                app.state.decisions.pop(active_analysis_id, None)
        return {'boot_id': app.state.boot_id, 'mode': 'MOCK' if transport else 'LIVE',
                'invalidated_assessment_id':app.state.invalidated_decisions.get(active_analysis_id),
                'provider_status': provider_status(), 'environmental_capabilities': capability_matrix(),
                'decision_result': app.state.decisions.get(active_analysis_id),
                'environmental_result': app.state.environmental_results.get(active_analysis_id)}

    @app.post('/api/restore')
    async def restore(inputs: RestoreInput, request: Request):
        origin = request.headers.get('origin')
        if not allowed_origin(request):
            return JSONResponse({'error': 'Request origin rejected.'}, status_code=403)
        if request.headers.get('x-session-id') != app.state.boot_id:
            return JSONResponse({'error': 'Application restarted. Refresh the session.'}, status_code=409)
        try:
            result = load_persisted_analysis(root, inputs.document_sha256, inputs.analysis_run_id)
        except FileNotFoundError:
            return JSONResponse({'error': 'Persisted analysis run was not found.'}, status_code=404)
        except (ValueError, json.JSONDecodeError):
            return JSONResponse({'error': 'Persisted analysis reference or artifact is invalid.'}, status_code=422)
        app.state.analyses.clear()
        app.state.environmental_results.clear()
        app.state.analyses[result['analysis_id']] = result
        return result

    @app.get('/api/environmental/capabilities')
    async def environmental_capabilities():
        return {'capabilities': capability_matrix()}

    @app.post('/api/environmental')
    async def environmental(inputs: EvaluationInput, request: Request):
        origin = request.headers.get('origin')
        if not allowed_origin(request):
            return JSONResponse({'error': 'Request origin rejected.'}, status_code=403)
        if request.headers.get('x-session-id') != app.state.boot_id:
            return JSONResponse({'error': 'Application restarted. Select your PDF again.'}, status_code=409)
        analysis = app.state.analyses.get(inputs.analysis_id)
        if not analysis:
            return JSONResponse({'error': 'No active analysis for this session.'}, status_code=404)
        if inputs.latitude is not None:
            from .review_overlays import approved_spatial_points
            approved = approved_spatial_points(list_reviews(root, analysis))
            if not any(isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and abs(inputs.latitude-lat) < 1e-9 and abs(inputs.longitude-lon) < 1e-9 for lat, lon in approved):
                return JSONResponse({'error': 'An explicitly approved, source-verified permit point is required.'}, status_code=422)
        if app.state.busy:
            return JSONResponse({'error': 'A request is already running.'}, status_code=409)
        app.state.busy = True
        try:
            adapters = environmental_transports
            if not transport and adapters is not None:
                # Partial marine override must not silently remove the existing
                # forecast connector. Calls still require explicit Fetch.
                from src.environmental.ecmwf import retrieve as weather_retrieve
                adapters = {'ECMWF_FORECAST':weather_retrieve, **adapters}
            if transport and adapters is None:
                from src.environmental.fixture import mock_evidence
                adapters = {name: mock_evidence for name in ['COPERNICUS_MARINE', 'ECMWF_FORECAST', 'ERA5']}
            result = await asyncio.to_thread(evaluate, analysis, inputs,
                root/'cache'/'simple_environment'/app.state.boot_id/inputs.analysis_id, transports=adapters)
            result['mode'] = 'MOCK' if transport else 'LIVE'
            # Associate only a successfully returned aggregate result. A
            # provider/evaluation exception leaves any prior result intact.
            stored_result = {**result, 'analysis_id': inputs.analysis_id}
            app.state.environmental_results[inputs.analysis_id] = stored_result
            return result
        finally:
            app.state.busy = False

    @app.post('/api/analyze')
    async def run(request: Request):
        # Same-origin, no CORS; stale browser sessions cannot dispatch after restart.
        origin = request.headers.get('origin')
        if not allowed_origin(request):
            return JSONResponse({'error': 'Permit analysis could not be completed.'}, status_code=403)
        if request.headers.get('x-session-id') != app.state.boot_id:
            return JSONResponse({'error': 'Application restarted. Select your PDF again.'}, status_code=409)
        if app.state.busy:
            return JSONResponse({'error': 'An analysis is already running.'}, status_code=409)
        chunks = bytearray()
        async for chunk in request.stream():
            chunks.extend(chunk)
            if len(chunks) > 25_000_000:
                return JSONResponse({'error': 'PDF exceeds the 25 MB limit.'}, status_code=413)
        if app.state.busy:
            return JSONResponse({'error': 'An analysis is already running.'}, status_code=409)
        app.state.busy = True
        # A new document starts a new active session; never expose the prior
        # document's environmental evidence while it is being analyzed.
        app.state.analyses.clear()
        app.state.environmental_results.clear()
        try:
            result = await asyncio.to_thread(analyze, bytes(chunks), unquote(request.headers.get('x-filename', 'permit.pdf')), root, transport=transport)
            result = {**result, 'document_sha256': sha256(bytes(chunks)).hexdigest(), 'restored_from_persistence': False}
            # Active process memory only; never restore historical environmental state.
            app.state.analyses.clear()
            app.state.environmental_results.clear()
            app.state.analyses[result['analysis_id']] = result
            return result
        except ExtractionIncompleteError as exc:
            logging.getLogger(__name__).warning('Permit analysis incomplete: %s', exc.category)
            audit = exc.audit or {}
            return JSONResponse({
                'error': 'EXTRACTION_INCOMPLETE',
                'analysis_run_id': exc.analysis_id,
                'extracted_count': audit.get('extracted_count', 0),
                'candidate_count': audit.get('candidate_count', 0),
                'missing_count': audit.get('missing_count', 0),
                'missing_conditions': audit.get('missing_conditions', []),
                'message': 'Environmental extraction incomplete. Re-analysis or human review is required.',
            }, status_code=422)
        except Exception as exc:
            # Only safe category/type: never SDK exception messages or request payloads.
            logging.getLogger(__name__).error('Permit analysis failed: %s / %s', type(exc).__name__, getattr(exc, 'category', 'ANALYSIS_FAILED'))
            return JSONResponse({'error': 'Permit analysis could not be completed.'}, status_code=422)
        finally:
            app.state.busy = False

    build = Path(dist) if dist else root / 'frontend' / 'dist'
    if build.exists():
        app.mount('/assets', StaticFiles(directory=build / 'assets'), name='assets')
        @app.get('/')
        async def index(): return FileResponse(build / 'index.html', headers={'Cache-Control': 'no-store'})
    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8530)
    parser.add_argument('--mock', action='store_true', help='Explicit synthetic offline UI demonstration; never calls OpenAI')
    args = parser.parse_args()
    load_dotenv(ROOT / '.env')
    transport = None
    if args.mock:
        from .simple_fixture import mock_request
        transport = mock_request
    import uvicorn
    uvicorn.run(create_app(transport=transport), host='127.0.0.1', port=args.port)


if __name__ == '__main__': main()
