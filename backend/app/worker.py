from __future__ import annotations

import logging
import time
import uuid

from app.config import RETRY_INTERVAL_SECONDS
from app.db import get_connection
from app.db.repository import get_domain, persist_domain_result, try_claim_domain
from app.services.domain_processor import process_domain

logger = logging.getLogger("consumer")

CLAIM_RETRY_SECONDS = 2
CLAIM_RETRY_ATTEMPTS = 30


def handle_message(payload: dict) -> None:
    domain_id = uuid.UUID(payload["domain_id"])
    domain_name = payload["domain"]
    logger.info("Received work for %s", domain_name)

    claimed = None
    for attempt in range(CLAIM_RETRY_ATTEMPTS):
        with get_connection() as conn:
            existing = get_domain(conn, domain_id)
            if existing is None:
                logger.info("Domain %s not visible yet, waiting", domain_id)
            elif existing["status"] in ("COMPLETED", "FAILED"):
                logger.info("Domain %s already terminal (%s)", domain_name, existing["status"])
                return
            else:
                claimed = try_claim_domain(conn, domain_id)
                if claimed:
                    break
        time.sleep(CLAIM_RETRY_SECONDS if attempt else RETRY_INTERVAL_SECONDS)

    if not claimed:
        with get_connection() as conn:
            existing = get_domain(conn, domain_id)
        if existing and existing["status"] in ("COMPLETED", "FAILED"):
            return
        raise RuntimeError(f"Could not claim domain {domain_name}")

    result = process_domain(domain_name)
    with get_connection() as conn:
        persisted = persist_domain_result(
            conn,
            domain_id,
            success=result["success"],
            ip_addresses=result["ip_addresses"],
            dns_records=result["dns_records"],
            http_status=result["http_status"],
            title=result["title"],
            response_time_ms=result["response_time_ms"],
            error_type=result["error_type"],
            error_message=result["error_message"],
        )
    logger.info(
        "Finished %s success=%s persisted=%s error=%s",
        domain_name,
        result["success"],
        persisted,
        result["error_type"],
    )
