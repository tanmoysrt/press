# Phase 1 — Basic Read Tools

**Sprint**: 1  
**Goal**: Fetch real Frappe Cloud context via MCP.

---

## Files

```
press/ai_investigator/tools/incidents.py
press/ai_investigator/tools/documents.py
press/ai_investigator/tools/jobs.py
```

---

## `tools/incidents.py`

```python
get_incident_details(incident_name: str) -> dict
get_active_incidents(cluster: str | None = None) -> list
get_incident_history(target_doctype: str, target_name: str, days: int = 7) -> list
```

FC APIs: `press.api.incident.get_incidents`, `press.api.incident.get_incident_count`

---

## `tools/documents.py`

```python
get_document(doctype: str, name: str) -> dict
list_documents(doctype: str, filters: dict | None = None, fields: list | None = None, limit: int = 20) -> list
get_document_versions(doctype: str, name: str, days: int = 30) -> list
```

**Allowed doctypes**:
```
Server, Database Server, Proxy Server, Monitor Server,
Bench, Site, Agent Job, Ansible Play,
Press Job, Press Workflow,
Incident, Cluster, Release Group, Operational Investigation
```

`get_document_versions` uses `GET /api/resource/Version` filtered by `ref_doctype` + `docname`.

---

## `tools/jobs.py`

```python
get_recent_jobs(target_doctype: str, target_name: str, from_time: str, to_time: str, status: str | None = None) -> list
get_job_details(job_name: str) -> dict
get_site_jobs(site: str, limit: int = 20, status: str | None = None) -> list
get_server_jobs(server: str, limit: int = 20, status: str | None = None) -> list
get_bench_jobs(bench: str, limit: int = 20, status: str | None = None) -> list
```

FC API: `press.api.server.jobs`

`get_job_details` returns full output + step-by-step log.

---

## Checklist

- [ ] `get_incident_details` works
- [ ] `get_active_incidents` works (with + without cluster filter)
- [ ] `get_document` works for all allowed doctypes, rejects others
- [ ] `list_documents` with filters works
- [ ] `get_document_versions` returns field change history
- [ ] `get_recent_jobs` works
- [ ] `get_job_details` returns step output
- [ ] All tools have `@system_manager_only`
- [ ] Errors return readable messages

## Success Criteria

From MCP chat:
```
"Show details of INC-123"       → incident fields + alert summary
"Show recent jobs for site X"   → job list with status
```
