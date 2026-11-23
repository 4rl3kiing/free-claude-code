"""Launchers start fast: importing one must not load the HTTP client stack."""

import subprocess
import sys

import pytest

LAUNCHERS = (
    "claude",
    "codex",
    "pi",
    "opencode",
    "cline",
    "hermes",
    "dsh",
    "grok",
    "muse",
    "agy",
)


@pytest.mark.parametrize("launcher", LAUNCHERS)
def test_launcher_import_does_not_load_httpx(launcher: str) -> None:
    code = (
        f"import sys, free_claude_code.cli.launchers.{launcher}; "
        "print(sorted(m for m in ('httpx', 'rich') if m in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    assert result.stdout.strip() == "[]"


def test_proxy_validation_still_rejects_bad_urls() -> None:
    from free_claude_code.config.provider_proxies import (
        PROVIDER_PROXY_ENV_KEYS,
        invalid_provider_proxy_keys,
    )

    assert invalid_provider_proxy_keys({}) == ()
    key = PROVIDER_PROXY_ENV_KEYS[0]
    assert invalid_provider_proxy_keys({key: "http://"}) == (key,)
    assert invalid_provider_proxy_keys({key: "socks5://127.0.0.1:1080"}) == ()
