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


def test_private_demo_requires_authentication(tmp_path, monkeypatch):
    import base64
    monkeypatch.setenv("PERMITPULSE_PRIVATE_DEMO", "1")
    monkeypatch.setenv("PERMITPULSE_DEMO_USERNAME", "operator")
    monkeypatch.setenv("PERMITPULSE_DEMO_PASSWORD", "strong-demo-password")
    with TestClient(create_app(root=tmp_path)) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/session").status_code == 401
        assert client.get("/api/session", headers={"Authorization": "Basic invalid"}).status_code == 401
        wrong = base64.b64encode(b"operator:wrong").decode()
        assert client.get("/api/session", headers={"Authorization": "Basic " + wrong}).status_code == 401
        valid = base64.b64encode(b"operator:strong-demo-password").decode()
        assert client.get("/api/session", headers={"Authorization": "Basic " + valid}).status_code == 200


def test_private_demo_fails_closed_without_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("PERMITPULSE_PRIVATE_DEMO", "1")
    monkeypatch.delenv("PERMITPULSE_DEMO_USERNAME", raising=False)
    monkeypatch.delenv("PERMITPULSE_DEMO_PASSWORD", raising=False)
    with TestClient(create_app(root=tmp_path)) as client:
        assert client.get("/api/session").status_code == 503
