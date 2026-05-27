Instructions for AI coding agents (Claude Code, Cursor, Copilot, etc.) working in this repository.

---

> **REQUIRED — do this before anything else:**
> Read [`press/press/doctype/research/overview.md`](press/press/doctype/research/overview.md).
> Do **not** grep, glob, or open source files until you have read it.
> It contains the full architecture map and index of all research files.
> Reading it will save you from exploring the wrong modules.
>
> To read large doctype use `jq` and `grep` instead of reading the whole file. 
---

# Press

100% open-source cloud hosting for the Frappe stack.

## Codebase Research

All detailed research lives in `press/press/doctype/research/`.
After reading `overview.md`, check the relevant research file for the area you are working in before touching source code.

## Module Layout

| Path                         | Purpose                                              |
| ---------------------------- | ---------------------------------------------------- |
| `press/press/`               | Core doctypes — sites, servers, billing, teams       |
| `press/workflow_engine/`     | Async task engine (`PressWorkflow`, `@flow`/`@task`) |
| `press/saas/`                | SaaS trial pooling and instant provisioning          |
| `press/incident_management/` | Incident triage and auto-remediation                 |
| `press/infrastructure/`      | VM-level ops — disk resize, migration, SSH audit     |
| `press/marketplace/`         | App marketplace — audits, plans, subscriptions       |
| `press/partner/`             | Partner network — approvals, leads, territories      |
| `press/experimental/`        | Experimental features                                |
| `press/playbooks/`           | Ansible playbooks (357+) and roles                   |
| `press/api/`                 | Whitelisted API endpoints                            |
| `press/agent.py`             | HTTP client to the agent daemon                      |
| `press/runner.py`            | Ansible runner and callback capture                  |

## Stack

| Layer    | Technology              |
| -------- | ----------------------- |
| Backend  | Python 3.10, Frappe v15 |
| Frontend | Vue 3 + Frappe UI       |
| Linter   | `ruff`                  |

## Code Rules

- Max 800 lines per file, max 30 lines per method.
- Every public class and method gets a single-line docstring — name does the heavy lifting, docstring covers only what the name cannot convey.
- No abbreviations in function or variable names.
- Follow OOP practices. Reuse, don't repeat.
- Write tests for every change. Run related tests before committing.
- Never run tests on the current development site. Use `test.local` — if it doesn't exist, ask the user for the test site name before running anything.
- Code should be readable without a wiki.
- **Type annotations**: All new whitelisted methods must have full type annotations on parameters. Add type hints to other new methods also wherever it doesn't complicate readability — skip if the annotation would be unwieldy (e.g., deeply nested generics).

## Frontend Rules

- All UI uses Frappe UI components — no bespoke HTML/CSS for standard patterns (buttons, dialogs, lists, badges, inputs).
- Data fetching uses Frappe UI resource primitives: `createDocumentResource`, `createListResource`, `createResource`. No raw `fetch`/`axios`.
- New entities follow the object definition pattern (`objects/*.js`) — one file drives both list and detail pages via `generateRoutes`.
- Whitelisted backend methods are declared in the object's `whitelistedMethods` map and called via `.submit()` on the document resource.
- See [`press/press/doctype/research/ui.md`](press/press/doctype/research/ui.md) for full patterns.

## Commit Rules

- Follow [Conventional Commits](https://www.conventionalcommits.org/).
- Subject: sentence case, max 80 characters, scope in kebab-case.
- Put extra context in the commit body.
- If pre-commit hooks fail, fix the reported errors and retry the commit — never skip hooks.

## Maintenance

Update research docs whenever doctypes or implementation change.
