# Asynchronous Domain Processing Service

Accepts a list of domains, processes DNS and HTTP lookups in the background, and exposes job progress through a REST API and a small web UI.

Stack: FastAPI, PostgreSQL, RabbitMQ, a Pika consumer, static HTML/JS. Everything starts with one Compose command.

## Architecture and major components

```text
Frontend → FastAPI → PostgreSQL (jobs, domains, job_domains)
                   → RabbitMQ (domain_processing)
                   → consumer(s) → PostgreSQL
```

| Component | Responsibility |
| --- | --- |
| Frontend | Submit domains, list jobs, poll details |
| Backend API | Validate input, persist jobs, publish work, serve status |
| PostgreSQL | Source of truth for job/domain state and results |
| RabbitMQ | Durable queue for domain work |
| Consumer | Claim a domain, DNS + HTTP, persist, ACK |

GET endpoints do not change job state. Counters are updated when a worker persists a terminal domain result.

## Key design decisions

- PostgreSQL is the source of truth; RabbitMQ is a durable work buffer (at-least-once delivery, manual ACK).
- One canonical `domains` row per hostname (`UNIQUE`) plus `job_domains`, so the same name across jobs is processed once and shared.
- Workers claim with a conditional `UPDATE` so two consumers cannot process the same row at once. Persist is `UPDATE … WHERE status = PROCESSING` so a redelivery cannot increment counters twice.
- DNS/HTTP run outside a DB transaction. Parallelism is extra consumer processes (`--scale consumer=3`), not threads inside Pika.
- Failed domains do not fail the job. The job is COMPLETED when every linked domain is COMPLETED or FAILED.

## Assumptions

- Input is hostnames, not URLs (`https://example.com/path` is rejected).
- Normalization: trim, lowercase, strip trailing dots, require a dotted hostname.
- HTTP 4xx/5xx still count as a successful probe (COMPLETED with `http_status`). Connect, timeout, and DNS failures are FAILED.
- HTTPS is tried first; HTTP is the fallback. Title is taken from HTML when present.
- Naive `created_at` from Postgres is treated as UTC in the UI (shown as IST).
- Compose credentials are for local use only.

## Known limitations

- No authentication.
- IPv6 (AAAA) is not collected.
- Title extraction is a regex, not a full HTML parser.
- A worker crash after claim can delay completion until stale reclaim (~45s).
- Publish happens after DB commit; a failed publish can leave a PENDING domain with no message.
- A previously FAILED or COMPLETED hostname is reused forever; a later job does not see that the site went down (or came back up).

## What I would improve with more time

- **Publish recovery:** if commit succeeds and publish does not, a periodic job can find `domains` still `PENDING` and publish them again. Duplicate messages are safe because claim is idempotent. Mark the **job** PROCESSING after a successful publish if you want; keep the **domain** PENDING until a worker claims it.
- **Metrics:** queue depth and DNS/HTTP lookup latency (no extra claim-conflict machinery).
- **Result freshness:** optional TTL (or “reprocess if `processed_at` older than X”) so a new job does not copy yesterday’s success after the site is down.
- **In-process concurrency:** a thread pool (or async I/O) sized to prefetch, with ACK still on the Pika connection thread.

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
