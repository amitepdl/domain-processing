from app.services.domain_normalize import DomainValidationError, normalize_domain, normalize_domains
import pytest


def test_trim_lower_and_trailing_dot():
    assert normalize_domain(" Google.com ") == "google.com"
    assert normalize_domain("google.com.") == "google.com"
    assert normalize_domain("GOOGLE.COM.") == "google.com"


def test_duplicates_removed_after_normalization():
    assert normalize_domains(["Google.com", " google.com", "google.com."]) == ["google.com"]


def test_rejects_empty():
    with pytest.raises(DomainValidationError):
        normalize_domain("   ")


def test_rejects_urls_and_paths():
    with pytest.raises(DomainValidationError):
        normalize_domain("https://google.com")
    with pytest.raises(DomainValidationError):
        normalize_domain("google.com/path")


def test_rejects_malformed():
    with pytest.raises(DomainValidationError):
        normalize_domain("not a domain")
    with pytest.raises(DomainValidationError):
        normalize_domain("-bad.com")
    with pytest.raises(DomainValidationError):
        normalize_domain("localhost")
