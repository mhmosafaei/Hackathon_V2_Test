"""Loopback React host. No active analysis is restored or shared between sessions."""
import argparse
import asyncio
import logging
from pathlib import Path
from uuid import uuid4
from urllib.parse import unquote

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from .simple_analysis import analyze

ROOT = Path(__file__).resolve().parents[2]


def create_app(root=ROOT, *, transport=None, dist=None):
    app = FastAPI(docs_url=None, redoc_url=None)
    app.state.boot_id = uuid4().hex
    app.state.busy = False

    @app.get('/api/session')
    async def session():
        return {'boot_id': app.state.boot_id, 'mode': 'MOCK' if transport else 'LIVE'}

    @app.post('/api/analyze')
    async def run(request: Request):
        # Same-origin, no CORS; stale browser sessions cannot dispatch after restart.
        origin = request.headers.get('origin')
        if origin and origin != str(request.base_url).rstrip('/'):
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
        try:
            result = await asyncio.to_thread(analyze, bytes(chunks), unquote(request.headers.get('x-filename', 'permit.pdf')), root, transport=transport)
            return result
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
