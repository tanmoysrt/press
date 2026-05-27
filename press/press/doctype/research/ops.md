# Press Core: Ops, Monitoring & Audit Research

This document covers operational tooling, Ansible automation, build metrics, security update tracking, audit logging, alerting pipelines, and Telegram notification systems in Press.

---

## Monitoring Stack

### Architecture

Press runs a **global** Monitor Server (Prometheus + Grafana) and Log Server (Elasticsearch). These are not per-cluster — all clusters ship metrics and logs to the central monitoring stack.

```
Each server (n / f / m)
  ├── node_exporter          → system metrics (CPU, RAM, disk, network)
  ├── cadvisor               → Docker container / bench metrics
  ├── mysqld_exporter        → MariaDB metrics (m servers only)
  └── blackbox_exporter      → HTTP probe: GET /api/method/ping for each site

Monitor Server
  ├── Prometheus             → scrapes all exporters; evaluates alert rules
  └── Grafana                → dashboards over Prometheus + Elasticsearch data

Log Server
  └── Elasticsearch          → receives syslog + application logs from all servers
```

### Exporters

| Exporter | Runs on | What it measures |
|----------|---------|-----------------|
| `node_exporter` | all servers | CPU, RAM, disk I/O, filesystem, network |
| `cadvisor` | f servers | Per-container CPU/RAM/network for bench containers |
| `mysqld_exporter` | m servers | MariaDB queries, connections, InnoDB buffer pool |
| `blackbox_exporter` | monitor server | HTTP GET `/api/method/ping` per site — measures availability and latency |

### Alert → Incident flow

```
Prometheus evaluates PrometheusAlertRule (PromQL)
  │  threshold exceeded
  ▼
Alertmanager fires webhook → Press /api/method/press.api.monitoring.alertmanager_webhook
  │
  ▼
AlertmanagerWebhookLog created
  │  matches server/site, classifies alert type
  ▼
Incident created (or existing incident updated)
  │  state: Investigating → Confirmed
  ▼
Incident escalated to team (email / dashboard notification)
  │  optional: IncidentInvestigator auto-remediation pipeline runs
  ▼
Ops team resolves → Incident state: Resolved
```

`PrometheusAlertRule` docs in Press define PromQL expressions + severity. `AlertmanagerWebhookLog` is the entry point for all inbound Prometheus alerts. See `alerts.md` for full doctype details.

---

## Core DocTypes

### [Audit Log](press/press/doctype/audit_log/audit_log.py)
- **Role**: Compliance and operations audit trail for scheduled background checks (backup health, billing accuracy, certificate expiry, etc.).
- **Key Fields**: `audit_type`, `status` (Success / Failure), `log`, `telegram_group`.
- **Key Methods**:
  - `after_insert()` — automatically calls `notify()` on failure.
  - `notify()` — sends structured failure alert to configured Telegram group.

### Ansible Automation Suite

#### [Ansible Play](press/press/doctype/ansible_play/ansible_play.py)
- **Role**: Tracks a single Ansible playbook execution run on a server.
- **Key Fields**: `play`, `playbook`, `server`, `status` (Pending / Running / Success / Failure), `start`/`end`, `duration`, `ok`/`changed`/`failed`/`rescued`/`ignored`/`skipped` (task counters).
- **Key Methods**: `get_list_query()` (permission check on server access), `on_trash()` (cascade deletes child tasks).

#### [Ansible Task](press/press/doctype/ansible_task/ansible_task.py)
- **Role**: Child record of `Ansible Play` representing a single task execution result (task name, status, stdout/stderr output, duration).

#### [Ansible Console](press/press/doctype/ansible_console/ansible_console.py)
- **Role**: Interactive ad-hoc Ansible shell command execution interface. Submits one-off shell module commands to target servers.

#### [Ansible Console Log](press/press/doctype/ansible_console_log/ansible_console_log.py) & [Ansible Console Output](press/press/doctype/ansible_console_output/ansible_console_output.py)
- **Role**: Stores the raw stdout/stderr output from `Ansible Console` runs as structured log lines.

### Build Metrics

#### [Build Metric](press/press/doctype/build_metric/build_metric.py)
- **Role**: Records performance and resource metrics from Docker image build runs — layer sizes, cache hit/miss rates, step durations, and total build time. Used for build pipeline optimization.

#### [Build Cache Shell](press/press/doctype/build_cache_shell/build_cache_shell.py)
- **Role**: Manages cached Docker layer shells used to accelerate repeated app builds. Tracks cache hit state, associated `Deploy Candidate`, and the Docker layer hash.

### Security & Updates

#### [Security Update](press/press/doctype/security_update/security_update.py)
- **Role**: Tracks OS-level security package updates available on servers.
- **Key Fields**: `package`, `server`, `server_type`, `version`, `priority` (High / Medium / Low), `priority_level`, `job_status`, `package_meta`, `change_log`, `datetime`.
- **Key Methods**:
  - `fetch_security_updates()` (static) — runs Ansible to query `apt-get --simulate upgrade` on each server and parse available security patches.
  - `get_package_priority_and_level()` — uses regex to classify packages by CVE severity.

#### [Security Update Check](press/press/doctype/security_update_check/security_update_check.py)
- **Role**: Orchestrates a fleet-wide security update scan across all active servers — groups results by priority and notifies ops team via Telegram.

### Remote & Serial Operations

#### [Remote Operation Log](press/press/doctype/remote_operation_log/remote_operation_log.py)
- **Role**: Records low-level cloud API operations (e.g. EC2 API calls, volume attachments, snapshot creation) with status, error output, and timestamp for debugging and auditing.

#### [Serial Console Log](press/press/doctype/serial_console_log/serial_console_log.py)
- **Role**: Captures EC2/cloud serial console output — used during unresponsive VM investigations when SSH is unavailable. Logs kernel panics, boot errors, and OOM kill messages.

### SQL & Static IP Logs

#### [SQL Playground Log](press/press/doctype/sql_playground_log/sql_playground_log.py)
- **Role**: Audit trail for all SQL queries executed by developers via the SQL Playground console. Stores team, site, query text, execution time, and row count for compliance review.

#### [Static IP Log](press/press/doctype/static_ip_log/static_ip_log.py)
- **Role**: Tracks Elastic IP / static IP address assignments, reassignments, and releases for servers. Maintains history of which server held which IP at what time.

### Scheduled Operations

#### [Scheduled Auto Update Log](press/press/doctype/scheduled_auto_update_log/scheduled_auto_update_log.py)
- **Role**: Records outcomes of automatic bench/site update jobs run on schedule. Stores which sites/benches were updated, success/failure counts, and traceback on failure.

### Resource Tags

#### [Resource Tag](press/press/doctype/resource_tag/resource_tag.py)
- **Role**: Free-form tagging system for Press resources (servers, sites, benches). Enables filtered views, cost allocation, and bulk operations by tag.

### Telegram Notifications

#### [Telegram Group](press/press/doctype/telegram_group/telegram_group.py)
- **Role**: Configures a Telegram chat group (bot token + chat ID) as a notification target for alerts, audit failures, and incident reports.

#### [Telegram Group Topic](press/press/doctype/telegram_group_topic/telegram_group_topic.py)
- **Role**: Maps specific alert categories or server groups to dedicated Telegram group threads/topics for organized routing.

#### [Telegram Message](press/press/doctype/telegram_message/telegram_message.py)
- **Role**: Logs outbound Telegram notification messages with delivery status and content — provides an audit trail for all system alerts sent.
