from unittest.mock import patch

from app.services.dns import DnsError
from app.services.http import HttpError, extract_title
from app.services.domain_processor import process_domain


def test_title_extraction():
    html = "<html><head><title>  Example  Domain\n</title></head></html>"
    assert extract_title(html) == "Example Domain"
    assert extract_title("<html></html>") is None


def test_valid_domain_collects_dns_and_http():
    dns = {
        "records": {
            "A": ["93.184.216.34"],
            "TXT": ["v=spf1"],
            "CNAME": [],
            "MX": ["mail.example.com"],
            "NS": ["a.iana-servers.net"],
        },
        "ip_addresses": ["93.184.216.34"],
    }
    http = {"http_status": 200, "title": "Example Domain", "response_time_ms": 150}
    with (
        patch("app.services.domain_processor.lookup_dns", return_value=dns),
        patch("app.services.domain_processor.fetch_http", return_value=http),
    ):
        result = process_domain("example.com")
    assert result["success"] is True
    assert result["ip_addresses"] == ["93.184.216.34"]
    assert result["http_status"] == 200
    assert result["title"] == "Example Domain"
    assert result["response_time_ms"] == 150
    assert result["dns_records"]["NS"] == ["a.iana-servers.net"]


def test_invalid_or_missing_dns_fails():
    with patch(
        "app.services.domain_processor.lookup_dns",
        side_effect=DnsError("DNS resolution failed", "NXDOMAIN for invalid.example"),
    ):
        result = process_domain("invalid.example")
    assert result["success"] is False
    assert result["error_type"] == "DNS resolution failed"
    assert result["http_status"] is None


def test_dns_timeout():
    with patch(
        "app.services.domain_processor.lookup_dns",
        side_effect=DnsError("DNS timeout", "timed out"),
    ):
        result = process_domain("slow.example")
    assert result["error_type"] == "DNS timeout"
    assert result["success"] is False


def test_http_failure_keeps_dns():
    dns = {
        "records": {"A": ["1.2.3.4"], "TXT": [], "CNAME": [], "MX": [], "NS": []},
        "ip_addresses": ["1.2.3.4"],
    }
    with (
        patch("app.services.domain_processor.lookup_dns", return_value=dns),
        patch(
            "app.services.domain_processor.fetch_http",
            side_effect=HttpError("HTTP connection failed", "down"),
        ),
    ):
        result = process_domain("example.com")
    assert result["success"] is False
    assert result["ip_addresses"] == ["1.2.3.4"]
    assert result["error_type"] == "HTTP connection failed"


def test_http_timeout():
    dns = {
        "records": {"A": ["1.2.3.4"], "TXT": [], "CNAME": [], "MX": [], "NS": []},
        "ip_addresses": ["1.2.3.4"],
    }
    with (
        patch("app.services.domain_processor.lookup_dns", return_value=dns),
        patch(
            "app.services.domain_processor.fetch_http",
            side_effect=HttpError("HTTP timeout", "read timed out"),
        ),
    ):
        result = process_domain("example.com")
    assert result["error_type"] == "HTTP timeout"
