# Virtual Machine — Deep Dive

Covers the `VirtualMachine` doctype (3291 lines), its multi-cloud abstraction, volume management, image/snapshot lifecycle, and how it relates to server provisioning.

---

## Purpose

`VirtualMachine` is the cloud-layer abstraction. Every server doctype (Server, DatabaseServer, ProxyServer, etc.) is backed by exactly one `VirtualMachine`. Press never calls cloud APIs directly from server code — it always goes through the VM doc.

---

## Series Codes

The `series` field determines what type of server will be created from this VM:

| Series | Server Type |
|--------|------------|
| `n` | App Server (Server) |
| `f` | App Server (large fleet) |
| `m` | Database Server |
| `c` | Monitor Server |
| `p` | Proxy Server |
| `e` | Log Server |
| `r` | Registry Server |
| `u` | Unified Server (app + DB on one VM) |
| `t` | Trace Server |
| `nfs` | NFS Server |
| `fs` | App Server (fs variant) |
| `nat` | NAT Server |

`BIG_SERIES = ["f", "m", "u", "t"]` — these use a different IP calculation formula supporting more than 256 VMs in a cluster.

---

## Fields

### Identity
- `name` — auto-generated from series + cluster index
- `series`, `index` — series code + numeric index within cluster
- `cluster` — link to Cluster
- `domain` — link to Domain
- `team` — optional owner team

### Cloud Config
- `cloud_provider` — AWS EC2 / OCI / Hetzner / DigitalOcean / Frappe Compute
- `region` — link to Region
- `availability_zone` — AZ string
- `machine_type` — instance type (e.g. `t3.large`, `4x8`)
- `platform` — `x86_64` or `arm64`
- `ssh_key` — link to SSH Key doc
- `security_group_id` — cloud provider security group ID
- `machine_image` — cloud provider AMI/image ID
- `kms_key_id` — AWS KMS key for EBS encryption

### Compute
- `vcpu`, `ram` — vCPUs, memory MB

### Storage
- `disk_size` — total data volume GB
- `root_disk_size` — root volume GB
- `has_data_volume` — boolean: separate data volume vs single disk
- `volumes` — child table of `VirtualMachineVolume`
- `temporary_volumes` — child table of `VirtualMachineTemporaryVolume`
- `data_disk_snapshot` — link to `Virtual Disk Snapshot`
- `data_disk_snapshot_attached`, `data_disk_snapshot_volume_id`

### Network
- `private_ip_address`, `public_ip_address`
- `private_dns_name`, `public_dns_name`
- `secondary_private_ip` — used for NAT servers
- `subnet_id`, `subnet_cidr_block`
- `assign_public_ip` — boolean
- `is_static_ip` — boolean

### Status
- `status` — Draft / Pending / Running / Stopped / Terminated
- `instance_id` — cloud provider instance ID
- `termination_protection` — boolean guard
- `ready_for_conversion` — ARM/AMD migration flag
- `disable_server_snapshot` — skip scheduled snapshots

---

## Lifecycle Methods

### Provisioning

```
provision() → _provision_aws()
           → _provision_oci()
           → _provision_hetzner()
           → _provision_digital_ocean()
           → _provision_frappe_compute()
```

- `_provision_aws()` — `ec2.run_instances` with block device mappings, KMS encryption, source/dest check disabled for NAT
- `_provision_oci()` — `LaunchInstanceDetails` with shape config (vCPU/RAM)
- `_provision_hetzner()` — `servers.create` + `attach_to_network` with protection
- `_provision_digital_ocean()` — `droplets.create` with VPC/firewall/SSH key/user data
- `_provision_frappe_compute()` — API call to Frappe Compute service

### State Operations
- `start()`, `stop(force=False)`, `force_stop()`, `reboot()` — lifecycle across all providers
- `terminate(reason=None)` — terminates instance, cleans volumes on Hetzner/DO
- `force_terminate()` — dev mode only; disables termination protection then terminates

### Sync

```
sync() → _sync_aws()           # describe_instances, volumes, IPs, termination protection
       → _sync_oci()           # get_instance, VNIC, volumes with IOPS calc
       → _sync_hetzner()       # server state, volumes, protection
       → _sync_digital_ocean() # droplet state, networks, volumes
       → _sync_frappe_compute()
```

`update_servers()` — after sync, propagates IP/status to all linked server docs.

**Bulk sync** (called from scheduled jobs):
- `bulk_sync_aws()` — chunks all VMs, enqueues `bulk_sync_aws_cluster` per cluster
- `bulk_sync_oci()`, `bulk_sync_hetzner()` — similar batch patterns

---

## Disk / Volume Management

### Attach / Detach
- `attach_new_volume(size, iops, throughput)` — creates + attaches new block volume
- `attach_volume(volume_id, is_temporary_volume=False)` — attaches existing volume
- `detach(volume_id)` — detaches volume
- `delete_volume(volume_id)` — detaches then deletes

### Resize & Performance
- `increase_disk_size(volume_id, increment=50)` — modifies volume size (all providers)
- `convert_to_gp3()` — converts AWS EBS to gp3, updates IOPS/throughput
- `update_ebs_performance(volume_id, iops, throughput)` — modifies AWS EBS performance params
- `get_ebs_performance()` — returns current IOPS/throughput of first EBS volume
- `update_oci_volume_performance(vpus)` — updates OCI volume VPUs (IOPS proxy)

### Device Name Allocation
- `get_next_volume_device_name()` — returns next `/dev/sdX` device path

### Snapshots
```
create_snapshots(exclude_boot_volume, physical_backup, rolling_snapshot) 
  → _create_snapshots_aws()        # create_snapshots API with tags
  → _create_snapshots_oci()        # boot + data volume backups (incremental)
  → _create_snapshots_hetzner()    # server image snapshot
  → _create_snapshots_frappe_compute()
```

### Data Disk Snapshots
- `check_and_attach_data_disk_snapshot_volume()` — attaches snapshot volume if available
- `ensure_no_data_disk_attached_before_attaching_snapshot_disk()` — removes extra disks first
- `create_data_disk_volume_from_snapshot()` — creates EBS volume from snapshot

---

## Machine Images

- `create_image(public=True)` — creates `VirtualMachineImage` doc linked to this VM
- `get_latest_ubuntu_image()` — fetches latest Ubuntu 20.04/22.04 AMI for platform/provider
- `convert_to_arm(vmi, machine_type)` / `convert_to_amd(...)` — creates `VirtualMachineMigration` doc

### VirtualMachineImage (`virtual_machine_image.py`)

Fields: `virtual_machine`, `cluster`, `region`, `image_id`, `snapshot_id`, `status` (Pending/Available/Unavailable), `platform`, `public`, `has_data_volume`, `series`, `size`, `root_size`, `volumes`, `mariadb_root_password`.

Key methods:
- `create_image()` — fires cloud API to create AMI/snapshot/image
- `create_image_from_copy()` — copies image across regions (AWS/DO only)
- `sync()` — polls image status, extracts volumes list (AWS)
- `wait_for_availability()` — retries sync every 60s, 10 attempts
- `copy_image(cluster)` — creates copy doc in different cluster
- `delete_image()` — deregisters/deletes image + associated snapshot
- `set_credentials()` — extracts MariaDB root password for m/u series images
- `get_available_for_series(series, region, platform, cloud_provider)` — queries latest public image

---

## Networking

### IP Calculation
- Index ≤ 256 → `get_private_ip_old_logic()` (simple offset)
- Index > 256 → `get_private_ip_new_logic()` (uses `BIG_SERIES` offsets)

### Static IP
- `attach_static_ip(static_ip)` — associates Elastic IP (AWS only)
- `detach_static_ip()` — disassociates Elastic IP

### Secondary IP (NAT servers)
- `attach_secondary_private_ip()` / `detach_secondary_private_ip()` — manages secondary IP on NAT instances
- `disable_source_dest_check()` / `enable_source_dest_check()` — required for NAT to forward packets

### Firewall
- `attach_to_firewall(firewall_id)` / `detach_from_firewall(firewall_id)` — security groups/NSGs across all providers
- `get_security_groups()` — returns list of security group IDs

---

## Termination Protection

- `enable_termination_protection()` / `disable_termination_protection()` — cloud API guard
- `disable_delete_on_termination_for_all_volumes()` — AWS-specific: modifies block device mapping so EBS volumes survive instance termination

---

## Server Creation from VM

After a VM is provisioned, call the appropriate factory method to create the server doc:

```python
vm.create_server()           # → Server doc (App Server)
vm.create_database_server()  # → Database Server doc
vm.create_proxy_server()     # → Proxy Server doc
vm.create_monitor_server()   # → Monitor Server doc
vm.create_log_server()       # → Log Server doc
vm.create_registry_server()  # → Registry Server doc
vm.create_nat_server()       # → NAT Server doc (series "nat" only)
vm.create_unified_server()   # → Server + Database Server paired (series "u")
```

---

## VirtualMachineVolume Child Table

Fields: `device` (/dev/sdX), `volume_id`, `size` (GB), `volume_type` (gp3/gp2), `iops`, `throughput`, `last_updated_at`, `skip_rightsize`.

---

## Cloud Init

`get_cloud_init()` — generates `cloud-init.yml` from Jinja2 template. Configures:
- MariaDB settings (via `get_mariadb_context()`)
- Logging/syslog
- StatsD
- Filebeat

---

## Status Mappings

| Cloud Status | Press Status |
|---|---|
| AWS: `running` | Running |
| AWS: `stopped` | Stopped |
| AWS: `terminated` | Terminated |
| AWS: `pending` / `shutting-down` / `stopping` | Pending |
| Hetzner: `running` | Running |
| Hetzner: `off` | Stopped |
| OCI: `RUNNING` | Running |
| OCI: `STOPPED` | Stopped |
| OCI: `TERMINATED` | Terminated |

---

## Scheduled Module Functions

- `sync_virtual_machines()` — calls `bulk_sync_aws/oci/hetzner`
- `snapshot_aws_servers()` — creates server snapshots, skips VMs with active press jobs
- `snapshot_aws_internal_virtual_machines()` — snapshots internal servers (non f/m series)
- `snapshot_oci_virtual_machines()`, `snapshot_hetzner_virtual_machines()`, `snapshot_frappe_compute_virtual_machines()` — daily snapshots per provider
- `rolling_snapshot_database_server_virtual_machines()` — rolling snapshots for physical backup support

---

## AWS Serial Console

- `get_serial_console_credentials()` — sends SSH public key via `ec2-instance-connect`, returns endpoint + username (used for unresponsive VM recovery)
- `reboot_with_serial_console()` — delegates to server doc's serial console method
- `AWS_SERIAL_CONSOLE_ENDPOINT_MAP` — region → endpoint + SHA256 fingerprint mapping
