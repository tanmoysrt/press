# Phase 4 — Safe Action Planning

**Sprint**: 4  
**Goal**: Agent recommends actions; human approves; system executes.

---

## Files

```
press/ai_investigator/investigation/actions.py
press/ai_investigator/tools/actions.py
press/ai_investigator/guardrails.py
```

---

## Flow

```
Agent recommends action
  → creates action_plan log entry (status=pending_approval)
  → user reviews: target, reason, expected impact, current state, expiry
  → user approves via execute_action_plan
  → action executes
  → result stored as action_result log
  → investigation status → Action Taken
```

---

## Tools

```python
# tools/actions.py
plan_restart_bench(bench: str, investigation_name: str, reason: str) -> dict
plan_reboot_app_server(server: str, investigation_name: str, reason: str) -> dict
plan_activate_site(site: str, investigation_name: str, reason: str) -> dict

execute_action_plan(investigation_name: str, action_id: str, approval_token: str) -> dict
```

All tools: `@system_manager_only`  
`execute_action_plan` also calls `frappe.only_for("System Manager")` inside.

Action tools run on the Press server and call existing Press APIs. Do not expose shell execution to the model. If a future action needs command execution, it must run through the tool execution sandbox and still require approval.

---

## Action Plan Log Entry

```json
{
  "action": "restart_bench",
  "target_doctype": "Bench",
  "target_name": "bench-001",
  "reason": "web workers are down",
  "expected_impact": "brief downtime while workers restart",
  "status": "pending_approval",
  "approval_token_hash": "...",
  "expires_at": "2026-05-27 14:30:00",
  "approved_by": null,
  "executed_at": null,
  "result": null
}
```

`action_id` = name of the `Operational Investigation Log` entry.

---

## `guardrails.py` — Forbidden Actions

```python
FORBIDDEN_ACTIONS = {
    "archive", "delete", "drop",
    "restore", "reinstall",
    "reboot_database_server",
    "disable_proxy", "remove_proxy",
    "ssh_write", "execute_command",
    "read_credentials", "read_env",
}

def check_action(action: str):
    if action in FORBIDDEN_ACTIONS:
        raise frappe.PermissionError(f"Action '{action}' is not allowed via MCP.")
```

---

## Allowed Actions (Phase 10)

| Tool | FC API | Notes |
|------|--------|-------|
| `restart_bench` | `press.api.bench.restart` | Supervisor reload |
| `reboot_app_server` | `press.api.server.reboot` | App server only, not DB |
| `activate_site` | `press.api.site.activate` | Bring suspended site back |

`reboot_database_server` is forbidden — too destructive.

---

## `execute_action_plan` Flow

```
load action_plan log entry
→ check status = pending_approval
→ check action has not expired
→ check approval token matches
→ check action not forbidden
→ check current user = System Manager
→ re-read target doc and validate current state still matches plan assumptions
→ update log: approved_by, status=approved
→ call FC API
→ update log: status=executed, executed_at, result
→ append action_result log
→ update investigation status = Action Taken
```

---

## Plan Display Format

When recommending action, system should show:

```
Recommended action: restart bench bench-001
Reason: web workers are unresponsive
Expected impact: brief downtime (~30s) while workers restart
Action ID: OIL-00042
Expires: 2026-05-27 14:30:00
Approval token: shown once to the approving user

To approve: execute_action_plan("OI-0001", "OIL-00042", approval_token)
```

---

## Checklist

- [ ] `plan_*` tools create action_plan log (pending_approval)
- [ ] `guardrails.py` blocks all forbidden actions
- [ ] `execute_action_plan` requires pending_approval status
- [ ] `execute_action_plan` requires unexpired approval token
- [ ] `execute_action_plan` re-checks System Manager
- [ ] `execute_action_plan` revalidates target state before execution
- [ ] No shell command execution exposed to the model
- [ ] FC API call succeeds and result stored
- [ ] Investigation status updates to Action Taken
- [ ] Calling execute twice returns error (already executed)

## Success Criteria

```
Assistant: Recommended action: restart bench bench-001. Reason: workers down. Action ID: OIL-00042. Approve?
User: execute_action_plan OI-0001 OIL-00042
System: Bench bench-001 restarted. Workers back online.
```
