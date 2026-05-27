# Phase 3 — Stateful Continuation + RCA

**Sprint**: 3  
**Goal**: Investigations can be continued interactively. RCA markdown generated from stored evidence.

Replaces old phases 5b, 8, 9.

---

## Files

```
press/ai_investigator/investigation/runner.py      (additions)
press/ai_investigator/investigation/rca.py
press/ai_investigator/tools/investigation.py       (additions)
```

---

## New Runner Functions

```python
def continue_investigation(investigation_name: str, instruction: str) -> dict:
    """Store user message, map instruction → checks, run checks, update hypotheses, store response."""

def finalize_rca(investigation_name: str) -> str:
    """Build RCA markdown from logs. Store in rca_markdown. Return markdown text."""
```

## New MCP Tools

```python
get_investigation_status(investigation_name: str) -> dict
continue_investigation(investigation_name: str, instruction: str) -> dict
finalize_rca(investigation_name: str) -> str
```

---

## `get_investigation_status` return shape

```python
{
    "name": "OI-0001",
    "status": "Completed",
    "summary": "...",
    "primary_cause": "...",
    "confidence": 0.78,
    "recommended_next_checks": [...],
    "log_count": 12,
    "last_updated": "2026-05-27 14:05:00"
}
```

---

## `continue_investigation` flow

```
load investigation
→ append log (type=message, role=user, content=instruction)
→ map instruction → additional checks (see table below)
→ load prior findings (skip redundant tool calls: same tool + same window)
→ run checks, log tool_calls + findings
→ update existing hypotheses if new evidence confirms/denies (don't duplicate)
→ append log (type=message, role=assistant, content=response)
→ return response dict
```

### Instruction → checks mapping

| Instruction pattern | Checks run |
|---------------------|------------|
| "check DB" / "database slow" | `db_slow` mini-playbook |
| "show error logs" | `get_site_error_logs` |
| "compare previous hour" | re-run request summary + metrics with shifted window |
| "caused by deploy?" | `get_recent_jobs` + `get_document_versions` |
| "slow APIs?" | `get_slow_apis` |
| "worker queue?" | `get_bench_processes` |
| "can we restart?" | Phase 4 action planning |

Keyword matching first. LLM classification fallback for ambiguous instructions.

---

## State Transitions

```
Queued → Running → Completed
                 → Needs Human → (continue_investigation) → Completed
                 → Inconclusive
Running → Failed  (on exception)
Completed → Action Recommended → Action Taken
```

---

## `finalize_rca` — RCA markdown format

```markdown
# RCA: INC-123

## Summary
One paragraph: what happened and primary cause.

## Impact
- Affected site(s): customer.example.com
- Downtime window: 14:03–14:22 (19 min)
- Error rate during window: 12%

## Timeline
| Time  | Event |
|-------|-------|
| 14:01 | Deploy completed for bench-001 |
| 14:03 | 5xx rate jumped from 0.1% to 12% |
| 14:03 | ImportError in error.log |
| 14:22 | Site recovered after bench restart |

## Root Cause
Primary: Deploy introduced an ImportError in the accounts module.
Confidence: 0.78

## Evidence
- error.log shows `ImportError: cannot import name 'get_dashboard_data'` from 14:03
- 5xx spike began 2 minutes after deploy (correlation)
- Server CPU and DB metrics were normal (rules out infra cause)

## Action Taken
- Bench bench-001 restarted at 14:20 (approved by admin@example.com)
- Site recovered at 14:22

## Follow-ups
- [ ] Fix import error in accounts module
- [ ] Add smoke test for deploy to catch import errors pre-prod
```

### Generation strategy

- Timeline + Evidence: built deterministically from log entries
- Summary + Root cause prose: LLM synthesis from stored findings and hypothesis
- Action taken: from `type=action_result` logs
- Follow-ups: from `recommended_next_checks` + low-confidence hypotheses

```python
doc.rca_markdown = markdown_text
doc.save()
append_log(investigation_name, type="rca", title="RCA generated", content=markdown_text)
```

Calling `finalize_rca` when already finalized returns existing without overwriting.

---

## Checklist

- [ ] `continue_investigation` stores user message before running checks
- [ ] Instruction → checks mapping covers all patterns in table
- [ ] Redundant tool calls skipped (same tool + same window already ran)
- [ ] New findings update existing hypotheses, not duplicate
- [ ] Time window shift ("previous hour") works
- [ ] Assistant response stored after checks
- [ ] `get_investigation_status` returns useful summary
- [ ] RCA timeline built from tool_call + finding timestamps
- [ ] RCA evidence from `type=finding` logs
- [ ] RCA root cause from highest-confidence hypothesis
- [ ] RCA action taken from `type=action_result` logs
- [ ] RCA stored in `rca_markdown` field + log entry appended
- [ ] `finalize_rca` idempotent (won't overwrite)

## Success Criteria

```
User: continue_investigation OI-0001 "Was this caused by a deploy?"
→ runs get_recent_jobs + get_document_versions
→ updates hypothesis confidence
→ "Deploy to bench-001 at 14:01 correlates with incident start at 14:03"

User: finalize_rca OI-0001
→ returns full RCA markdown
→ stored in Operational Investigation.rca_markdown
→ usable as post-mortem draft without editing
```
