from __future__ import annotations

from unittest.mock import patch
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.jobs import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_malformed_request_missing_body():
    response = client.post("/jobs", json={})
    assert response.status_code == 422


def test_empty_domain_list():
    response = client.post("/jobs", json={"domains": []})
    assert response.status_code == 422


def test_malformed_domain_is_rejected():
    response = client.post("/jobs", json={"domains": ["https://google.com"]})
    assert response.status_code == 400


def test_unknown_job(db):
    response = client.get("/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@patch("app.api.jobs.publish_domain_jobs")
def test_create_job_and_get_job(publish, db):
    response = client.post(
        "/jobs",
        json={"domains": ["Example.com", " example.com ", "example.com."]},
    )
    assert response.status_code == 200
    body = response.json()
    assert UUID(body["job_id"])
    assert body["status"] == "pending"
    publish.assert_called_once()
    published = publish.call_args[0][0]
    assert len(published) == 1
    assert published[0]["domain"] == "example.com"

    listed = client.get("/jobs")
    assert listed.status_code == 200
    assert listed.json()[0]["job_id"] == body["job_id"]
    assert listed.json()[0]["total_domains"] == 1

    detail = client.get(f"/jobs/{body['job_id']}")
    assert detail.status_code == 200
    assert detail.json()["results"][0]["domain"] == "example.com"
    assert detail.json()["results"][0]["status"] == "pending"


@patch("app.api.jobs.publish_domain_jobs")
def test_get_jobs_sorted_by_created_at_desc(publish, db):
    first = client.post("/jobs", json={"domains": ["first-sort.example.test"]}).json()
    second = client.post("/jobs", json={"domains": ["second-sort.example.test"]}).json()
    jobs = client.get("/jobs").json()
    ids = [job["job_id"] for job in jobs]
    assert ids.index(second["job_id"]) < ids.index(first["job_id"])
    assert publish.call_count == 2
