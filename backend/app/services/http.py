from __future__ import annotations

import re
import time
from typing import Any

import httpx

from app.config import HTTP_CONNECT_TIMEOUT_SECONDS, HTTP_READ_TIMEOUT_SECONDS

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
MAX_BODY_BYTES = 64 * 1024
USER_AGENT = (
    "Mozilla/5.0 (compatible; domain-processing-service/1.0; +https://localhost)"
)


class HttpError(Exception):
    def __init__(self, error_type: str, message: str):
        super().__init__(message)
        self.error_type = error_type
        self.message = message


def extract_title(html: str) -> str | None:
    match = TITLE_RE.search(html)
    if not match:
        return None
    title = re.sub(r"\s+", " ", match.group(1)).strip()
    return title or None


def _timeout() -> httpx.Timeout:
    return httpx.Timeout(
        connect=HTTP_CONNECT_TIMEOUT_SECONDS,
        read=HTTP_READ_TIMEOUT_SECONDS,
        write=HTTP_CONNECT_TIMEOUT_SECONDS,
        pool=HTTP_CONNECT_TIMEOUT_SECONDS,
    )


def _read_limited(response: httpx.Response) -> str:
    chunks: list[bytes] = []
    size = 0
    for chunk in response.iter_bytes():
        chunks.append(chunk)
        size += len(chunk)
        if size >= MAX_BODY_BYTES:
            break
    return b"".join(chunks).decode("utf-8", errors="replace")


def _get(url: str, *, follow_redirects: bool) -> dict[str, Any]:
    started = time.monotonic()
    with httpx.Client(
        timeout=_timeout(),
        follow_redirects=follow_redirects,
        headers={"User-Agent": USER_AGENT},
        verify=True,
    ) as client:
        with client.stream("GET", url) as response:
            body = _read_limited(response)
            title = None
            content_type = response.headers.get("content-type", "")
            if "html" in content_type.lower() or not content_type:
                title = extract_title(body)
            elapsed_ms = int((time.monotonic() - started) * 1000)
            return {
                "http_status": response.status_code,
                "title": title,
                "response_time_ms": elapsed_ms,
                "final_url": str(response.url),
            }


def _classify(url: str, exc: Exception) -> HttpError:
    if isinstance(exc, httpx.ConnectError):
        return HttpError("HTTP connection failed", f"Could not connect to {url}: {exc}")
    if isinstance(exc, httpx.TimeoutException):
        return HttpError("HTTP timeout", f"Timed out requesting {url}: {exc}")
    if isinstance(exc, httpx.HTTPError):
        return HttpError("HTTP error", f"HTTP request failed for {url}: {exc}")
    return HttpError("HTTP error", f"HTTP request failed for {url}: {exc}")


def fetch_http(domain: str) -> dict[str, Any]:
    last_error: HttpError | None = None

    for scheme in ("https", "http"):
        url = f"{scheme}://{domain}/"
        try:
            return _get(url, follow_redirects=True)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError) as follow_exc:
            last_error = _classify(url, follow_exc)
            try:
                return _get(url, follow_redirects=False)
            except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError) as direct_exc:
                last_error = _classify(url, direct_exc)

    if last_error:
        raise last_error
    raise HttpError("HTTP error", f"HTTP request failed for {domain}")
