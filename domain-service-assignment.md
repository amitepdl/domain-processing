# Backend Coding Assignment: Asynchronous Domain Processing Service

## Objective

Build a small backend service that accepts a list of domains, processes them asynchronously, and allows users to retrieve the processing status and results.

The goal of this exercise is to understand how you approach backend design, problem solving, error handling, asynchronous processing, and engineering trade-offs. Prioritize the areas you consider most important and document any decisions, assumptions, or limitations.

## Requirements

### 1. Submit a Processing Job

Provide an API to submit one or more domains for processing.

Example request:

```http
POST /jobs
```

```json
{
  "domains": [
    "example.com",
    "google.com",
    "invalid.example"
  ]
}
```

The API should return a unique job ID without waiting for all domains to be processed.

Example:

```json
{
  "job_id": "abc123",
  "status": "pending"
}
```

### 2. Process Domains Asynchronously

Each domain should be processed independently in the background.

For every domain, collect at least the following information:

* Resolved IP address(es), if available
* DNS records (A, TXT, CNAME, MX, NS)
* HTTP/HTTPS response status
* Page title, if available
* Response time

You may collect additional information if you believe it is useful, but this is not required.

The API request that creates the job should not remain blocked while the processing is taking place.

### 3. Retrieve Job Status and Results

Provide an API to retrieve the current status and results of a submitted job.

Example:

```http
GET /jobs/{job_id}
```

A response could look similar to:

```json
{
  "job_id": "abc123",
  "status": "in_progress",
  "results": [
    {
      "domain": "example.com",
      "status": "completed",
      "ip_addresses": ["93.184.216.34"],
      "http_status": 200,
      "title": "Example Domain",
      "response_time_ms": 150,
      "dns": {}
    },
    {
      "domain": "invalid.example",
      "status": "failed",
      "error": "DNS resolution failed"
    }
  ]
}
```

The exact response structure is up to you.

## Expected Behavior

The service should behave reasonably when:

* A domain is malformed
* A domain does not resolve
* A remote server is unavailable
* A request takes too long
* The same domain is submitted more than once
* Some domains in a job succeed while others fail

You are free to decide how these scenarios should be handled.

## Technical Guidelines

* Use **Python** for the implementation.
* You may choose any Python web framework, libraries, database, queue, or supporting components you consider appropriate.
* Keep the solution reasonably easy to run locally.
* Do not over-engineer the solution for the sake of the assignment.

You may make reasonable assumptions where requirements are not explicitly defined. Please document those assumptions.

## Testing

Include tests for the areas you consider important.

We are more interested in what you choose to test and why than in achieving a particular code coverage percentage.

## Deliverables

Please submit:

* Source code
* Instructions to run the application locally
* API usage examples
* Tests
* A short README covering:
  * Architecture and major components
  * Key design decisions
  * Assumptions made
  * Known limitations
  * What you would improve if you had more time

## Use of External Resources

You are free to use any tool at your disposal. Please be prepared to discuss your implementation and explain the major decisions made during development. There is no single expected architecture or technology choice. We are interested in understanding how you approach the problem and why you made the decisions you did.
