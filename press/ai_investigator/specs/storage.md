# Storage Model

Two generic doctypes. No doctype per investigation type.

Provider settings live in `Press Settings`; see [llm-providers.md](llm-providers.md).

---

## Operational Investigation

One document per investigation.

```
title: Data
source: Select [Manual, MCP, Scheduler, Incident Hook, Dashboard, Webhook]
investigation_type: Select [Incident RCA, Performance Check, Downtime Explanation, Change Correlation, General Question, Action Planning]
status: Select [Queued, Running, Needs Human, Action Recommended, Action Taken, Completed, Inconclusive, Failed]

target_doctype: Data
target_name: Dynamic Link
team: Link / Team
started_by: Link / User

incident: Link / Incident
affected_site: Link / Site
affected_server: Link / Server
affected_bench: Link / Bench
affected_database_server: Link / Database Server

from_time: Datetime
to_time: Datetime
started_at: Datetime
completed_at: Datetime
last_run_at: Datetime
background_job_id: Data
error_count: Int

summary: Long Text
primary_cause: Small Text
confidence: Float
rca_markdown: Long Text

state_json: JSON
```

`state_json` example:
```json
{
  "query": "Why was site customer.example.com down yesterday?",
  "intent": "downtime_explanation",
  "time_window": {
    "from": "2026-05-27 13:30:00",
    "to": "2026-05-27 14:30:00"
  },
  "current_hypotheses": [],
  "recommended_next_checks": [],
  "recommended_actions": [],
  "last_error": null
}
```

---

## Operational Investigation Log

Append-only log for all events inside an investigation.

```
investigation: Link / Operational Investigation
type: Select [message, finding, hypothesis, tool_call, action_plan, action_result, rca, error, system]
title: Data
content: Long Text
data_json: JSON
timestamp: Datetime
```

Indexes:
- `incident, status`
- `target_doctype, target_name`
- `status, modified`
- `team, creation`

Store durable/filterable fields as DocType fields. Use `state_json` only for runner internals and non-queryable details.

### Example entries

**finding**:
```json
{
  "type": "finding",
  "title": "5xx started after deploy",
  "content": "5xx errors started two minutes after deploy job completed.",
  "data_json": {
    "evidence_type": "log",
    "source": "site_request_summary",
    "confidence": 0.8
  }
}
```

**tool_call**:
```json
{
  "type": "tool_call",
  "title": "get_site_error_logs",
  "data_json": {
    "input": {"site": "customer.example.com", "from_time": "...", "to_time": "..."},
    "output_summary": "Found repeated ImportError",
    "duration_ms": 1210,
    "status": "success"
  }
}
```

**action_plan**:
```json
{
  "type": "action_plan",
  "title": "Restart bench bench-001",
  "data_json": {
    "action": "restart_bench",
    "target_doctype": "Bench",
    "target_name": "bench-001",
    "reason": "web workers are down",
    "expected_impact": "brief downtime",
    "status": "pending_approval",
    "approved_by": null,
    "executed_at": null
  }
}
```

---

## What this model covers

- incident RCA
- manual performance checks
- chat messages
- tool calls (audit trail)
- findings
- hypotheses
- action plans + results
- RCA reports

No additional doctypes needed for the planned System Manager-only flow.
