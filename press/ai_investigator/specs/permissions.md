# Permission Model

## MVP: System Manager Only

Every MCP tool restricted to System Manager. Three redundant enforcement layers.

### Layer 1 — MCP endpoint

```python
@mcp.register()
def handle_mcp():
    frappe.only_for("System Manager")
    import press.ai_investigator.tools.incidents
    import press.ai_investigator.tools.documents
    # ... all tool modules
```

### Layer 2 — Tool decorator

```python
# press/ai_investigator/permissions.py
import functools, frappe

def system_manager_only(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        frappe.only_for("System Manager")
        return fn(*args, **kwargs)
    return wrapper
```

```python
@mcp.tool()
@system_manager_only
def investigate_incident(incident_name: str) -> dict:
    ...
```

### Layer 3 — Sensitive service functions

```python
def execute_action_plan(investigation_name, action_id):
    frappe.only_for("System Manager")
    ...
```

Intentionally redundant. Defense in depth.

---

## Roles

Only `System Manager` can access MCP tools, investigations, raw expert tools, and action approval/execution.

Do not add any other role access in this plan.

---

## Redaction

`press/ai_investigator/redaction.py` — strip from all tool output before returning to model:

Implemented in Phase 0. No production data tool is allowed before redaction tests pass.

**Always redact**:
- API keys, Authorization headers
- Cookies, passwords
- Database connection URLs
- Private keys, tokens in URLs
- Secrets in config files
- Sensitive headers

**Optional later**:
- Email addresses
- SQL literals with PII
- Customer data

## Audit

`press/ai_investigator/audit.py` records every MCP tool call from Phase 0 onward:
- user
- tool name
- input summary
- status
- duration
- timestamp

Investigation-specific tool calls are also appended to `Operational Investigation Log` once storage exists.
