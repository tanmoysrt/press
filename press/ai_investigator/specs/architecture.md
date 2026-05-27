# Architecture

## Goal

Press-native AI operations assistant. Handles:
- Automatic incident investigation
- Manual RCA / performance investigation
- Site / server / bench health checks
- Downtime explanation
- Recent change correlation
- Safe action recommendation + execution
- Source-code-aware performance analysis

Example questions:
```
Investigate INC-123.
Why was site customer.example.com down yesterday?
Check performance on server n1-mumbai.
Why is bench bench-001 slow?
Was this caused by a deploy?
Is it safe to restart this bench?
```

---

## System Shape

```
Incident / User Question
        ↓
Intent Router
        ↓
Target Resolver
        ↓
Investigation Runner
        ↓
Playbook
        ↓
Tool Calls
        ↓
Evidence + Hypotheses
        ↓
Answer / RCA / Action Plan
```

Two entry paths:

**Automatic**: Incident created → scheduler/hook → Operational Investigation → first-pass runs  
**Manual**: System Manager asks in chat → MCP tool → target resolved → playbook runs → answer returned

---

## Tech Direction

**Frappe version: v15.** Do not use v16-only APIs. Specifically:
- Use `frappe.get_all` / `frappe.get_list` / `frappe.get_doc` (v15 standard)
- Use `frappe.enqueue` with dotted string paths, not callable refs
- Use `frappe.db.exists`, `frappe.db.get_value`, `frappe.db.get_list`
- No `frappe.qb` — avoid entirely in this codebase
- No `frappe.db.sql` — avoid entirely; use ORM methods only
- Type hints in function signatures are fine (Python 3.10+ on v15), but no runtime type enforcement

Use `frappe/mcp` inside Press. No external MCP server.

Why:
- No duplicate auth layer
- LLM provider config stays inside Press settings
- No SQLite / external state
- Uses Frappe roles and permissions natively
- Direct access to Press doctypes and APIs
- Easier FC dashboard integration later
- Audit trail via Frappe ORM

## Existing Incident Flow

The existing `Incident Investigator` flow can keep working as it does today.
This spec does not require changing, disabling, or migrating it.

New AI Ops work uses:
- `Operational Investigation`
- `Operational Investigation Log`
- `press/ai_investigator/*`

The two systems may coexist. AI Ops duplicate prevention only needs to prevent duplicate `Operational Investigation` records.

---

## Code Structure

```
press/ai_investigator/
├── __init__.py
├── mcp.py               # MCP entrypoint, tool imports
├── llm.py               # OpenAI / Anthropic / Anthropic-compatible client config
├── permissions.py       # system_manager_only decorator
├── redaction.py         # strip credentials/PII from tool output
├── audit.py             # tool call audit log helpers
│
├── tools/
│   ├── __init__.py
│   ├── incidents.py     # get_incident_details, get_active_incidents
│   ├── documents.py     # get_document, list_documents, get_document_versions
│   ├── investigation.py # investigate, investigate_incident, check_*
│   ├── metrics.py       # get_server_basic_metrics, get_site_request_summary
│   ├── logs.py          # get_site_error_logs, get_slow_queries, get_slow_apis
│   ├── jobs.py          # get_recent_jobs, get_job_details
│   ├── actions.py       # plan_*, execute_action_plan
│   └── code_analysis.py # resolve_endpoint_source, analyze_slow_endpoint
│
└── investigation/
    ├── __init__.py
    ├── runner.py        # start, run_first_pass, continue, finalize
    ├── router.py        # intent classification
    ├── targets.py       # target resolution + related resource lookup
    ├── playbooks.py     # ordered check sequences per intent
    ├── evidence.py      # evidence storage helpers
    ├── hypotheses.py    # hypothesis scoring
    ├── rca.py           # RCA markdown generation
    ├── actions.py       # action plan creation + execution
    └── hooks.py         # Incident after_insert hook
```

---

## Investigation Flow (detailed)

```python
# MCP tool entry
investigate_incident("INC-123")
  → runner.start_investigation(incident_name="INC-123", source="MCP")
      → create Operational Investigation doc
      → enqueue run_first_pass

run_first_pass(investigation_name)
  → router.classify_intent(query, incident)     # → "incident_rca"
  → targets.resolve(incident)                   # → {site, server, bench}
  → playbooks.get("incident_rca")
  → run each tool in playbook order
  → evidence.store(findings)
  → hypotheses.score(findings)
  → update investigation doc (summary, primary_cause, confidence)
  → return result
```

---

## Safety Baseline

Before any tool returns production data to an MCP client:
- enforce role checks at endpoint + tool level
- redact secrets from every tool output
- cap time ranges and result sizes
- audit every tool call
- truncate large logs with an explicit `truncated=true` marker

Raw expert tools and action tools are forbidden until this baseline is implemented and tested.

---

## Tool Execution Model

For now, tools run on the same server as Press.

Execution rules:
- prefer Press/Frappe APIs and ORM calls over shell commands
- run all tool code with explicit sandbox constraints
- Docker/container isolation is allowed for tools that need filesystem or process inspection
- no arbitrary shell execution exposed to the model
- no arbitrary SSH write commands
- read-only filesystem access must use path allowlists
- write/action tools must go through the Phase 10 approval flow
- every tool call is audited with user, input summary, status, duration, and output summary

Sandbox requirements:
- bounded CPU/time/memory for expensive tools
- bounded result size
- no credential path reads
- no network access except approved internal endpoints and configured LLM provider endpoints
- all output passes through redaction before storage or display

Container usage:
- optional for MVP
- acceptable for log parsing, source analysis, or future diagnostic commands
- container must be read-only by default
- mount only required allowlisted paths
- drop unnecessary capabilities

---

## MCP Auth Pattern

Every HTTP call from MCP tool to FC (if calling FC REST API):
```
Authorization: token {api_key}:{api_secret}
X-Press-Team: {team}
```

But since we run inside Press itself, most tools call `frappe.get_doc` / Press API functions directly — no HTTP needed.

---

## Allowed Read Doctypes

```
Server, Database Server, Proxy Server, Monitor Server,
Bench, Site, Agent Job, Ansible Play,
Press Job, Press Workflow,
Incident, Cluster, Release Group,
Operational Investigation
```

---

## Guardrails Summary

**Forbidden actions** (hard-blocked at MCP layer):
- archive / delete / drop any resource
- restore / reinstall site
- reboot database server
- remove / disable proxy
- arbitrary SSH write commands
- credential file access

**Allowed actions** (Phase 10+, require human approval token):
- restart_bench
- reboot_app_server
- activate_site

**Path whitelist** for file reads:
- `/home/frappe/frappe-bench/logs/`
- `/var/log/nginx/`
- frappe app config files

Build guardrails around the rules, dont allow llm to execute ssh.