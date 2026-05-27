# Press Core: Incidents & Webhooks Research

This document covers system alert policies, incident tracking registers, Prometheus Alertmanager integrations, downstream webhooks, and tracing telemetry.

## Core DocTypes

### [Incident](press/press/doctype/incident/incident.py)
- **Role**: Tracks active service outages, resource spikes, or hardware failures across the host fleet.
- **Workflow**:
  - Automatically created by Alertmanager alert payloads.
  - Links to the affected `Server` or `Site`.
  - Coordinates state transitions: `Investigating`, `Confirmed`, `Validating`, `Acknowledged`, or `Resolved`.
  - Enqueues diagnostic pipelines (like launching an `Incident Investigator`).
  - Records resolution updates (`incident_updates`) and captures user remediation feedback (`incident_suggestion`).
- **[Incident Alerts](press/press/doctype/incident_alerts/incident_alerts.py)**: Tracks individual metrics alerts contributing to the incident.
- **[Incident Settings](press/press/doctype/incident_settings/incident_settings.py)**: Globally configures support contact details, incident priority rules, and threshold metrics.

### Prometheus Alerting Integrations
- **[Alertmanager Webhook Log](press/press/doctype/alertmanager_webhook_log/alertmanager_webhook_log.py)**:
  - Listens to incoming alert streams from Prometheus Alertmanager webhooks.
  - Matches alert definitions (e.g. `DiskFillingUp`, `InstanceDown`, `HighCPUUsage`) to specific servers.
  - Triggers reactive automated remediation jobs (`alertmanager_webhook_log_reaction_job`).
- **[Prometheus Alert Rule](press/press/doctype/prometheus_alert_rule/prometheus_alert_rule.py)** & **[Prometheus Alert Rule Cluster](press/press/doctype/prometheus_alert_rule_cluster/prometheus_alert_rule_cluster.py)**:
  - Formulates standard PromQL query templates (e.g. `node_memory_Active_bytes / node_memory_MemTotal_bytes > 0.90`) and maps alert thresholds across clusters.
- **[Silenced Alert](press/press/doctype/silenced_alert/silenced_alert.py)**: Manages scheduled maintenance window alert silencers to suppress notification storms during rolling upgrades.

### Outgoing Webhooks Framework
- **[Press Webhook](press/press/doctype/press_webhook/press_webhook.py)**: Configures outgoing notification webhooks sent to customer applications (e.g. Slack/Discord channels, team endpoints).
- **Sub-DocTypes**:
  - `press_webhook_event` & `press_webhook_selected_event`: Configures event triggers (e.g. `Site Created`, `Backup Completed`, `Deployment Failed`, `Incident Opened`).
  - `press_webhook_log` & `press_webhook_attempt`: Logs outgoing JSON payloads, network response status codes, execution timestamps, and coordinates retry logic.

### Telemetry & Tracing
- **[GitHub Webhook Log](press/press/doctype/github_webhook_log/github_webhook_log.py)**: Captures incoming webhooks from GitHub (e.g. commit push events, release tagging) to automatically trigger app release pipeline staging.
- **[Inspect Trace ID](press/press/doctype/inspect_trace_id/inspect_trace_id.py)**: Resolves Jaeger OpenTelemetry trace IDs to debug low-level inter-service RPC latency issues.
- **[Downtime Analysis](press/press/doctype/downtime_analysis/downtime_analysis.py)**: Automatically calculates cumulative site downtime statistics for SLA guarantees.
