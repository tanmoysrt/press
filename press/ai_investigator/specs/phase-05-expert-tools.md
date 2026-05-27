# Phase 5 — Expert Tools

**Sprint**: 5  
**Goal**: Source-code-aware slow endpoint analysis. Raw PromQL and ES queries for advanced debugging.

Replaces old phases 11, 12.

**Prerequisite**: `redaction.py`, `audit.py`, `guardrails.py`, `system_manager_only`, time-range limits, and tool execution sandbox must all be in place and tested before adding these tools.

---

## Files

```
press/ai_investigator/tools/code_analysis.py
press/ai_investigator/tools/metrics.py        (additions)
press/ai_investigator/tools/logs.py           (additions)
```

---

## Code Analysis (`code_analysis.py`)

```python
resolve_endpoint_source(site, endpoint_path) -> dict
get_app_source_file(site, app, file_path) -> str
get_bench_app_info(bench, app) -> dict
analyze_slow_endpoint(site, endpoint_path, from_time, to_time) -> dict
```

### `analyze_slow_endpoint` flow

```
get_slow_apis(site, from_time, to_time)
  → pick slowest endpoint
  → resolve_endpoint_source(site, endpoint_path)
      → parse endpoint → app, file_path, function
      → site → bench → BenchApp → AppSource (repo_url, branch)
      → bench → AppRelease → commit_hash
      → fetch source from git host at exact commit
  → detect bad patterns in function source
  → store as finding (evidence_type=source_code)
  → return findings
```

### Endpoint parsing

```
/api/method/{app}.{...modules}.{function}
  → app = first segment, file = {app}/{...modules}.py

/api/resource/{DocType}
  → DocType → module → app → doctype controller file

/api/method/run_doc_method  (with doctype/name params)
  → resolve doctype → controller file
```

### Source resolution

```
Site → bench → BenchApp → AppSource (repository_url, branch)
bench → AppRelease → commit_hash
→ fetch: GET /repos/{owner}/{repo}/contents/{path}?ref={sha}
```

No server filesystem access. Git host API at pinned commit only.

### Git host support

**GitHub**: `GET https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={sha}`  
Public repos: no token. Private: `github_token` from Press Settings.

**GitLab**: `GET https://gitlab.com/api/v4/projects/{id}/repository/files/{path}?ref={sha}`  
Token: `gitlab_token` from Press Settings.

### Bad patterns detected

```python
BAD_PATTERNS = [
    r"frappe\.get_doc\s*\(",          # N+1 queries inside loop
    r"frappe\.db\.get_value\s*\(",    # N+1 queries inside loop
    r"frappe\.db\.get_all\s*\(",      # N+1 queries inside loop
    r"frappe\.db\.sql\s*\([^)]+(?!limit)",  # unbounded queries
    r"requests\.get\(", r"requests\.post\(",  # sync HTTP in request path
    r"for .* in .*\.items:",          # large child table iteration
]
```

AST analysis preferred; regex fallback.

### `resolve_endpoint_source` return shape

```python
{
    "app": "erpnext",
    "file_path": "erpnext/accounts/doctype/sales_invoice/sales_invoice.py",
    "function": "get_dashboard_data",
    "repo_url": "https://github.com/frappe/erpnext",
    "commit": "a3f921b",
    "source": "def get_dashboard_data(...):\n    ...",
    "line_start": 142,
    "line_end": 178,
}
```

Add `analyze_slow_endpoint` to `site_performance` playbook.

---

## Raw Expert Tools

For advanced debugging not covered by standard wrappers.

```python
# tools/metrics.py
query_prometheus_raw(query, from_time, to_time, step="60s") -> dict

# tools/logs.py
query_elasticsearch_raw(index_pattern, query, filters=None, from_time=None, to_time=None, size=100) -> dict
```

### Guardrails

```python
MAX_RAW_TIME_RANGE_HOURS = 24
MAX_ES_RESULT_SIZE = 500
PROMETHEUS_TIMEOUT_SECONDS = 30
ES_TIMEOUT_SECONDS = 30
```

All output through `redaction.py`. All calls logged in `audit.py` and investigation log.

FC APIs:
- Prometheus: `press.api.server.prometheus_query`
- ES: `press.api.analytics.*` (index: `filebeat-*`)

---

## Checklist

- [ ] Prerequisite safety infrastructure verified before merging
- [ ] `/api/method/` endpoint parsing
- [ ] `/api/resource/` endpoint → DocType → file path
- [ ] Site → bench → AppSource → commit hash lookup
- [ ] GitHub API fetch at pinned commit (public + private)
- [ ] GitLab API fetch at pinned commit
- [ ] Function extraction from file content
- [ ] Bad pattern detection (AST + regex fallback)
- [ ] Findings stored as type=finding, evidence_type=source_code
- [ ] `analyze_slow_endpoint` added to site_performance playbook
- [ ] `query_prometheus_raw` time range limit enforced
- [ ] `query_elasticsearch_raw` size + time range limits enforced
- [ ] Timeouts enforced on both raw tools
- [ ] System Manager only on all tools

## Success Criteria

```
Slow API on a site:
→ "Endpoint calls frappe.db.get_value inside a loop over sales invoices.
   N+1 queries. File: erpnext/accounts/.../sales_invoice.py:156
   Deployed commit: a3f921b"

Advanced user runs custom PromQL:
→ results bounded, redacted, audited
```
