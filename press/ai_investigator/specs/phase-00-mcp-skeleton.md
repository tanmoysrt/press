# Phase 0 — MCP Skeleton

**Sprint**: 1  
**Goal**: Working MCP endpoint inside Press with System Manager guard.

---

## Build

```
press/ai_investigator/__init__.py
press/ai_investigator/mcp.py
press/ai_investigator/llm.py
press/ai_investigator/permissions.py
press/ai_investigator/redaction.py
press/ai_investigator/audit.py
press/ai_investigator/tools/ping.py
```

## `mcp.py`

```python
import frappe
import frappe_mcp

mcp = frappe_mcp.MCP("frappe-cloud-ops-mcp")

@mcp.register()
def handle_mcp():
    frappe.only_for("System Manager")
    import press.ai_investigator.tools.ping
```

Only import implemented tool modules. Later phases add their own imports when the module and tests exist.

## `permissions.py`

```python
import functools, frappe

def system_manager_only(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        frappe.only_for("System Manager")
        return fn(*args, **kwargs)
    return wrapper
```

## `llm.py`

Load provider settings from `Press Settings`.

Supported providers:
- OpenAI
- Anthropic
- Anthropic Compatible

Anthropic-compatible config supports:
- `anthropic_base_url`
- `anthropic_default_opus_model`
- `anthropic_default_sonnet_model`
- `anthropic_default_haiku_model`
- `anthropic_custom_headers_json`

See [llm-providers.md](llm-providers.md).

## `redaction.py`

```python
def redact(value):
    """Return value with secrets removed before it is sent to MCP."""
    ...
```

Minimum patterns:
- Authorization headers
- cookies
- passwords
- API keys
- private keys
- database URLs
- tokens in URLs

## `audit.py`

```python
def record_tool_call(tool_name: str, user: str, input_summary: str, status: str, duration_ms: int):
    """Record every MCP tool call for traceability."""
    ...
```

## Test tool

```python
@mcp.tool()
@system_manager_only
def ping() -> dict:
    """Verify MCP connection."""
    return {"status": "ok", "site": frappe.local.site}
```

---

## Checklist

- [ ] Add `frappe_mcp` dependency
- [ ] Create `press/ai_investigator/mcp.py`
- [ ] Create `press/ai_investigator/llm.py`
- [ ] Add AI Ops provider fields to `Press Settings`
- [ ] Create `press/ai_investigator/permissions.py` with `system_manager_only`
- [ ] Create `press/ai_investigator/redaction.py` with tests for common secret formats
- [ ] Create `press/ai_investigator/audit.py`
- [ ] Protect MCP endpoint with `frappe.only_for("System Manager")`
- [ ] Add `ping()` test tool
- [ ] Import only implemented tool modules
- [ ] Wrap tool responses with redaction before returning to MCP
- [ ] Record every tool call in audit
- [ ] Verify MCP client can call `ping()`
- [ ] Verify non-System Manager gets permission error

## Success Criteria

System Manager can call `ping()` via MCP. Non-System Manager cannot. A redaction unit test proves secrets are stripped before output leaves Press.
