CREATE TYPE job_status AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED');
CREATE TYPE domain_status AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED');

CREATE TABLE jobs (
    id UUID PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    status job_status NOT NULL DEFAULT 'PENDING',
    total_domains INTEGER NOT NULL,
    completed_domains INTEGER NOT NULL DEFAULT 0,
    failed_domains INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE domains (
    id UUID PRIMARY KEY,
    domain VARCHAR NOT NULL UNIQUE,
    status domain_status NOT NULL DEFAULT 'PENDING',
    ip_addresses JSONB,
    dns_records JSONB,
    http_status INTEGER,
    title TEXT,
    response_time_ms INTEGER,
    error_type VARCHAR,
    error_message TEXT,
    processed_at TIMESTAMP,
    claimed_at TIMESTAMP
);

CREATE TABLE job_domains (
    job_id UUID NOT NULL REFERENCES jobs(id),
    domain_id UUID NOT NULL REFERENCES domains(id),
    PRIMARY KEY (job_id, domain_id)
);

CREATE INDEX idx_jobs_created_at ON jobs (created_at DESC);
CREATE INDEX idx_job_domains_domain_id ON job_domains (domain_id);
