# FC AI Ops — Spec Index

Press-native AI operations assistant for Frappe Cloud. Handles incident investigation, RCA, performance checks, and safe action planning — all from MCP chat.

## Foundational Docs

- [architecture.md](architecture.md) — goal, system shape, code structure, tech direction
- [storage.md](storage.md) — two-doctype storage model
- [permissions.md](permissions.md) — System Manager-only permission model
- [llm-providers.md](llm-providers.md) — OpenAI, Anthropic, and Anthropic-compatible provider settings

## Phases

| Phase | File | Goal | Sprint |
|-------|------|------|--------|
| 0 | [phase-00-mcp-skeleton.md](phase-00-mcp-skeleton.md) | MCP endpoint, System Manager guard, redaction + audit baseline | 1 |
| 1 | [phase-01-read-tools.md](phase-01-read-tools.md) | Incident / document / job read tools | 1 |
| 2 | [phase-02-investigation-runner.md](phase-02-investigation-runner.md) | Storage, tools, runner, playbooks, auto-trigger | 2 |
| 3 | [phase-03-stateful-rca.md](phase-03-stateful-rca.md) | Chat continuation + RCA generation | 3 |
| 4 | [phase-04-safe-actions.md](phase-04-safe-actions.md) | Plan → approve → execute action flow | 4 |
| 5 | [phase-05-expert-tools.md](phase-05-expert-tools.md) | Source-code analysis + raw PromQL / ES | 5 |
| 6 | [phase-06-ui.md](phase-06-ui.md) | FC dashboard chat UI | 6 |

## First Working Version (end of Sprint 2)

Tool: `investigate_incident(incident_name)`

Output:
```
Investigation: OI-0001
Affected: site / server / bench
Timeline: key events
Findings: metrics, logs, jobs
Likely cause + confidence
Recommended next checks
```

## Build Order

**Sprint 1**: Phases 0–1 → MCP skeleton + read tools + safety baseline  
**Sprint 2**: Phase 2 → storage + full investigation runner + playbooks + auto-trigger  
**Sprint 3**: Phase 3 → chat continuation + RCA  
**Sprint 4**: Phase 4 → safe actions  
**Sprint 5**: Phase 5 → expert tools (gated on full safety infra)  
**Sprint 6**: Phase 6 → dashboard UI
