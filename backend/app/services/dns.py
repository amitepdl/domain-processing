from __future__ import annotations

from typing import Any

import dns.exception
import dns.resolver

from app.config import DNS_TIMEOUT_SECONDS

RECORD_TYPES = ("A", "TXT", "CNAME", "MX", "NS")
FALLBACK_NAMESERVERS = ["8.8.8.8", "1.1.1.1"]


class DnsError(Exception):
    def __init__(self, error_type: str, message: str):
        super().__init__(message)
        self.error_type = error_type
        self.message = message


def _make_resolver(nameservers: list[str] | None = None) -> dns.resolver.Resolver:
    if nameservers is None:
        resolver = dns.resolver.Resolver()
    else:
        resolver = dns.resolver.Resolver(configure=False)
        resolver.nameservers = nameservers
    resolver.lifetime = DNS_TIMEOUT_SECONDS
    resolver.timeout = DNS_TIMEOUT_SECONDS
    return resolver


def _resolvers() -> list[dns.resolver.Resolver]:
    return [
        _make_resolver(),
        _make_resolver(FALLBACK_NAMESERVERS),
    ]


def _resolve_type(domain: str, record_type: str) -> list[str]:
    last_error: Exception | None = None
    for resolver in _resolvers():
        try:
            answer = resolver.resolve(domain, record_type)
            return sorted(str(item).rstrip(".") for item in answer)
        except dns.resolver.NoAnswer:
            return []
        except dns.resolver.NXDOMAIN:
            raise
        except dns.resolver.YXDOMAIN:
            raise
        except (dns.resolver.NoNameservers, dns.exception.Timeout) as exc:
            last_error = exc
    if isinstance(last_error, dns.exception.Timeout):
        raise last_error
    return []


def lookup_dns(domain: str) -> dict[str, Any]:
    records: dict[str, list[str]] = {record_type: [] for record_type in RECORD_TYPES}
    resolved_any = False
    timed_out = False
    nxdomain = False

    for record_type in RECORD_TYPES:
        try:
            values = _resolve_type(domain, record_type)
            records[record_type] = values
            if values:
                resolved_any = True
        except dns.resolver.NXDOMAIN:
            nxdomain = True
            break
        except dns.resolver.YXDOMAIN as exc:
            raise DnsError("DNS resolution failed", str(exc)) from exc
        except dns.exception.Timeout:
            timed_out = True

    if nxdomain and not resolved_any:
        raise DnsError("DNS resolution failed", f"NXDOMAIN for {domain}")

    if not resolved_any:
        if timed_out:
            raise DnsError("DNS timeout", f"DNS lookup timed out for {domain}")
        raise DnsError("DNS resolution failed", f"No DNS records found for {domain}")

    return {
        "records": records,
        "ip_addresses": records.get("A", []),
    }
