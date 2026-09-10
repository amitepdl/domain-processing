const API_BASE = `${window.location.protocol}//${window.location.hostname}:8000`;

const app = document.getElementById("app");

function badge(status) {
  const value = (status || "").toLowerCase();
  return `<span class="badge ${value}">${value}</span>`;
}

async function api(path, options) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }
  if (!response.ok) {
    const detail = data && data.detail ? JSON.stringify(data.detail) : response.statusText;
    throw new Error(detail);
  }
  return data;
}

function renderCreate() {
  app.innerHTML = `
    <h1>Create job</h1>
    <p class="lead">Enter one domain per line. The API returns a job ID immediately; processing happens in the background.</p>
    <div class="panel">
      <label for="domains">Domains</label>
      <textarea id="domains" placeholder="example.com&#10;google.com&#10;invalid.example"></textarea>
      <button id="submit">Submit job</button>
      <div id="result"></div>
    </div>
  `;
  document.getElementById("submit").addEventListener("click", async () => {
    const button = document.getElementById("submit");
    const result = document.getElementById("result");
    const domains = document
      .getElementById("domains")
      .value.split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    button.disabled = true;
    result.innerHTML = "";
    try {
      const data = await api("/jobs", {
        method: "POST",
        body: JSON.stringify({ domains }),
      });
      result.innerHTML = `
        <div class="flash">
          Job created: <a class="mono" href="/jobs/${data.job_id}">${data.job_id}</a>
          ${badge(data.status)}
        </div>
      `;
    } catch (error) {
      result.innerHTML = `<div class="flash error">${error.message}</div>`;
    } finally {
      button.disabled = false;
    }
  });
}

function progress(job) {
  const done = job.completed_domains + job.failed_domains;
  return `${done} / ${job.total_domains} (${job.completed_domains} ok, ${job.failed_domains} failed)`;
}

async function renderJobs() {
  app.innerHTML = `<h1>Jobs</h1><p class="lead">Latest jobs first.</p><div class="panel">Loading…</div>`;
  try {
    const jobs = await api("/jobs");
    if (!jobs.length) {
      app.innerHTML = `<h1>Jobs</h1><div class="panel">No jobs yet.</div>`;
      return;
    }
    app.innerHTML = `
      <h1>Jobs</h1>
      <p class="lead">Latest jobs first.</p>
      <div class="panel">
        <table>
          <thead>
            <tr>
              <th>Job ID</th>
              <th>Created</th>
              <th>Status</th>
              <th>Progress</th>
            </tr>
          </thead>
          <tbody>
            ${jobs
              .map(
                (job) => `
              <tr>
                <td><a class="mono" href="/jobs/${job.job_id}">${job.job_id}</a></td>
                <td>${escapeHtml(formatCreatedAt(job.created_at))}</td>
                <td>${badge(job.status)}</td>
                <td>${progress(job)}</td>
              </tr>`
              )
              .join("")}
          </tbody>
        </table>
      </div>
    `;
  } catch (error) {
    app.innerHTML = `<div class="flash error">${error.message}</div>`;
  }
}

function formatCreatedAt(value) {
  if (!value) return "—";
  const iso = /Z$|[+-]\d{2}:\d{2}$/.test(value) ? value : `${value}Z`;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return String(value);
  const formatted = new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  }).format(date);
  return `${formatted} IST`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function domainCard(item, dnsOpen) {
  const error = item.error
    ? `<div class="kv">Error: ${escapeHtml(item.error.type || "")} — ${escapeHtml(item.error.message || "")}</div>`
    : "";
  const openAttr = dnsOpen ? " open" : "";
  return `
    <article class="card">
      <h3>${escapeHtml(item.domain)} ${badge(item.status)}</h3>
      <div class="kv">IP addresses: ${escapeHtml((item.ip_addresses || []).join(", ") || "—")}</div>
      <div class="kv">HTTP status: ${item.http_status ?? "—"}</div>
      <div class="kv">Title: ${escapeHtml(item.title || "—")}</div>
      <div class="kv">Response time: ${item.response_time_ms != null ? `${item.response_time_ms} ms` : "—"}</div>
      ${error}
      <details class="dns" data-domain="${escapeHtml(item.domain)}"${openAttr}>
        <summary>DNS records</summary>
        <pre>${escapeHtml(JSON.stringify(item.dns || {}, null, 2))}</pre>
      </details>
    </article>
  `;
}

let pollTimer = null;
let jobDomainFilter = "all";

function matchingResults(results) {
  if (jobDomainFilter === "completed") {
    return results.filter((item) => item.status === "completed");
  }
  if (jobDomainFilter === "failed") {
    return results.filter((item) => item.status === "failed");
  }
  return results;
}

function collectOpenDns() {
  return new Set(
    [...document.querySelectorAll("details.dns[open]")].map((el) => el.dataset.domain)
  );
}

function bindJobDetails(job) {
  document.querySelectorAll("[data-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      jobDomainFilter = button.dataset.filter;
      paintJob(job, collectOpenDns());
    });
  });
}

function paintJob(job, openDns) {
  const results = job.results || [];
  const visible = matchingResults(results);
  const empty =
    results.length && !visible.length
      ? `<div class="panel empty">No ${jobDomainFilter} domains in this job.</div>`
      : "";
  app.innerHTML = `
    <h1>Job details</h1>
    <p class="meta">
      <span class="mono">${escapeHtml(job.job_id)}</span>
      ${badge(job.status)}
      &nbsp; Created ${escapeHtml(formatCreatedAt(job.created_at))}
      &nbsp; Progress ${progress(job)}
    </p>
    <div class="toolbar">
      <div class="filters" role="tablist" aria-label="Filter domains by status">
        <button type="button" data-filter="all" class="${jobDomainFilter === "all" ? "active" : ""}">All</button>
        <button type="button" data-filter="completed" class="${jobDomainFilter === "completed" ? "active" : ""}">Completed</button>
        <button type="button" data-filter="failed" class="${jobDomainFilter === "failed" ? "active" : ""}">Failed</button>
      </div>
      <div class="filter-count">Showing ${visible.length} of ${results.length}</div>
    </div>
    <div class="grid">
      ${visible.map((item) => domainCard(item, openDns.has(item.domain))).join("")}
      ${empty}
    </div>
  `;
  bindJobDetails(job);
}

async function renderJob(jobId) {
  try {
    const openDns = collectOpenDns();
    const job = await api(`/jobs/${jobId}`);
    paintJob(job, openDns);
    const active = job.status === "pending" || job.status === "processing";
    if (active) {
      pollTimer = setTimeout(() => renderJob(jobId), 2000);
    }
  } catch (error) {
    app.innerHTML = `<div class="flash error">${escapeHtml(error.message)}</div>`;
  }
}

function route() {
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
  jobDomainFilter = "all";
  const path = window.location.pathname.replace(/\/$/, "") || "/";
  if (path === "/") {
    renderCreate();
    return;
  }
  if (path === "/jobs") {
    renderJobs();
    return;
  }
  const match = path.match(/^\/jobs\/([^/]+)$/);
  if (match) {
    renderJob(match[1]);
    return;
  }
  app.innerHTML = `<div class="panel">Not found.</div>`;
}

window.addEventListener("popstate", route);
document.addEventListener("click", (event) => {
  const link = event.target.closest("a");
  if (!link || link.target === "_blank" || link.origin !== window.location.origin) return;
  event.preventDefault();
  history.pushState({}, "", link.pathname);
  route();
});

route();
