# Agent Jobs — Architecture, Flow & How to Add New Ones

The agent is a small Flask app running on every bench server. Press communicates with it via HTTP. This doc covers the full request→execution→callback flow and how to add a new job.

---

## Architecture Overview

```
Press (Frappe)                         Agent (Flask on bench host)
──────────────────────────────────────────────────────────────────

AgentJob doc created
  ├─ job_type: "New Site"
  ├─ request_path: "/benches/{bench}/sites"
  ├─ request_data: {config, apps, passwords}
  └─ status: "Undelivered"
         │
         ▼ enqueue_http_request()
    Agent.request()
    → HTTP POST to agent
         │
         ▼ Flask route in web.py
    POST /benches/<bench>/sites
    → new_site() handler
    → @job decorator enqueues to RQ
         │
         ▼ RQ worker picks up
    Site.new_site() executes
    → @step sub-tasks run
         │
         ▼ Job completes
    callbacks.callback()
    → HTTP POST to Press
         │
         ▼ Press receives at
    /api/method/press.api.callbacks.callback
    → handle_job_updates()
    → process_job_updates()
    → side-effect handlers
```

---

## Agent Codebase Layout

```
/home/tanmoy/Desktop/frappe/agent/agent/
  web.py          ← Flask routes (55+ endpoints)
  job.py          ← RQ job management, @job/@step decorators, SQLite DB models
  callbacks.py    ← Posts job completion back to Press
  base.py         ← Base class (execute commands, manage configs, Redis)
  server.py       ← Server-level ops (benches, NIFs, proxy, database)
  bench.py        ← Bench ops (create, deploy, restart, config)
  site.py         ← Site ops (install, migrate, backup, restore)
```

---

## @job Decorator

Defined in `agent/job.py`. Wraps a method to:
1. Create a `JobModel` record in local SQLite (`jobs.sqlite3`)
2. Enqueue the method to RQ
3. Return `job_id` to the HTTP caller (Press stores this as `agent_job_id`)

```python
@job("New Site", priority="default", timeout=3600)
def new_site_job(self, site_config, apps):
    # orchestration — calls @step methods
    self.install_apps(apps)
    self.set_config(site_config)
    self.migrate()
```

**Options:**
- `priority` — `"default"` / `"high"` / `"low"` (maps to RQ queue names)
- `timeout` — seconds before RQ kills the job (default: 4 hours)

---

## @step Decorator

Wraps sub-tasks within a `@job`. Each `@step` maps to one `AgentJobStep` record in Press.

```python
@step("Download & Extract Files")
def restore_files(self, public_file=None, private_file=None):
    self.execute(f"tar xzf {public_file}")
    self.execute(f"tar xzf {private_file}")
    return {"extracted_files": [...]}
```

The step name string **must match** the `step_name` listed in the `AgentJobType` fixture on the Press side.

---

## SQLite Job/Step Models

Located at `jobs.sqlite3` (WAL mode, 2GB memory-mapped):

**JobModel:**
```
id, name, status (Pending|Running|Success|Failure),
agent_job_id, data (JSON), enqueue, start, end, duration
└─ steps: [StepModel]
```

**StepModel:**
```
id, name, job_id (FK), status, data (JSON), start, end, duration
```

---

## Callback Flow

### Agent side (`callbacks.py`)

When an RQ job completes (success or failure), RQ fires the callback:

```python
def callback(job, connection, result, *args, **kwargs):
    press_url = Server().press_url
    requests.post(
        f"{press_url}/api/method/press.api.callbacks.callback",
        data={"job_id": job.id},
    )
```

### Press side (`press/api/callbacks.py`)

```python
@frappe.whitelist(allow_guest=True)
def callback(job_id):
    # 1. Validate request origin (check agent IP)
    # 2. Enqueue handle_job_updates(job_id)
```

`handle_job_updates()`:
1. Calls `agent.get_job_status(job_id)` → HTTP GET to agent to fetch steps + output
2. `handle_polled_job()` → updates `AgentJob` + `AgentJobStep` records in Press DB
3. `process_job_updates()` → dispatches to job-specific side-effect handlers

### Side-effect handlers (Press)

```python
process_job_updates(job, update):
    match job.job_type:
        "New Site"         → process_new_site_job_update()
        "Archive Bench"    → process_archive_bench_job_update()
        "Backup Site"      → process_backup_site_job_update()
        ...                # 50+ handlers
```

---

## AgentJobType — Press Side

Defined in `press/fixtures/agent_job_type.json`. Example:

```json
{
    "name": "Add Domain to Upstream",
    "request_method": "POST",
    "request_path": "/proxy/upstreams/{upstream}/domains",
    "max_retry_count": 6,
    "disabled_auto_retry": 0,
    "steps": [
        {"step_name": "Add Site File to Upstream Directory"},
        {"step_name": "Reload NGINX"}
    ]
}
```

- `request_path` — Flask route path with `{param}` placeholders filled by Press at call time
- `steps` — expected step names; **must match** `@step("name")` strings in agent code
- `max_retry_count` — auto-retry on transient failures
- `disabled_auto_retry` — if 1, never auto-retry

---

## Route → Handler Mapping

Flask routes in `web.py` dispatch directly to Python methods. No central registry — URL structure determines what runs:

| Job Type | Method | Path | Agent Handler |
|----------|--------|------|---------------|
| New Site | POST | `/benches/<bench>/sites` | `Bench.new_site()` |
| Migrate Site | POST | `/benches/<bench>/sites/<site>/migrate` | `Site.migrate_job()` |
| Backup Site | POST | `/benches/<bench>/sites/<site>/backup` | `Site.backup_job()` |
| Activate Site | POST | `/benches/<bench>/sites/<site>/activate` | `Server.activate_site_job()` |
| New Bench | POST | `/benches` | `Server.new_bench()` |

---

## How to Add a New Job

### 1. Agent side — implement the job

Add to the appropriate class (`site.py`, `bench.py`, `server.py`):

```python
# agent/site.py

@job("My Custom Operation", priority="default", timeout=600)
def my_custom_operation_job(self, param1, param2):
    """High-level orchestrator — calls @step methods"""
    self.step_one(param1)
    self.step_two(param2)

@step("Step One")
def step_one(self, param1):
    """Low-level implementation"""
    output = self.execute(f"some-command {param1}")
    return {"result": output}

@step("Step Two")
def step_two(self, param2):
    result = self.execute(f"another-command {param2}")
    return {"output": result}
```

### 2. Agent side — add Flask route

In `web.py`:

```python
@application.route("/benches/<bench>/sites/<site>/my-custom", methods=["POST"])
def my_custom_operation(bench, site):
    data = request.json
    bench_obj = get_bench(bench)
    site_obj = Site(site, bench_obj)
    job = site_obj.my_custom_operation_job(
        param1=data["param1"],
        param2=data["param2"],
    )
    return {"job": job}
```

### 3. Press side — create AgentJobType fixture

Add to `press/fixtures/agent_job_type.json`:

```json
{
    "name": "My Custom Operation",
    "request_method": "POST",
    "request_path": "/benches/{bench}/sites/{site}/my-custom",
    "max_retry_count": 3,
    "disabled_auto_retry": 0,
    "steps": [
        {"step_name": "Step One"},
        {"step_name": "Step Two"}
    ]
}
```

### 4. Press side — call the job

```python
# From a Press doctype method
from press.agent import Agent

agent = Agent(self.server)
job = agent.create_job(
    job_type="My Custom Operation",
    path=f"/benches/{self.bench}/sites/{self.name}/my-custom",
    data={"param1": "value1", "param2": "value2"},
    site=self.name,
    bench=self.bench,
)
```

### 5. Press side — handle completion (optional)

In `press/api/callbacks.py` inside `process_job_updates()`:

```python
elif job.job_type == "My Custom Operation":
    process_my_custom_operation_update(job, update)
```

Implement `process_my_custom_operation_update(job, update)` to act on success/failure.

---

## Agent.request() — Press HTTP Client

`press/agent.py` `Agent` class handles building and sending requests:

- Adds auth headers (agent password)
- Sets `request_path` on the `AgentJob` doc
- Enqueues HTTP delivery via Celery so network failures are retried
- Polling fallback: if callback never arrives, a scheduled job polls `get_job_status`

---

## Retry Behavior

- `max_retry_count` on `AgentJobType` — auto-retry transient failures
- `disabled_auto_retry = 1` — opt out for jobs that aren't idempotent
- Manual retry: `agent_job.retry()` (whitelisted) — re-enqueues the HTTP request

---

## AgentJob Status Flow

```
Undelivered → Pending → Running → Success
                                → Failure → (auto-retry if configured)
```

`AgentJobStep` follows same status flow independently per step.

---

## Key Files

| Purpose | Path |
|---------|------|
| Agent Flask routes | `agent/agent/web.py` |
| Job/Step decorators + SQLite models | `agent/agent/job.py` |
| Job completion callback | `agent/agent/callbacks.py` |
| Site operations | `agent/agent/site.py` |
| Bench operations | `agent/agent/bench.py` |
| Server operations | `agent/agent/server.py` |
| Base class (execute, redis, config) | `agent/agent/base.py` |
| Press AgentJob doctype | `press/press/doctype/agent_job/agent_job.py` |
| Press callback handler | `press/api/callbacks.py` |
| AgentJobType fixtures | `press/fixtures/agent_job_type.json` |
| Press HTTP client | `press/agent.py` |
