# Press Core: Jobs & Ansible Execution Research

This document covers background system job runtimes, agent daemon job tracking, Ansible playbooks execution, remote shell logs, and scaling steps.

## Core DocTypes

### [Press Job](press/press/doctype/press_job/press_job.py)
- **Role**: Coordinates high-level, multi-step system workflows on the Press backend.
- **Workflow**:
  - Links to a specific `Press Job Type` which defines a pre-configured template of execution steps (`press_job_type_step`).
  - Sequentially fires and tracks steps (`press_job_step`). If a step fails, it halts or triggers rollback routines depending on the type policy.
  - Examples of Press Jobs: cluster provisioning, proxy routing tables rebuilds, or mass framework updates.

### [Agent Job](press/press/doctype/agent_job/agent_job.py)
- **Role**: The primary asynchronous execution bridge between Press (Frappe Cloud) and the agent daemon running on the customer hosts.
- **Key Mechanics**:
  - Enqueues command execution payloads (e.g. provision new site, create database dump, run bench migrate) via Celery/Redis queues on the target host.
  - Implements **[Agent Job Step](press/press/doctype/agent_job_step/agent_job_step.py)**: tracks low-level sub-actions running locally on the bench.
  - Coordinates callbacks (`agent_job_callback`) to return standard outputs (stdout/stderr) and exit status signals to Press.
  - Tracks network request/handshake drops via **[Agent Request Failure](press/press/doctype/agent_request_failure/agent_request_failure.py)** logs to diagnose agent connectivity drops.
  - Supports automated self-updating via **[Agent Update](press/press/doctype/agent_update/agent_update.py)** and **[Agent Update Server](press/press/doctype/agent_update_server/agent_update_server.py)** logs.

### Ansible Execution Suite
- **[Ansible Play](press/press/doctype/ansible_play/ansible_play.py)** & **[Ansible Task](press/press/doctype/ansible_task/ansible_task.py)**:
  - Tracks execution of systemic server setup tasks (Docker configurations, MariaDB variable updates, kernel tweaks) using Ansible engine playbooks.
  - Records real-time JSON task outcomes, tracking changed, failed, ok, or skipped counts per server host.
- **[Ansible Console](press/press/doctype/ansible_console/ansible_console.py)**, `ansible_console_log`, & `ansible_console_output`:
  - Implements an interactive terminal emulator inside the Press Admin Desk allowing system admins to run ad-hoc command line queries on active servers securely, logging outputs and traceback dumps.

### Remote Operations & Scaling
- **[Remote Operation Log](press/press/doctype/remote_operation_log/remote_operation_log.py)**: Records audit trails of low-level commands sent to remote servers (e.g. systemctl stops, disk mount manipulations).
- **[Remote File](press/press/doctype/remote_file/remote_file.py)**: Tracks S3-compatible backup file objects (database dumps, file archives) stored offsite for sites. See `sites.md` for full detail.
- **[Scale Step](press/press/doctype/scale_step/scale_step.py)**: Child table tracking host scale-up or scale-down lifecycle progress.
