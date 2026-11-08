"""Startup warns when the listener is reachable without real authentication."""

import pytest

from free_claude_code.config.server_urls import network_exposure_warnings
from free_claude_code.config.settings import Settings


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1", "[::1]"])
def test_loopback_hosts_never_warn(host):
    assert network_exposure_warnings(Settings(host=host)) == ()


def test_open_listener_without_authentication_warns():
    (warning,) = network_exposure_warnings(Settings(host="0.0.0.0", port=9000))
    assert "0.0.0.0:9000" in warning
    assert "authentication is disabled" in warning


def test_open_listener_with_default_token_warns():
    (warning,) = network_exposure_warnings(
        Settings(host="0.0.0.0", proxy_auth_enabled=True)
    )
    assert "default API token" in warning


def test_open_listener_with_custom_token_does_not_warn():
    settings = Settings(
        host="0.0.0.0", proxy_auth_enabled=True, proxy_auth_token="unique-token"
    )
    assert network_exposure_warnings(settings) == ()
