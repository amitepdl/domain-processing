# Asynchronous Domain Processing Service

Accepts a list of domains, processes DNS and HTTP lookups in the background, and exposes job progress through a REST API and a small web UI.

Stack: FastAPI, PostgreSQL, RabbitMQ, a Pika consumer, static HTML/JS. Everything starts with one Compose command.

## Run locally

Prerequisites: Docker Compose v2.

```bash
cp .env.example .env   # optional; Compose has defaults
docker compose up --build
```

| Service | URL |
| --- | --- |
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| RabbitMQ AMQP | localhost:5672 |
| RabbitMQ management | http://localhost:15672 (user/password `domain` / `domain`) |
| PostgreSQL | localhost:5432 |

Then: open the frontend, submit domains, get a job id immediately, watch the job list and details (polling while the job is in progress).

More consumers:

```bash
docker compose up --build --scale consumer=3
```

`docker compose down` keeps Postgres and RabbitMQ volumes. `docker compose down -v` deletes them.

Backend and consumer wait for Postgres/RabbitMQ, apply schema on startup, and retry broker connections.

## Services

| Service | Role |
| --- | --- |
| Frontend (`:3000`) | Create job, list jobs, job details |
| Backend (`:8000`) | REST API, persist jobs, publish work |
| PostgreSQL | Job state, canonical domains, results |
| RabbitMQ | Durable `domain_processing` queue |
| Consumer | Claim a domain, DNS/HTTP, persist, ACK |

## API

Create a job (returns immediately):

```bash
curl -s http://localhost:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{"domains":["example.com","google.com","Example.com","invalid.example"]}'
```

```json
{ "job_id": "…", "status": "pending" }
```

List jobs (`created_at` descending):

```bash
curl -s http://localhost:8000/jobs
```

Job details:

```bash
curl -s http://localhost:8000/jobs/<job_id>
```

Health:

```bash
curl -s http://localhost:8000/health
```

Duplicate hostnames in one request are normalized and collapsed. The same hostname across jobs shares one stored result.

## Tests

```bash
python -m pytest
```

Unit tests run without Postgres. Integration tests (API + worker + counters) run when Postgres is reachable via `DATABASE_URL`.

## Layout

```text
backend/     FastAPI app, domain processor, DB, RabbitMQ helpers, tests
consumer/    worker entrypoint
frontend/    static UI
docker-compose.yml
```
