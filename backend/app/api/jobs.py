from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.db import get_connection
from app.db.repository import (
    create_job_with_domains,
    get_job_with_results,
    list_jobs,
    serialize_job,
)
from app.rabbitmq.client import publish_domain_jobs
from app.schemas.job import CreateJobRequest
from app.services.domain_normalize import DomainValidationError, normalize_domains

router = APIRouter()


@router.post("/jobs")
def create_job(payload: CreateJobRequest) -> dict:
    try:
        domains = normalize_domains(payload.domains)
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not domains:
        raise HTTPException(status_code=400, detail="Domain list must not be empty")

    with get_connection() as conn:
        job = create_job_with_domains(conn, domains)

    to_publish = job.pop("to_publish", [])
    publish_domain_jobs(to_publish)
    serialized = serialize_job(job)
    return {"job_id": serialized["job_id"], "status": serialized["status"]}


@router.get("/jobs")
def get_jobs() -> list[dict]:
    with get_connection() as conn:
        jobs = list_jobs(conn)
    return [serialize_job(job) for job in jobs]


@router.get("/jobs/{job_id}")
def get_job(job_id: uuid.UUID) -> dict:
    with get_connection() as conn:
        job = get_job_with_results(conn, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return serialize_job(job)
