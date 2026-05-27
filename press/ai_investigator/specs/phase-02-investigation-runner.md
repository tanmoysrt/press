# Phase 2 — Investigation Runner

**Sprint**: 2  
**Goal**: Storage, tools, runner, playbooks, and auto-trigger all working. `investigate_incident` and `investigate()` produce findings end-to-end.

Replaces old phases 2, 3, 4, 5a, 6, 7.

---

## Files Created

```
press/ai_investigator/tools/metrics.py
press/ai_investigator/tools/logs.py
press/ai_investigator/tools/jobs.py
press/ai_investigator/tools/investigation.py
press/ai_investigator/investigation/runner.py
press/ai_investigator/investigation/router.py
press/ai_investigator/investigation/targets.py
press/ai_investigator/investigation/playbooks.py
press/ai_investigator/investigation/evidence.py
press/ai_investigator/investigation/hooks.py
```

---

## Storage

Create two doctypes. Full field specs in [storage.md](storage.md).

- `Operational Investigation` — one doc per investigation
- `Operational Investigation Log` — append-only events (tool_call, finding, hypothesis, message, action_plan, action_result, rca, error, system)

### `evidence.py` helpers

```python
def append_log(investigation_name, type, title, content="", data=None): ...
def log_tool_call(investigation_name, tool_name, input, output_summary, duration_ms, status): ...
def log_finding(investigation_name, title, content, evidence_type, confidence): ...
def log_hypothesis(investigation_name, title, confidence, evidence, next_check=None): ...
```

---

## Tools

### `tools/metrics.py`

```python
get_server_basic_metrics(server, from_time, to_time) -> dict   # CPU, memory, disk, load
get_site_request_summary(site, from_time, to_time) -> dict     # count, 5xx, avg/p95 latency
get_uptime(site, from_time, to_time) -> dict
get_server_metrics(server, metric_type, from_time, to_time) -> dict
```

`metric_type`: `cpu`, `memory`, `disk`, `iops`, `network`, `load`, `db`

### `tools/logs.py`

```python
get_site_error_logs(site, from_time, to_time, limit=100) -> list
get_site_log(site, log_type, from_time, to_time, limit=100) -> str
get_bench_log(bench, log_type, from_time, to_time, limit=100) -> str
get_slow_queries(site, from_time, to_time, search_pattern=None, max_lines=100) -> list
get_slow_apis(site, from_time, to_time, threshold_ms=None) -> list
get_frequent_slow_queries(site, from_time, to_time) -> list
```

`log_type`: `frappe.log`, `error.log`, `database.log`, `scheduler.log`, `worker.log`

### `tools/jobs.py`

```python
get_recent_jobs(target_doctype, target_name, from_time, to_time, limit=20) -> list
get_job_details(job_name) -> dict
get_bench_processes(server) -> dict
list_processes(server) -> list
```

### `tools/investigation.py`

```python
investigate_incident(incident_name: str) -> dict
investigate(
    query: str,
    target_doctype: str | None = None,
    target_name: str | None = None,
    from_time: str | None = None,
    to_time: str | None = None,
) -> dict
check_site_performance(site, from_time=None, to_time=None) -> dict
check_server_performance(server, from_time=None, to_time=None) -> dict
check_bench_health(bench, from_time=None, to_time=None) -> dict
explain_downtime(target_doctype, target_name, from_time, to_time) -> dict
check_recent_changes(target_doctype, target_name, from_time=None, to_time=None) -> dict
```

All tools: `@system_manager_only`, output via `redaction.py`, call via `audit.py`.

---

## Runner (`runner.py`)

```python
def start_investigation(
    query=None, incident_name=None,
    target_doctype=None, target_name=None,
    from_time=None, to_time=None,
    source="Manual",
) -> str:
    """Create Operational Investigation (status=Queued), enqueue run_first_pass. Return doc name."""

def run_first_pass(investigation_name: str):
    """Classify intent → resolve target → pick playbook → run tools → store findings → update doc."""
```

### `run_first_pass` flow

```
load investigation
→ router.classify_intent(query or incident)
→ targets.resolve(...)
→ playbooks.get(intent)
→ run each PlaybookStep in order (skip required=False steps on error)
→ log_tool_call + log_finding for each
→ log_hypothesis for scored hypotheses
→ doc: summary, primary_cause, confidence, status=Completed
       (status=Needs Human if confidence < 0.4)
→ on exception: status=Failed, append error log
```

### Time ranges

```python
DEFAULT_TIME_RANGE_HOURS = 1
MAX_TIME_RANGE_HOURS = 24
```

---

## Intent Router (`router.py`)

```python
def classify_intent(query: str, incident=None) -> str
```

Intents: `incident_rca`, `site_performance`, `server_performance`, `bench_performance`, `database_performance`, `downtime_explanation`, `recent_changes`, `job_failure`, `capacity_check`, `safe_action_request`, `general_question`

Keyword matching. LLM fallback for ambiguous cases only.

---

## Target Resolver (`targets.py`)

```python
def resolve(query, incident=None, target_doctype=None, target_name=None) -> dict
```

Returns:
```python
{
    "target_doctype": "Site",
    "target_name": "customer.example.com",
    "related": {"bench": "...", "server": "...", "database_server": "...", "cluster": "..."}
}
```

Sources: explicit params → name extracted from query → Frappe DB lookup → incident doc.

---

## Playbooks (`playbooks.py`)

```python
@dataclass
class PlaybookStep:
    tool: str
    required: bool = True
    condition: str | None = None  # skip if this finding type absent

PLAYBOOKS = {
    "incident_rca": [...],
    "site_performance": [...],
    "server_performance": [...],
    "bench_performance": [...],
    "downtime_explanation": [...],
    "recent_changes": [...],
    "database_performance": [...],
}

def get_playbook(intent: str) -> list[PlaybookStep]:
    return PLAYBOOKS.get(intent, general_question_playbook)
```

### Playbook steps

**incident_rca**: `get_incident_details` → `get_recent_jobs` → `get_site_error_logs` → `get_site_request_summary` → `get_server_basic_metrics`

**site_performance**: `get_site_request_summary` → `get_slow_apis` → `get_slow_queries` → `get_server_basic_metrics` → `get_recent_jobs`

**server_performance**: `get_server_basic_metrics` → `list_processes` → `get_bench_processes` → `get_recent_jobs`

**bench_performance**: `get_bench_processes` → `get_bench_log` → `get_server_basic_metrics`

**downtime_explanation**: `get_uptime` → `get_site_request_summary` → `get_site_error_logs` → `get_recent_jobs` → `get_server_basic_metrics`

**recent_changes**: `get_recent_jobs` → `get_document_versions`

**database_performance**: `get_slow_queries` → `get_frequent_slow_queries` → `get_site_request_summary` → `get_server_basic_metrics`

---

## Auto-Trigger (`hooks.py`)

### Scheduler — every minute

```python
def poll_active_incidents():
    active = frappe.get_all("Incident",
        filters={"status": ["in", ["Investigating", "Acknowledged"]]},
        fields=["name"])
    for inc in active:
        if not has_investigation(inc.name):
            frappe.enqueue("press.ai_investigator.investigation.runner.start_investigation",
                incident_name=inc.name, source="Scheduler")

def has_investigation(incident_name) -> bool:
    return frappe.db.exists("Operational Investigation",
        {"incident": incident_name, "status": ["not in", ["Failed"]]})
```

Add to `press/hooks.py`:
```python
scheduler_events = {"cron": {"* * * * *": ["press.ai_investigator.investigation.hooks.poll_active_incidents"]}}
```

### Incident hook — after scheduler confirmed stable

```python
# press/hooks.py
doc_events = {"Incident": {"after_insert": "press.ai_investigator.investigation.hooks.on_incident_created"}}

def on_incident_created(doc, method=None):
    if not has_investigation(doc.name):
        frappe.enqueue("press.ai_investigator.investigation.runner.start_investigation",
            incident_name=doc.name, source="Incident Hook")
```

---

## `investigate_incident` return shape

```python
{
    "investigation": "OI-0001",
    "incident": "INC-123",
    "affected": {"site": "...", "server": "...", "bench": "..."},
    "time_window": {"from": "...", "to": "..."},
    "timeline": ["14:01 deploy completed", "14:03 5xx started"],
    "findings": [{"type": "log", "text": "ImportError at 14:03"}, ...],
    "primary_cause": "Deploy introduced application import error",
    "confidence": 0.78,
    "recommended_next_checks": ["Inspect deploy job output", "..."]
}
```

---

## Checklist

- [ ] `Operational Investigation` doctype
- [ ] `Operational Investigation Log` doctype
- [ ] `evidence.py` helpers (append_log, log_tool_call, log_finding, log_hypothesis)
- [ ] All tools in metrics.py, logs.py, jobs.py, investigation.py
- [ ] All tool output through `redaction.py`
- [ ] All tool calls recorded in `audit.py` and investigation log
- [ ] `start_investigation` creates doc + enqueues
- [ ] `run_first_pass` runs via `frappe.enqueue`
- [ ] Intent router classifies all intents
- [ ] Target resolver for Site, Server, Bench, Incident
- [ ] Related resource lookup (site→bench→server)
- [ ] All 7 playbooks with ordered steps
- [ ] Required=False steps don't abort on error
- [ ] Conditional steps skip when condition not met
- [ ] Status transitions (Queued → Running → Completed / Needs Human / Failed)
- [ ] Scheduler polls active incidents every minute
- [ ] Duplicate prevention via `has_investigation()`
- [ ] Incident hook added after scheduler confirmed
- [ ] `run_first_pass` failure → status=Failed + error log

## Success Criteria

```
User: investigate_incident("INC-123")
→ OI-0001 created, first pass runs in background
→ findings, tool call logs, hypotheses stored
→ status=Completed, primary_cause + confidence set
→ new incident created → investigation starts within 1 minute automatically
→ no duplicate investigations
```
