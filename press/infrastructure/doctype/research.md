# Infrastructure DocType Group Research

This module manages low-level VM host and filesystem infrastructure lifecycle actions (AWS EC2 operations, Ansible execution, security audits, and storage volume modifications) within the Press ecosystem.

## DocType Reference & Role

### [Virtual Disk Resize](press/press/infrastructure/doctype/virtual_disk_resize/virtual_disk_resize.py)
- **Role**: Automates zero-loss AWS EBS volume shrinking for ext4 partitions.
- **Workflow Steps**:
  1. **Performance Boost**: Scales up IOPS and throughput of the source EBS volume to accelerate transfer rates.
  2. **Provisioning**: Attaches a new, smaller target volume and formats it as `ext4`.
  3. **Tear-down Preparation**: Stops target service (Docker or MariaDB) and stops Filebeat to release file handles.
  4. **Snapshot Backup**: Safety snapshots the old volume.
  5. **Data Copying**: Calls `rsync -x` via Ansible to copy all data from the old mount point to the new volume temporary mount `/opt/volumes/resize`.
  6. **UUID/Mount Swapping**: Unmounts both volumes, updates `/etc/fstab` with the new UUID using `sed`, reloads systemd daemon, and mounts the new volume onto the original directory (`/opt/volumes/benches` or `/opt/volumes/mariadb`).
  7. **Recovery**: RESTARTS stopped services, reverts the new volume to standard baseline EBS performance limits, deletes the old volume from AWS, and reboots target VM (if f-series).

### [Virtual Machine Migration](press/press/infrastructure/doctype/virtual_machine_migration/virtual_machine_migration.py)
- **Role**: Coordinates migration of active VMs to different AWS EC2 machine types (e.g. x86 to ARM64 architectural upgrades).
- **Workflow Steps**:
  1. **Docker Cleanup**: Stops and removes active container configurations to avoid volume lock issues.
  2. **Partition Label Reset**: Updates ext4 label (`e2label`) and vfat label (`fatlabel`) of the root filesystem (e.g. `cloudimg-rootfs` to `old-rootfs`) so the old drive doesn't cause boot conflicts.
  3. **Safe Shutdown**: Stops the VM, disables delete-on-termination on all attached EBS volumes, and terminates the EC2 instance.
  4. **VM Recreation**: Provisions a new instance in-place with the upgraded AMI/instance type, reusing existing IP configurations.
  5. **Volume Swapping**: Attaches all detached data volumes to the new instance.
  6. **Security Swap**: Removes old SSH host key signature locally using `ssh-keygen -R` to prevent signature mismatch warnings.
  7. **Mount Repair**: Updates `/etc/fstab` on the new instance, runs `chown` permissions to repair ownership UID/GIDs on bind mounts, and updates Ansible configurations and platform fields to `arm64`.

### [Virtual Machine Replacement](press/press/infrastructure/doctype/virtual_machine_replacement/virtual_machine_replacement.py)
- **Role**: Orchestrates direct replacement of a degraded VM with a fresh instance, handling detaching/reattaching volumes and migrating elastic IP mappings.

### [SSH Access Audit](press/press/infrastructure/doctype/ssh_access_audit/ssh_access_audit.py)
- **Role**: Automated fleet-wide SSH authorized keys scanner and security compliance manager.
- **Workflow**:
  - Dynamically builds an Ansible inventory of all active non-hybrid/non-self-hosted fleet servers.
  - Executes shell module commands to parse all login shells from `/etc/passwd`.
  - Audits `.ssh/authorized_keys` for every login user.
  - Matches keys against legitimate keys in `SSH Key` and server public keys (`root_public_key`, `frappe_public_key`).
  - Classifies mismatches: if key belongs to a system manager user (`User SSH Key`), it marks a "known violation"; otherwise, it raises a security compliance failure.
  - Inspects login users: any login shell user other than `frappe` and `root` triggers a suspicious user violation.

### SSH Access Audit Host & Violation
- **Role**: Child tables storing audited server status (`SSH Access Audit Host`) and details of non-compliant public keys or suspicious login shells (`SSH Access Audit Violation`).

### ARM Build Record & ARM Docker Image
- **Role**: Manages and registers multi-arch ARM docker builds and image pushes to registry servers.

### Virtual Machine Migration bind mount, mount, step, and volume
- **Role**: Child tables representing configurations (bind mounts, volume IDs, target paths) and track individual task execution state during VM migrations and disk resizes.
