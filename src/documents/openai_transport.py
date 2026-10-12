"""Direct, TLS-verified OpenAI client construction for PermitPulse.

The desktop execution environment can inherit diagnostic proxy variables.  Live
PermitPulse calls must not route a permit through an unrelated local proxy, so
the SDK's ``httpx`` transport deliberately ignores environment proxy settings.
This does not weaken certificate verification or mutate process/global state.
"""
from __future__ import annotations

import os
from typing import Mapping


TRANSPORT_VERSION = "direct-https-v1"


PROXY_ENVIRONMENT_NAMES = frozenset({
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
    "http_proxy", "https_proxy", "all_proxy",
})


def clean_connection_environment(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return a child-process environment with only proxy routing removed."""
    source = os.environ if environ is None else environ
    return {key: value for key, value in source.items() if key not in PROXY_ENVIRONMENT_NAMES}


def direct_openai_client(*, timeout: float, max_retries: int):
    """Build an SDK client that uses direct HTTPS with normal TLS validation."""
    import httpx
    from openai import OpenAI

    # ``trust_env=False`` excludes HTTP(S)_PROXY/ALL_PROXY only for this
    # connection. httpx continues to verify the OpenAI TLS certificate.
    return OpenAI(
        timeout=timeout,
        max_retries=max_retries,
        http_client=httpx.Client(timeout=timeout, trust_env=False),
    )
