# Incident Management DocType Group Research

This module automates the detection, triage, investigation, and automated remediation of system resource incidents (CPU, Memory, Disk, System Load) across application servers, database servers, and clusters in the Press environment.

## DocType Reference & Role

### [Incident Investigator](press/press/incident_management/doctype/incident_investigator/incident_investigator.py)
- **Status**: Core orchestrator (subclass of `StepHandler`).
- **Triage & Safety Rules**:
  - Rejects self-hosted servers with `ValidationError`.
  - Implements a configurable `cool_off_period` (ignores duplicate incidents in quick succession on the same server).
  - Checks if another server in the same cluster failed in the last minute to suppress cluster-wide alert storms (`is_cluster_spam()`).
- **Core Investigation Lifecycle**:
  1. **Triage**: Runs checks in `before_insert()`.
  2. **Initialization**: In `after_insert()`, populates the `server_investigation_steps` and `database_investigation_steps` children tables with Prometheus checks, sets investigation window (5m before insertion), and enqueues `investigate` via background worker.
  3. **Prometheus Queries**: Uses `PrometheusInvestigationHelper` to hit Grafana/Prometheus API (`node_load5`, `node_cpu_seconds_total`, `node_memory_MemAvailable_bytes`, `/` and `/opt/volumes` mount points). Sets `is_likely_cause` or `is_unable_to_investigate`.
  4. **Reaction/Remediation Planning**:
     - **Database server busy/unreachable**: Captures MariaDB process list via Ansible playbook `capture_process_list.yml`, reboots database VM (via cloud provider APIs or EC2 serial console), and restarts benches via `start_benches.yml`.
     - **App server spikes**: Logs Elasticsearch `earlyoom` OOM kill events, gets recent `Agent Job` executions, and summarizes bench memory usage statistics.
  5. **Findings Serialization**: Records all results into `investigation_findings` (JSON) and executes remediation/diagnostic steps.

### [Incident Pattern](press/press/incident_management/doctype/incident_pattern/incident_pattern.py)
- **Role**: Automatically suggests or applies server scaling plans based on resource threshold breaches (`has_high_cpu_load`, `has_high_system_load`, `has_high_memory_usage`).
- **Logic**:
  - Triggered `after_insert`.
  - Determines next appropriate plan via `server.get_next_plan(requires_cpu, requires_memory)`.
  - If the server is `public`, it automatically upgrades the server via `server_doc.change_plan(plan_name)`.
  - If non-public, it emails the team a recommendation notification using the `plan_upgrade_recommendation` template.

### [Incident Pattern Investigation](press/press/incident_management/doctype/incident_pattern_investigation/incident_pattern_investigation.json)
- **Role**: Child table linking an `IncidentPattern` to an `IncidentInvestigator`.

### [Investigation Step](press/press/incident_management/doctype/investigation_step/investigation_step.py)
- **Role**: Child table representing a single metric query step. Tracks `step_name`, python `method` executed, and whether it was `is_likely_cause` or `is_unable_to_investigate`.

### [Action Step](press/press/incident_management/doctype/action_step/action_step.py)
- **Role**: Child table representing an automated diagnostic or remediation task. Tracks `job_type`, scheduled background `job`, `method_name` to run, `attempt` count, `max_attempt` limits, `status` ("Pending", "Running", "Success", "Failure"), and task console `output`.
- **Optimization**: Has database index on `("parent", "idx")` to accelerate ordered task execution.
