"""
HTTP client factory for standardized AsyncClient configuration
"""
import httpx


def get_async_client(
    timeout: float = 10.0,
    max_connections: int = 100,
    max_keepalive: int = 10
) -> httpx.AsyncClient:
    """
    Return an AsyncClient with HTTP/2 support, connection limits, and default timeout.

    Args:
        timeout: request timeout in seconds
        max_connections: maximum number of connections
        max_keepalive: maximum number of keep-alive connections
    """
    limits = httpx.Limits(max_keepalive_connections=max_keepalive, max_connections=max_connections)
    try:
        # Try to enable HTTP/2; if h2 package is missing, fall back
        return httpx.AsyncClient(http2=True, limits=limits, timeout=timeout)
    except ImportError:
        return httpx.AsyncClient(http2=False, limits=limits, timeout=timeout) 