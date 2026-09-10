from __future__ import annotations

from typing import Any

from app.services.dns import DnsError, lookup_dns
from app.services.http import HttpError, fetch_http


def process_domain(domain: str) -> dict[str, Any]:
    """Collect DNS and HTTP data for a normalized hostname.

    Isolated from queue and database concerns so it can be unit-tested.
    """
    result: dict[str, Any] = {
        "domain": domain,
        "success": False,
        "ip_addresses": [],
        "dns_records": {},
        "http_status": None,
        "title": None,
        "response_time_ms": None,
        "error_type": None,
        "error_message": None,
    }

    try:
        dns_data = lookup_dns(domain)
    except DnsError as exc:
        result["error_type"] = exc.error_type
        result["error_message"] = exc.message
        return result

    result["dns_records"] = dns_data["records"]
    result["ip_addresses"] = dns_data["ip_addresses"]

    try:
        http_data = fetch_http(domain)
    except HttpError as exc:
        result["error_type"] = exc.error_type
        result["error_message"] = exc.message
        return result

    result["http_status"] = http_data["http_status"]
    result["title"] = http_data["title"]
    result["response_time_ms"] = http_data["response_time_ms"]
    result["success"] = True
    return result
