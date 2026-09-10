from unittest.mock import MagicMock, patch

import dns.exception
import dns.resolver

from app.services.dns import lookup_dns


class _FakeAnswer(list):
    pass


def test_lookup_continues_when_one_type_gets_servfail():
    def resolve(domain, record_type):
        if record_type == "TXT":
            raise dns.resolver.NoNameservers(
                request=MagicMock(question="google.com IN TXT"),
                errors=[],
            )
        if record_type == "CNAME":
            raise dns.resolver.NoAnswer(response=MagicMock())
        if record_type == "A":
            return _FakeAnswer(["93.184.216.34"])
        if record_type == "MX":
            return _FakeAnswer(["10 mail.example.com."])
        if record_type == "NS":
            return _FakeAnswer(["ns.example.com."])
        raise AssertionError(record_type)

    resolver = MagicMock()
    resolver.resolve.side_effect = resolve
    with patch("app.services.dns._resolvers", return_value=[resolver]):
        result = lookup_dns("example.com")
    assert result["ip_addresses"] == ["93.184.216.34"]
    assert result["records"]["TXT"] == []
    assert result["records"]["A"] == ["93.184.216.34"]


def test_lookup_timeout_all_types_fails():
    resolver = MagicMock()
    resolver.resolve.side_effect = dns.exception.Timeout()
    with patch("app.services.dns._resolvers", return_value=[resolver]):
        try:
            lookup_dns("slow.example")
            raised = None
        except Exception as exc:
            raised = exc
    assert raised is not None
    assert raised.error_type == "DNS timeout"
