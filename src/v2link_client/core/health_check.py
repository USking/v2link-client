"""Connectivity checks for the running core.

We treat the core as "online" when an HTTPS request succeeds *through* the local
HTTP proxy inbound. This validates both:
- the local core is reachable, and
- the outbound tunnel can reach the internet.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Sequence
import urllib.error
import urllib.request


DEFAULT_TEST_URLS: tuple[str, ...] = (
    # Small, fast endpoints intended for connectivity checking.
    "https://www.gstatic.com/generate_204",
    "https://1.1.1.1/cdn-cgi/trace",
)


@dataclass(frozen=True, slots=True)
class ProxyHealthResult:
    ok: bool
    checked_url: str | None
    status_code: int | None
    latency_ms: int | None
    error: str | None


def check_http_proxy(
    proxy_host: str,
    proxy_port: int,
    *,
    urls: Sequence[str] = DEFAULT_TEST_URLS,
    timeout_s: float = 4.0,
) -> ProxyHealthResult:
    proxy_url = f"http://{proxy_host}:{proxy_port}"
    handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
    opener = urllib.request.build_opener(handler)

    last_error: str | None = None
    for url in urls:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "v2link-client/0.1"},
            method="GET",
        )
        started = time.monotonic()
        try:
            with opener.open(request, timeout=timeout_s) as response:
                status = getattr(response, "status", None)
                # Read a byte so the request fully completes for endpoints with a body.
                try:
                    response.read(1)
                except Exception:
                    # Some responses may not be readable; ignore as long as the
                    # connection/proxying succeeded.
                    pass
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
            continue

        latency_ms = int((time.monotonic() - started) * 1000)
        ok = status is None or 200 <= int(status) < 400
        return ProxyHealthResult(
            ok=ok,
            checked_url=url,
            status_code=int(status) if status is not None else None,
            latency_ms=latency_ms,
            error=None if ok else f"HTTP {status}",
        )

    return ProxyHealthResult(
        ok=False,
        checked_url=urls[-1] if urls else None,
        status_code=None,
        latency_ms=None,
        error=last_error or "Unknown error",
    )

