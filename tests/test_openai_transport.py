from src.documents.openai_transport import PROXY_ENVIRONMENT_NAMES, clean_connection_environment, direct_openai_client


def test_clean_connection_environment_removes_only_proxy_routing_variables():
    original = {
        "OPENAI_API_KEY": "secret-not-printed",
        "OPENAI_MODEL": "gpt-4.1-mini",
        "HTTP_PROXY": "http://127.0.0.1:9",
        "HTTPS_PROXY": "http://127.0.0.1:9",
        "ALL_PROXY": "http://127.0.0.1:9",
        "NO_PROXY": "localhost",
        "UNRELATED": "preserved",
    }
    result = clean_connection_environment(original)
    assert not (set(result) & PROXY_ENVIRONMENT_NAMES)
    assert result["OPENAI_API_KEY"] == original["OPENAI_API_KEY"]
    assert result["OPENAI_MODEL"] == "gpt-4.1-mini"
    assert result["NO_PROXY"] == "localhost"
    assert result["UNRELATED"] == "preserved"


def test_openai_client_uses_direct_tls_httpx_transport(monkeypatch):
    import httpx
    # Import before replacing ``httpx.Client``: the SDK defines its own
    # default Client subclass at module import time.
    from openai import OpenAI  # noqa: F401
    captured = {}
    real_client = httpx.Client

    class CapturingClient(real_client):
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)
            super().__init__(*args, **kwargs)

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(httpx, "Client", CapturingClient)
    client = direct_openai_client(timeout=5.0, max_retries=0)
    try:
        assert captured["trust_env"] is False
        assert captured["timeout"] == 5.0
    finally:
        client.close()
