"""Browser-friendly local server URLs shared by runtime and launchers."""

from urllib.parse import urlsplit

from free_claude_code.config.settings import Settings


def _browser_host_for_local_urls(settings: Settings) -> str:
    """Host fragment for URLs shown to humans on the same machine as the server."""

    host = settings.host.strip() if settings.host else "127.0.0.1"
    if host in {"0.0.0.0", "::", "[::]"}:
        host = "127.0.0.1"
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return host


def local_proxy_root_url(settings: Settings) -> str:
    """Return the proxy root URL (no path) for clients on the same machine."""

    return f"http://{_browser_host_for_local_urls(settings)}:{settings.port}"


def local_admin_url(settings: Settings) -> str:
    """Return a browser-friendly URL for the localhost-only admin UI."""

    return f"{local_proxy_root_url(settings)}/admin"


def same_proxy_url(value: object, expected: str) -> bool:
    """Compare client endpoints, allowing equivalent loopback names and trailing slashes."""
    if not isinstance(value, str):
        return False

    def normalized(url: str) -> tuple[str, str | None, int | None, str]:
        parsed = urlsplit(url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Unexpected URL components")
        host = parsed.hostname
        if host in {"localhost", "127.0.0.1", "::1"}:
            host = "localhost"
        return parsed.scheme, host, parsed.port, parsed.path.rstrip("/")

    try:
        return normalized(value) == normalized(expected)
    except ValueError:
        return False


def proxy_v1_url(proxy_root_url: str) -> str:
    """Return the canonical local proxy API root for client launchers."""

    stripped = proxy_root_url.rstrip("/")
    return stripped if stripped.endswith("/v1") else f"{stripped}/v1"


_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "[::1]", "localhost"})
DEFAULT_PROXY_AUTH_TOKEN = "freecc"


def network_exposure_warnings(settings: Settings) -> tuple[str, ...]:
    """Explain risky listener settings; empty when the server is loopback-only."""

    host = (settings.host or "").strip().lower()
    if host in _LOOPBACK_HOSTS:
        return ()
    listener = f"{settings.host}:{settings.port}"
    if not settings.proxy_auth_enabled:
        return (
            f"FCC is listening on {listener}, which other machines on the network "
            "can reach, and API authentication is disabled. Anyone who can connect "
            "can spend your provider keys. Enable Require API Authentication in "
            "Admin or set HOST=127.0.0.1.",
        )
    if settings.proxy_auth_token == DEFAULT_PROXY_AUTH_TOKEN:
        return (
            f"FCC is listening on {listener} with the default API token "
            f"'{DEFAULT_PROXY_AUTH_TOKEN}'. Set a unique API/CLI Auth Token in "
            "Admin or set HOST=127.0.0.1.",
        )
    return ()
