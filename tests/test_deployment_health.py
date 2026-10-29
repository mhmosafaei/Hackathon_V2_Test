"""Deployment smoke tests. No external API calls."""
from fastapi.testclient import TestClient
from src.permit.simple_api import create_app


def test_health_endpoint(tmp_path):
    with TestClient(create_app(root=tmp_path)) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_untrusted_origin_cannot_start_analysis(tmp_path, monkeypatch):
    monkeypatch.setenv("PERMITPULSE_ALLOWED_ORIGIN", "https://permitpulse.example")
    with TestClient(create_app(root=tmp_path)) as client:
        session = client.get("/api/session").json()
        response = client.post("/api/analyze", headers={
            "Origin": "https://attacker.example",
            "X-Session-Id": session["boot_id"],
            "Content-Type": "application/pdf",
        }, content=b"%PDF-1.4")
        assert response.status_code == 403
