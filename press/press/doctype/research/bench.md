# Press Core: Benches & Deployments Research

This document details the configuration management of Frappe Benches, application release tracking, build systems, deployment pipelines, and release group architectures.

## Core DocTypes

### [Bench](press/press/doctype/bench/bench.py)
- **Role**: Represents a Frappe Bench installation on a physical host (often containerized under Docker).
- **Core Responsibilities**:
  - Acts as the runtime boundary for multiple sites sharing the same codebase versions.
  - Manages site allocation, ensuring that site-to-bench density doesn't cause container memory exhaustion.
  - Tracks installed applications (`bench_app`), global configuration parameters, volume mounts (`bench_mount`), and system-level environment variables (`bench_variable`).
  - Calls agent endpoints to execute tasks: clearing Redis caches, compiling JS/CSS assets, restarting Celery/Gunicorn background processes, and synchronizing user credentials.

### [Deploy](press/press/doctype/deploy/deploy.py)
- **Role**: Coordinates the deployment lifecycle of new code versions to benches.
- **Workflow**:
  - Enqueues jobs to pull down git repositories via SSH keys.
  - Executes bench migrations (`bench --site all migrate`) across all hosted sites in parallel.
  - Re-compiles assets (`bench build`), updates static file paths, restarts background workers, and signals public routers (Proxy Servers) to route traffic safely.
- **[Deploy Bench](press/press/doctype/deploy_bench/deploy_bench.py)**: Maps a deployment run to specific benches.
- **[New Bench Queue](press/press/doctype/new_bench_queue/new_bench_queue.py)**: Queue processor that serializes the provisioning of fresh benches to avoid resource spikes on physical hosts.

### [App Release](press/press/doctype/app_release/app_release.py)
- **Role**: Tracks specific git commits, tags, or release branches of Frappe applications.
- **Key Mechanics**:
  - Resolves dependency trees (`required_apps`) and records differences in schema/code compared to the previous release (`app_release_difference`).
  - Implements **[App Release Approval Request](press/press/doctype/app_release_approval_request/app_release_approval_request.py)**: a formal audit log where system reviewers can approve or reject custom/third-party app versions before they are cleared for bench deployment.
  - Integrates with security auditors (e.g. `Yanked App Release`) to immediately mark specific commits as invalid if a security breach, backdoor, or critical regression is flagged.

### Deploy Candidate & Staging Pipeline
- **[Deploy Candidate](press/press/doctype/deploy_candidate/deploy_candidate.py)**: The central orchestrator for building new bench environments. It acts as a pre-flight staging area.
- **Related Sub-DocTypes**:
  - `deploy_candidate_app` & `deploy_candidate_variable`: Compiles exact git commit hashes and environment configs to be bundled.
  - `deploy_candidate_build` & `deploy_candidate_build_step`: Tracks individual Docker container builds, node package compilations, and static asset generation tasks.
  - `deploy_candidate_difference` & `deploy_candidate_package`: Generates a checklist of differences in app versions and system packages to decide if a hard restart or DB migration is needed.

### Release Groups & Policies
- **[Release Group](press/press/doctype/release_group/release_group.py)**: Logical classification grouping multiple benches and servers together (e.g. "Stable", "Beta", "Experimental").
- **Mechanics**:
  - Enforces version policies: e.g. automatically upgrades benches in this group when a new minor app release is tagged, or schedules quiet-hours rollouts.
  - Compiles global environmental variables (`release_group_variable`), mounting schemes (`release_group_mount`), and system-level python/binary packages (`release_group_package`) to ensure environmental parity across all servers in the cluster.
  - Implements **[Release Pipeline](press/press/doctype/release_pipeline/release_pipeline.py)**: automates rolling upgrades through staging, canary, and finally production release groups.

### Bench Management & Maintenance
- **[Bench Site Update](press/press/doctype/bench_site_update/bench_site_update.py)** & **[Bench Update](press/press/doctype/bench_update/bench_update.py)**: Orchestrates scheduled minor updates, framework patches, and migrations on individual sites without triggering full bench rebuilds.
- **[Bench Shell](press/press/doctype/bench_shell/bench_shell.py)** & **[Bench Shell Log](press/press/doctype/bench_shell_log/bench_shell_log.py)**: Executes secure, sandboxed shell commands on target benches for remote operations and returns console streams.
- **[New Bench Queue](press/press/doctype/new_bench_queue/new_bench_queue.py)**: Serializes fresh bench provisioning to prevent concurrent creation spikes on physical hosts. Fields: `group`, `bench`, `status` (Queued/Started/Failure), `payload`.

### Release Group (expanded)
- **[Release Group](press/press/doctype/release_group/release_group.py)**: Logical grouping of benches/servers sharing the same app versions and environment configuration.
- **Key Fields**: `title`, `version`, `team`, `apps`, `servers`, `dependencies`, `public`, `enabled`, `saas_bench`.
- **Key Methods**: `create_deploy_candidate()`, `deploy_information()`, `add_server()`, `change_app_branch()`, `add_app()`, `remove_app()`, `clone_group()`, `archive()`.
- **Child Tables**: `release_group_app`, `release_group_dependency`, `release_group_mount`, `release_group_package`, `release_group_server`, `release_group_variable` — compile the exact app set, system packages, env vars, and volume mounts applied to every bench in the group.
- **[Release Group Policy](press/press/doctype/release_group_policy/release_group_policy.py)** & **[Release Group Policy App](press/press/doctype/release_group_policy_app/release_group_policy_app.py)**: Defines auto-update rules — e.g. automatically upgrade to the latest patch release when a new minor version is tagged.

### Release Pipeline
- **[Release Pipeline](press/press/doctype/release_pipeline/release_pipeline.py)**: Automates rolling upgrades through staging → canary → production release groups.
- **Key Fields**: `release_group`, `status` (Pending/Running/Success/Failure/Partial Success/Retrying), `workflow`, `pipeline_builds`.
- **Key Methods**: `create_release()`, `run_pre_release_checks()`, `prepare_deployment()`, `orchestrate_build_monitoring()`, `monitor_bench_creation()`, `add_implicit_app_dependencies()`, `auto_update_bench_dependency_versions()`.
- **[Release Pipeline Build](press/press/doctype/release_pipeline_build/release_pipeline_build.py)**: Child table tracking each deploy candidate build within a pipeline run — status, bench target, and timing.

### Deploy Candidate (expanded child tables)
- **[Deploy Candidate](press/press/doctype/deploy_candidate/deploy_candidate.py)** child tables provide granular build configuration:
  - `deploy_candidate_app` — pinned app + git commit hash to bundle.
  - `deploy_candidate_variable` — environment variable overrides for the build.
  - `deploy_candidate_dependency` — resolved system-level dependency versions (Python, Node, wkhtmltopdf).
  - `deploy_candidate_package` — extra OS packages to install in the Docker layer.
  - `deploy_candidate_build` — tracks a single Docker image build attempt: start time, status, log output.
  - `deploy_candidate_build_step` — per-layer build steps within a Docker build run.
  - `deploy_candidate_difference` — delta of changed apps vs previous deploy.
  - `deploy_candidate_difference_app` — per-app breakdown of what changed in the difference.

### Frappe Version
- **[Frappe Version](press/press/doctype/frappe_version/frappe_version.py)**: Defines supported Frappe framework versions available for release groups.
- **Key Fields**: `name`, `number`, `status` (Develop/Beta/Stable/End of Life), `public`, `default`, `dependencies`.
- **[Frappe Version Dependency](press/press/doctype/frappe_version_dependency/frappe_version_dependency.py)**: Child table listing system dependency versions (Python, Node, MariaDB) required by each Frappe version.

### Site Update
- **[Site Update](press/press/doctype/site_update/site_update.py)**: Manages migration of a specific site to a new bench (triggered by app updates or scheduled minor updates).
- **Key Fields**: `site`, `source_bench`, `destination_bench`, `status`, `deploy_type` (Pull/Migrate), `backup_type` (Logical/Physical/Logical Replication), `scheduled_time`.
- **Key Methods**: `start()`, `trigger_recovery_job()`, `get_steps()`, `activate_site()`, `deactivate_site()`, `create_physical_backup()`.
- Distinct from `Version Upgrade` (which changes Frappe major version) — `Site Update` moves the site to an updated bench within the same version.
