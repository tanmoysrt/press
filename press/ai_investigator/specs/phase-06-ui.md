# Phase 14 — Chat UI

**Sprint**: 6  
**Goal**: AI Ops chat workspace inside Press dashboard. 2-panel layout. No right context panel — investigation state surfaces inline in chat.

---

## Approach

`/dashboard/ai` in the Press Frappe app. Frappe UI (Vue) only. No React, no SQLite. Data via Frappe resource/document APIs and AI Ops backend methods.

---

## Routes

| Path | View |
|---|---|
| `/dashboard/ai` | New chat / empty state |
| `/dashboard/ai/:name` | Investigation or general chat thread |

---

## Layout

2 panels. No right context panel.

```
┌─────────────────┬──────────────────────────────────────────────────┐
│ AI Ops          │ Chat thread                                        │
│ [+ New]         │                                                    │
│                 │                                                    │
│ Today           │                                                    │
│ ● INC-123 RCA   │                                                    │
│ ○ bench-001     │                                                    │
│                 │                                                    │
│ Yesterday       │                                                    │
│ ○ DB pressure   │                                                    │
│ ○ deploy corr.  │                                                    │
│                 │                                                    │
│                 │                                                    │
│                 │  ┌──────────────────────────────────────────────┐ │
│                 │  │ Ask about a site, server, bench, incident...  │ │
│                 │  └───────────────────────────────────── [Send] ─┘ │
└─────────────────┴──────────────────────────────────────────────────┘
```

Left sidebar: 240px fixed. Status dot (● running, ○ done, ✕ failed). Title + relative time. Search at top. Scrollable.

---

## Chat Thread — States

### Empty state

```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│              FC AI Assistant                             │
│              System Manager only                         │
│                                                          │
│   What do you want to investigate?                       │
│                                                          │
│   [Investigate an incident]  [Check a site]              │
│   [Check a server]           [Why was X slow?]           │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Ask about a site, server, bench, incident...       │  │
│  └──────────────────────────────────────── [Send] ───┘  │
└──────────────────────────────────────────────────────────┘
```

Suggestion chips route to pre-filled composer. Nothing is mandatory.

---

### Investigation in progress

```
┌──────────────────────────────────────────────────────────┐
│ INC-123 · Incident RCA                     Running...    │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  You                                                     │
│  Investigate INC-123                                     │
│                                                          │
│  Assistant                                               │
│  Started. Running first pass on INC-123...               │
│                                                          │
│  ▸ get_incident_details                     ✓  80ms      │
│  ▸ get_site_error_logs                      ✓  1.2s      │
│  ▸ get_site_request_summary                 …            │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ [disabled while running]                           │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

Tool rows: collapsed by default, click to expand. Spinner on in-flight row. Composer disabled while first pass runs.

---

### Investigation complete

```
┌──────────────────────────────────────────────────────────┐
│ INC-123 · Incident RCA                                   │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  You                                                     │
│  Investigate INC-123                                     │
│                                                          │
│  Assistant                                               │
│  5xx errors spiked at 14:03, two minutes after the       │
│  deploy completed. ImportError in app logs confirms      │
│  the deploy introduced a broken import.                  │
│                                                          │
│  ▸ get_site_error_logs       ✓  1.2s                     │
│  ▸ get_site_request_summary  ✓  420ms                    │
│  ▸ get_recent_jobs           ✓  310ms                    │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │ Completed · 78% confident                        │   │
│  │ Cause: Deploy introduced application import error │   │
│  │                                                   │   │
│  │ [Generate RCA]              [Recommended Actions] │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Ask a follow-up...                        [Send]  │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

Summary card appears after first pass completes. Always at bottom of assistant response, above composer.

---

### Tool call expanded

```
  ▾ get_site_error_logs  ✓  1.2s
  ┌────────────────────────────────────────────────────────┐
  │ site: customer.example.com                             │
  │ from: 2026-05-27 13:30  to: 2026-05-27 14:30          │
  │ ─────────────────────────────────────────────────      │
  │ Found 47 errors. ImportError: cannot import 'utils'    │
  │ repeated 43x starting 14:03:12.                        │
  └────────────────────────────────────────────────────────┘
```

Input above the line, output summary below. No JSON. No raw data. Plain English.

---

### Action recommendation (in chat)

```
  Assistant
  Bench workers are still unresponsive. Recommending restart.

  ┌────────────────────────────────────────────────────────┐
  │ Action: restart bench-001                              │
  │ Reason: web workers unresponsive for >5 min            │
  │ Impact: brief downtime ~30s                            │
  │ Expires: 14:30:00                                      │
  │                                          [Approve] ──→ │
  └────────────────────────────────────────────────────────┘
```

[Approve] opens confirmation modal. No token entry — dashboard handles token automatically.

---

### Action confirmation modal

```
  ┌───────────────────────────────────────────────────────┐
  │ Confirm Action                                        │
  ├───────────────────────────────────────────────────────┤
  │ restart bench-001                                     │
  │                                                       │
  │ Reason        web workers unresponsive for >5 min     │
  │ Impact        brief downtime ~30s                     │
  │ Current state workers still unhealthy (re-checked)    │
  │ Expires       14:30:00                                │
  │                                                       │
  │                          [Cancel]  [Approve & Run]    │
  └───────────────────────────────────────────────────────┘
```

Backend re-checks target state on modal open. No manual token entry in the UI — token passed automatically on confirm. If using MCP directly, the plan log entry shows the token once.

---

### RCA view (inline)

Clicking [Generate RCA] appends RCA as a markdown block in the chat thread. No separate page.

```
  Assistant
  ──────────────────── RCA ────────────────────────────────

  ## INC-123 Root Cause Analysis
  **Date**: 2026-05-27  **Confidence**: 78%

  ### Summary
  Deploy at 14:01 introduced a broken import. 5xx began
  at 14:03. Site was degraded for 22 minutes.

  ### Timeline
  ...

  ### Recommended follow-up
  ...
  ──────────────────────────────────────────────────────────
  [Copy RCA]  [Download .md]
```

---

## Incident page section

One compact section added to the Incident doctype form. No full UI embedded.

```
┌─────────────────────────────────────────────────────────────────┐
│ AI Investigation                                                │
├─────────────────────────────────────────────────────────────────┤
│ OI-00042 · Completed · 78% confident          [Open in AI Ops] │
│ Cause: Deploy introduced application import error.             │
└─────────────────────────────────────────────────────────────────┘
```

When no investigation exists:

```
┌─────────────────────────────────────────────────────────────────┐
│ AI Investigation                                                │
│                                            [Investigate with AI]│
└─────────────────────────────────────────────────────────────────┘
```

[Investigate with AI] calls `start_investigation(incident_name)`, opens `/dashboard/ai/:name`.

---

## Sidebar

```
┌─────────────────┐
│ AI Ops    [+ New]│
│ ┌─────────────┐ │
│ │ Search...   │ │
│ └─────────────┘ │
│                 │
│ Today           │
│ ● INC-123 RCA   │
│ ○ bench-001     │
│                 │
│ Yesterday       │
│ ○ DB pressure   │
└─────────────────┘
```

Status dots: ● blue = running, ○ grey = done, ✕ red = failed, △ yellow = needs human.  
No filter tabs. Status is visible from the dot.

---

## Components

Frappe UI only:
- `Button`, `TextArea`, `Badge`, `Tooltip`, `Dialog`
- `FeatherIcon` for tool status icons
- Frappe Charts for metric tool outputs (inside expanded tool rows)

---

## Checklist

- [ ] Register `/dashboard/ai` and `/dashboard/ai/:name` routes
- [ ] 2-panel shell: sidebar + chat thread
- [ ] Sidebar: list, search, status dots, [+ New]
- [ ] Empty state with suggestion chips
- [ ] Message stream: user, assistant, tool rows, summary card, RCA block, action card
- [ ] Tool row: collapsed by default, click to expand input/output
- [ ] Summary card appears after first pass completes
- [ ] Composer disabled while first pass running
- [ ] [Generate RCA] appends markdown block inline
- [ ] Action card → confirmation modal → execute (token handled automatically)
- [ ] Incident page compact section: linked investigation or [Investigate with AI]
- [ ] System Manager gate on route and all API calls
- [ ] Polling for status while investigation is Running

## Success Criteria

System Manager opens `/dashboard/ai`, types "Investigate INC-123", sees tool calls run, reads findings, clicks Generate RCA, gets markdown. All without leaving chat. No right panel, no tabs, no drawer management.
