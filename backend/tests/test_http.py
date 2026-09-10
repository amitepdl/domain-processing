from unittest.mock import patch

import httpx

from app.services.http import fetch_http


def test_timeout_following_redirects_falls_back_to_direct_status():
    calls = {"n": 0}

    def fake_get(url, *, follow_redirects):
        calls["n"] += 1
        if follow_redirects:
            raise httpx.ReadTimeout("timed out")
        return {
            "http_status": 301,
            "title": None,
            "response_time_ms": 40,
            "final_url": url,
        }

    with patch("app.services.http._get", side_effect=fake_get):
        result = fetch_http("adobe.com")
    assert result["http_status"] == 301
    assert calls["n"] == 2
