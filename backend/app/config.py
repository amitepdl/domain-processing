import os


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://domain:domain@localhost:5432/domain",
)

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = _int("RABBITMQ_PORT", 5672)
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "domain")
RABBITMQ_PASSWORD = os.environ.get("RABBITMQ_PASSWORD", "domain")
RABBITMQ_QUEUE = os.environ.get("RABBITMQ_QUEUE", "domain_processing")
RABBITMQ_PREFETCH = _int("RABBITMQ_PREFETCH", 10)

DNS_TIMEOUT_SECONDS = _int("DNS_TIMEOUT_SECONDS", 5)
HTTP_CONNECT_TIMEOUT_SECONDS = _int("HTTP_CONNECT_TIMEOUT_SECONDS", 5)
HTTP_READ_TIMEOUT_SECONDS = _int("HTTP_READ_TIMEOUT_SECONDS", 10)
CLAIM_STALE_SECONDS = _int("CLAIM_STALE_SECONDS", 45)

RETRY_INTERVAL_SECONDS = float(os.environ.get("RETRY_INTERVAL_SECONDS", "1.5"))
RETRY_MAX_ATTEMPTS = _int("RETRY_MAX_ATTEMPTS", 40)
