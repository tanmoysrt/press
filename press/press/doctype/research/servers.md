# Press Core: Servers & Cloud Providers Research

This document covers physical/virtual hosts, database instances, public proxies, networking, providers, replication, telemetry servers, and host-level SSH key controls.

## Core DocTypes

### [Server](press/press/doctype/server/server.py)
- **Role**: High-level abstract representational host supporting Benches and Sites.
- **Key Relationships**: Links to `Virtual Machine` (the active cloud node), `Cluster` (deployment grouping), and `Server Plan` (IOPS/RAM thresholds).
- **Core Responsibilities**:
  - Implements methods to bootstrap the host environment using Ansible playbooks (`setup_server.yml`, `setup_bench_mounts.yml`).
  - Manages host volumes (`server_mount`), active SSH public/private keys, TLS certificate files, and maps database instances (`Database Server`).
  - Orchestrates rolling application container starts via `start_active_benches()`.

### [Virtual Machine](press/press/doctype/virtual_machine/virtual_machine.py)
- **Role**: Connects directly to underlying Cloud APIs (AWS EC2, etc.) to control physical VM instances.
- **Key Mechanics**:
  - Encapsulates AWS SDK (Boto3) client calls to perform VM operations: `provision`, `stop`, `start`, `reboot`, and `terminate`.
  - Manages cloud persistent volumes (`virtual_machine_volume`), temporary swap mounts (`virtual_machine_temporary_volume`), and machine images (`virtual_machine_image`).
  - Implements EBS modification rates validation and snapshots creation for server restore operations.

### Databases & Query Servers
- **[Database Server](press/press/doctype/database_server/database_server.py)**: Manages MariaDB/MySQL database clusters linked to application servers. Controls configuration variables (`database_server_mariadb_variable`), MariaDB metrics, and user connection pools.
- **[Managed Database Service](press/press/doctype/managed_database_service/managed_database_service.py)**: Provisions offsite, cloud-managed DB instances (like AWS RDS) rather than host-local MariaDB setups.
- **[MariaDB Binlog](press/press/doctype/mariadb_binlog/mariadb_binlog.py)** & **[Logical Replication Server](press/press/doctype/logical_replication_server/logical_replication_server.py)**: Manages point-in-time recovery logs (binlogs) and master-slave replication sync jobs.

### Networks & Routers
- **[Proxy Server](press/press/doctype/proxy_server/proxy_server.py)**: Encompasses the public ingress routing engine. Rebuilds and syncs Nginx config templates dynamically to route user domain names to specific host server IP targets.
- **[Bastion Server](press/press/doctype/bastion_server/bastion_server.py)**: Implements secure SSH gatekeepers within private virtual clouds (VPCs) to bridge developer access to internal servers.
- **[NAT Server](press/press/doctype/nat_server/nat_server.py)**: Implements outbound network address translation so private database servers can perform security updates without opening public ingress routes.
- **[Wireguard Peer](press/press/doctype/wireguard_peer/wireguard_peer.py)**: Provisions secure VPN tunnels connecting distributed clusters and developer networks.

### Cloud Orchestration & Regions
- **[Cloud Provider](press/press/doctype/cloud_provider/cloud_provider.py)**: Integrates cloud-specific credentials (AWS Access Keys, IAM Roles, GCP Service Accounts, DigitalOcean Tokens).
- **[Cloud Region](press/press/doctype/cloud_region/cloud_region.py)**: Maps regions (e.g. `us-east-1`, `ap-south-1`) with specific pricing tiers, latency rankings, and default VPC subnets.
- **[Cluster](press/press/doctype/cluster/cluster.py)**: Manages logical cluster topologies (e.g. shared multitenant nodes, isolated hybrid clouds, or self-hosted external clusters).

### Telemetry & Infrastructure Services
- **[Monitor Server](press/press/doctype/monitor_server/monitor_server.py)**: Core Prometheus/Grafana instance collecting system resource metrics from host `node_exporter` daemons.
- **[Log Server](press/press/doctype/log_server/log_server.py)**: ElasticSearch/Kibana centralized logging engine indexing system syslog streams and earlyoom logs.
- **[Trace Server](press/press/doctype/trace_server/trace_server.py)**: Jaeger distributed tracing collector.
- **[NFS Server](press/press/doctype/nfs_server/nfs_server.py)**: Coordinates central file storage sharing via NFS volumes (`nfs_volume_attachment`, `nfs_volume_detachment`) across stateless app server nodes.

### Authentication & Keys
- **[SSH Certificate Authority](press/press/doctype/ssh_certificate_authority/ssh_certificate_authority.py)**: Issues cryptographically signed temporary SSH certificates (`ssh_certificate`) rather than using static authorized public keys to audit developer console operations securely.

### Server Detail & Health

- **[Server Activity](press/press/doctype/server_activity/server_activity.py)**: Audit log of all admin operations performed on a server (plan changes, reboots, SSH access grants, firewall edits).
- **[Server Firewall](press/press/doctype/server_firewall/server_firewall.py)** & **[Server Firewall Rule](press/press/doctype/server_firewall_rule/server_firewall_rule.py)**: Manages cloud-level security group rules attached to a server. `Server Firewall` is the parent; `Server Firewall Rule` is the child with port/protocol/CIDR.
- **[Server Mount](press/press/doctype/server_mount/server_mount.py)**: Child table on `Server` defining bind-mount paths and their source volumes (benches, MariaDB data, etc.).
- **[Server Snapshot](press/press/doctype/server_snapshot/server_snapshot.py)**: Point-in-time server volume snapshot. Tracks snapshot ID, status, size, and cloud provider reference.
  - `server_snapshot_plan` — billing plan for snapshot retention.
  - `server_snapshot_recovery` — tracks restoration attempts from a snapshot.
  - `server_snapshot_site_recovery` — site-level recovery operation from a snapshot.
- **[Server Storage Plan](press/press/doctype/server_storage_plan/server_storage_plan.py)**: Billing plan for extra attached block storage on servers (beyond the base plan disk).
- **[Disk Performance](press/press/doctype/disk_performance/disk_performance.py)**: Records disk I/O latency (read/write ms) from `dd` benchmark tests run via Ansible. Fields: `server`, `server_type`, `read_latency_ms`, `write_latency_ms`. Used to detect degraded EBS volumes.

### Special Server Types

- **[Analytics Server](press/press/doctype/analytics_server/analytics_server.py)**: Plausible Analytics instance. Configured with `domain`, `plausible_password`, `google_client_*` OAuth fields. Provisioned via Ansible (`_setup_server()`).
- **[Self Hosted Server](press/press/doctype/self_hosted_server/self_hosted_server.py)**: Manages externally hosted servers brought into Press management. Key fields: `ip`, `private_ip`, `mariadb_ip`, `mariadb_root_password`, `proxy_server`, `database_server`, `ssh_user`, `ssh_port`. Methods: `fetch_apps_and_sites()`, `create_application_server()`, `create_database_server()`, `create_proxy_server()`, `check_minimum_specs()`.
  - `self_hosted_site_apps` — child table listing apps discovered on self-hosted sites.
- **[Registry Server](press/press/doctype/registry_server/registry_server.py)**: Docker image registry. Stores built bench images for deployment. Fields: `registry_username`, `registry_password`, `docker_data_mountpoint`, `bucket_name`, `is_mirror`. Methods: `prune_mirror_registry()`, `create_registry_mirror()`. Module function: `delete_old_images_from_registry()`.

### MariaDB Operations

- **[MariaDB Stalk](press/press/doctype/mariadb_stalk/mariadb_stalk.py)**: Captures MariaDB diagnostic snapshots (process list, InnoDB status, slow query log) during high-load incidents. Module functions: `fetch_stalks()`, `fetch_server_stalks()`. Child table: `mariadb_stalk_diagnostic`.
- **[MariaDB Upgrade](press/press/doctype/mariadb_upgrade/mariadb_upgrade.py)**: Workflow-based MariaDB version upgrade with automatic rollback. Fields: `database_server`, `snapshot`, `status`, `upgrade_play`, `downgrade_play`, `auto_downgrade_version_in_case_of_failure`. Methods: `start()`, `create_disk_snapshot()`, `upgrade_mariadb_version()`, `downgrade_mariadb_version()`.
  - `mariadb_upgrade_step` — child table of upgrade/downgrade step execution.
- **[MariaDB Variable](press/press/doctype/mariadb_variable/mariadb_variable.py)**: Defines allowed `SET GLOBAL` MariaDB configuration variables that can be tuned on database servers.
- **[Logical Replication Server](press/press/doctype/logical_replication_server/logical_replication_server.py)**: Manages MariaDB logical replication (binlog-based master-replica) setup between database servers.
  - `logical_replication_backup` — backup records taken during replication setup.
  - `logical_replication_step` — step-by-step execution log for replication configuration.
- **[MariaDB Binlog](press/press/doctype/mariadb_binlog/mariadb_binlog.py)**: Tracks binary log files on database servers for point-in-time recovery. Used with logical replication to restore sites to specific timestamps.

### Physical Backup System

- **[Physical Backup Group](press/press/doctype/physical_backup_group/physical_backup_group.py)**: Orchestrates bulk physical (filesystem-level) backups across many sites simultaneously. Fields: `site_backups` (child), `no_of_sites`, `successful_backups`. Methods: `sync()`, `trigger_next_backup()`, `retry_failed_backups()`, `delete_backups()`, `create_duplicate_group()`.
  - `physical_backup_group_site` — child table mapping each site to its backup status in the group.
- **[Physical Backup Restoration](press/press/doctype/physical_backup_restoration/physical_backup_restoration.py)**: Orchestrates site restoration from a physical backup. Tracks steps in `physical_backup_restoration_step`.
- **[Physical Restoration Test](press/press/doctype/physical_restoration_test/physical_restoration_test.py)**: Automated integrity test restores from physical backups. Records test results in `physical_restoration_test_result`.

### Failover Systems

- **[Proxy Failover](press/press/doctype/proxy_failover/proxy_failover.py)**: Orchestrates proxy server failover. 16+ step workflow: `stop_replication()`, `attach_static_ip_to_secondary()`, `update_app_servers()`, `switch_primary()`. Fields: `primary`, `secondary`, `failover_steps`, `status`, `error`. Method: `execute_failover_steps()`, `force_continue()`.
  - `proxy_failover_steps` — child table of step execution status.
  - `proxy_server_domain` — child table on `Proxy Server` mapping domains to routing targets.
- **[NAT Failover](press/press/doctype/nat_failover/nat_failover.py)**: Automates NAT server failover — migrates static IP and secondary private IP to standby instance. Methods: `attach_static_ip_to_secondary()`, `configure_secondary_private_ip_on_secondary()`, `update_servers()`, `test_server_egress()`.
  - `nat_failover_steps` — child table tracking each failover step.
- **[On Prem Failover](press/press/doctype/on_prem_failover/on_prem_failover.py)**: Sets up on-premises server as a warm standby via WireGuard VPN + lsyncd/rsync database replication. Fields: `app_server`, `database_server`, `team`, `cluster`, `wireguard_*`, `is_lsyncd_running_for_db`. Methods: `setup_wireguard_on_*_server()`, `setup_failover()`, `teardown_failover()`, `setup_db_lsync_for_initial_sync()`, `_setup_and_configure_database_replica()`.

### NFS Volume Operations

- **[NFS Volume Attachment](press/press/doctype/nfs_volume_attachment/nfs_volume_attachment.py)**: Manages attaching an NFS volume to an app server for shared file storage.
  - `nfs_volume_attachment_step` — tracks each step in the attachment workflow.
- **[NFS Volume Detachment](press/press/doctype/nfs_volume_detachment/nfs_volume_detachment.py)**: Manages safe NFS volume unmounting and detachment.
  - `nfs_volume_detachment_step` — step execution tracking.
