# Press Core: Clusters & Cloud Infrastructure Research

This document covers cloud provider integrations, cluster provisioning, virtual machine lifecycle, auto-scaling, backup storage, and volume management in the Press engine.

---

## Cluster Topology & Request Flow

Each cluster is a self-contained deployment unit in one geographic region. A standard cluster contains:

| Series | Server Type | Role |
|--------|-------------|------|
| `n` | Proxy Server | Public ingress — Nginx, TLS termination, routes to app servers |
| `f` | App Server (Server) | Hosts bench containers and site workers |
| `m` | Database Server | MariaDB, reachable only over private network |
| `u` | Unified Server | App + DB co-located (cost-optimized single-tenant) |

### Request flow

```
Internet
  │
  ▼
n server (Proxy / Nginx)          ← public IP, wildcard TLS
  │  routes by Host header
  ▼
f server (App Server / Nginx)     ← private IP only
  │  upstream = bench container (gunicorn)
  ▼
Bench container                   ← Docker, gunicorn workers + Redis
  │
  ▼
m server (Database Server)        ← private IP only, MariaDB
```

- The `n` server holds all Nginx site configs; when a site is created/migrated, Press re-generates and reloads Nginx on `n`.
- The `f` server runs a second Nginx layer that forwards to the specific bench container port.
- The `m` server is never exposed publicly; `f` servers reach it directly over the cluster's private network (Hetzner private network, AWS VPC subnet, etc.).

### Monitoring servers (global, not per-cluster)

| Server Type | Role |
|-------------|------|
| Monitor Server | Prometheus + Grafana — scrapes exporters on all servers |
| Log Server | Elasticsearch — receives logs from all servers |
| Trace Server | Jaeger — receives distributed traces |

---

## Server Provisioning Model

Two paths depending on whether a cloud provider supports machine images (VMI):

### Generic VM providers (no VMI workflow)

1. Provision VM via cloud API.
2. Run `Setup Server` Ansible play (`setup_server.yml`) on the new VM.
3. Server is ready.

### Managed clusters (AWS, Hetzner, OCI — VMI workflow)

1. Provision and configure a reference VM manually (n, f, or m server type).
2. Run the full Ansible setup (`setup_n_server.yml`, `setup_f_server.yml`, `setup_m_server.yml`) on the reference VM.
3. Create a **Virtual Machine Image** (AMI / Hetzner snapshot) from the configured VM.
4. All future servers of that type boot from this VMI — no Ansible setup needed, just provision + agent registration.

This means `VirtualMachineImage` is the golden image for the cluster. When a cluster needs a new app server (e.g. auto-scale), Press provisions a new VM from the stored image and skips the full setup play.

---

## Core DocTypes

### [Cluster](press/press/doctype/cluster/cluster.py)
- **Role**: Logical grouping of cloud resources (VMs, networks, security groups) in a single geographic region.
- **Key Fields**: `cloud_provider`, `region`, `vpc_id`, `subnet_id`, `security_group_id`, `ssh_key`, `cidr_block`.
- **Supported Providers**: AWS EC2, OCI, Hetzner, DigitalOcean, Frappe Compute.
- **Key Methods**:
  - `create_server()` — provisions new App / DB / Proxy / Monitor / Log / NFS / NAT servers inside the cluster.
  - `create_unified_server()` — co-locates app + database on a single VM (cost-optimized single-tenant setup).
  - `check_machine_availability()` — validates that the requested instance type is available in the region.
  - `create_firewall()` / `delete_firewall()` — manages cloud security groups/firewall rules.
  - `provision_on_aws_ec2()`, `provision_on_oci()`, `provision_on_hetzner()`, `provision_on_digital_ocean()`, `provision_on_frappe_compute()` — cloud-specific provisioning logic.

### [Cluster Plan](press/press/doctype/cluster_plan/cluster_plan.py)
- **Role**: Defines allowed server plan configurations (CPU, RAM, disk) available inside a cluster. Controls which server sizes can be provisioned in a given cluster/region.

### [Cloud Provider](press/press/doctype/cloud_provider/cloud_provider.py)
- **Role**: Singleton configuration document storing credentials and settings for each cloud provider (AWS, OCI, Hetzner, etc.).

### [Cloud Region](press/press/doctype/cloud_region/cloud_region.py)
- **Role**: Maps cloud provider region identifiers (e.g. `ap-south-1`) to human-readable names and availability metadata.

### [Root Domain](press/press/doctype/root_domain/root_domain.py)
- **Role**: Manages the primary DNS zone used for subdomain routing of all hosted sites.
- **Key Fields**: `dns_provider` (AWS Route 53 / Generic), `aws_access_key_id`, `aws_secret_access_key`, `default_cluster`, `default_proxy_server`, `enabled`.
- **Key Methods**:
  - `after_insert()` — enqueues TLS wildcard certificate provisioning via Let's Encrypt.
  - `obtain_root_domain_tls_certificate()` — requests wildcard TLS cert for `*.domain.tld`.
  - `remove_unused_cname_records()` — periodic cleanup of stale DNS entries.
  - `update_dns_records_for_sites()` — batch DNS record sync for all sites under this domain.
  - `add_to_proxies()` — distributes TLS cert and routing config to all proxy servers.

### [Virtual Machine](press/press/doctype/virtual_machine/virtual_machine.py)
- **Role**: Represents a cloud VM instance (EC2, OCI compute, Hetzner droplet, DigitalOcean droplet).
- **Key Fields**: `instance_id`, `cluster`, `machine_type`, `disk_size`, `volumes` (child table), `status`, `series` (n/f/m/u/fs/nat — determines workload role).
- **Key Methods**:
  - `provision()` — creates VM via cloud provider API.
  - `sync()` — refreshes status, IP addresses, and volume attachments from cloud APIs.
  - `reboot()`, `start()`, `stop()`, `terminate()` — full VM lifecycle controls.
  - `increase_disk_size()` — grows EBS/block storage without downtime.
  - `create_snapshots()` — snapshots all attached volumes for backup.
  - `create_image()` — creates a machine image (AMI) from the running VM for cloning.
  - `enable_termination_protection()` / `disable_termination_protection()` — safety guard.

### [Virtual Machine Image](press/press/doctype/virtual_machine_image/virtual_machine_image.py)
- **Role**: Tracks AMI / machine image records created from VMs. Used to launch new instances from a known-good base state.

### [Virtual Machine Volume](press/press/doctype/virtual_machine_volume/virtual_machine_volume.py)
- **Role**: Child table representing a block storage volume (EBS, OCI Block Volume) attached to a VM. Tracks `volume_id`, `device`, `size`, `iops`, `throughput`.

### [Virtual Machine Image Volume](press/press/doctype/virtual_machine_image_volume/virtual_machine_image_volume.py)
- **Role**: Child table on `Virtual Machine Image` mapping volumes included in a machine image snapshot.

### [Virtual Machine Temporary Volume](press/press/doctype/virtual_machine_temporary_volume/virtual_machine_temporary_volume.py)
- **Role**: Tracks ephemeral scratch volumes created during disk resize or migration operations — deleted after the operation completes.

### [Virtual Disk Snapshot](press/press/doctype/virtual_disk_snapshot/virtual_disk_snapshot.py)
- **Role**: Records point-in-time EBS/block volume snapshots for DR and backup purposes. Tracks snapshot ID, source volume, creation time, and status.

### [Backup Bucket](press/press/doctype/backup_bucket/backup_bucket.py)
- **Role**: Configures S3-compatible object storage buckets used for offsite site backup uploads.
- **Key Fields**: `bucket_name`, `cluster`, `endpoint_url`, `region`, `replication_bucket`, `replication_enabled`, `replication_endpoint_url`, `replication_region`.
- **Design**: Supports cross-region replication for geo-redundant backup retention.

### [Backup Restoration Test](press/press/doctype/backup_restoration_test/backup_restoration_test.py)
- **Role**: Orchestrates automated test restores of site backups to verify backup integrity. Creates a temporary site, restores the backup, validates the result, and archives the test site.

### [Auto Scale Record](press/press/doctype/auto_scale_record/auto_scale_record.py)
- **Role**: Orchestrates horizontal scale-up/scale-down of server pairs (primary + secondary) in response to load triggers.
- **Key Fields**: `primary_server`, `secondary_server`, `action` (Scale Up / Scale Down), `status`, `scale_steps` (child table).
- **Scale-Up Flow**: Start secondary VM → expose Redis → switch traffic → setup upstream → mark scaled.
- **Scale-Down Flow**: Switch back to primary → stop secondary → create usage record.
- **Key Methods**:
  - `before_insert()` — populates `scale_steps` based on action type.
  - `execute_scale_steps()` — enqueues async sequential step execution.
- **Module Functions**: `validate_scaling_schedule()`, `create_prometheus_rule_for_scaling()`, `calculate_secondary_server_price()`.

### [Auto Scale Trigger](press/press/doctype/auto_scale_trigger/auto_scale_trigger.py)
- **Role**: Defines Prometheus metric thresholds that trigger auto-scaling. Links a Prometheus alert rule to an `Auto Scale Record` creation action.

### [Scale Step](press/press/doctype/scale_step/scale_step.py)
- **Role**: Child table on `Auto Scale Record` representing a single step in the scale-up/down workflow with `status`, `method`, and `output` tracking.

### [Region](press/press/doctype/region/region.py)
- **Role**: Canonical geographic region record (distinct from `Cloud Region`). Maps region codes to human-readable names, continent, and country — used for UI display and geo-based routing logic.

### [Disk Performance](press/press/doctype/disk_performance/disk_performance.py)
- **Role**: Records disk I/O benchmark results per server. Fields: `server`, `server_type` (Server/Database Server), `read_latency_ms`, `write_latency_ms`. Method: `check_disk_read_write_latency()` runs `dd` tests via Ansible to detect degraded EBS/block volumes. Also documented in `servers.md`.
