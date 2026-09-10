from __future__ import annotations

import re

DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[a-z0-9-]{1,63}(?<!-)(?:\.(?!-)[a-z0-9-]{1,63}(?<!-))+$"
)


class DomainValidationError(ValueError):
    pass


def normalize_domain(value: str) -> str:
    if value is None:
        raise DomainValidationError("Domain must be a string")
    if not isinstance(value, str):
        raise DomainValidationError("Domain must be a string")

    candidate = value.strip().lower()
    if not candidate:
        raise DomainValidationError("Domain must not be empty")
    if "://" in candidate or "/" in candidate or " " in candidate:
        raise DomainValidationError(f"Not a valid domain: {value}")

    candidate = candidate.rstrip(".")
    if candidate.endswith("."):
        candidate = candidate.rstrip(".")

    if not DOMAIN_RE.match(candidate):
        raise DomainValidationError(f"Malformed domain: {value}")
    return candidate


def normalize_domains(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        normalized = normalize_domain(value)
        if normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique
