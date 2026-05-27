# Press Core: Sites & Domains Research

This document covers the core architecture of Site provisioning, DNS/domain mapping, backup orchestration, analytics, and migration lifecycles in the Press engine.

## Core DocTypes

### [Site](press/press/doctype/site/site.py)
- **Role**: The central document representing a deployed customer Frappe site instance.
- **Key Relationships**: Links to `Bench` (the runtime environment), `Server` (the physical/virtual host), `Team` (the owner), and `Site Plan` (billing/limits).
- **Core Responsibilities**:
  - Validates subdomains against a globally blacklisted set of terms to prevent system spoofing.
  - Implements `generate_saas_communication_secret` to generate unique access tokens allowing secure API and RPC communication between Frappe Cloud (Press) and the agent daemon running on the host bench.
  - Controls site lifecycle hooks: `provision` (creates site on bench), `suspend` (blocks web traffic and disables scheduler), `resume`, and `archive` (safely drops the database and deletes public/private files).

### [Site Domain](press/press/doctype/site_domain/site_domain.py)
- **Role**: Manages custom domain pointing (CNAME/A records) for sites.
- **Logic**:
  - Automatically queries DNS server records to verify CNAME/A record pointing to the public router/proxy IP before initiating domain routing.
  - Integrates with Let's Encrypt / ACME protocols via Nginx/Proxy servers to provision and auto-renew SSL/TLS certificates.
  - Manages routing tables inside Nginx configurations by triggering Caddy/Nginx config rebuild jobs on the proxy fleet.

### [Site Backup](press/press/doctype/site_backup/site_backup.py)
- **Role**: Orchestrates backup generation and offsite storage.
- **Workflow**:
  - Background scheduler pushes backup commands via `Agent Job` to the host bench.
  - Bench executes `bench --site [site] backup --with-files` to package:
    1. SQL database dump (`database.sql.gz`)
    2. Public files directory (`public_files.tar.gz`)
    3. Private files directory (`private_files.tar.gz`)
  - Once completed, the backup daemon uploads files directly to an offsite S3-compatible storage bucket (`backup_bucket` linked to AWS S3, Cloudflare R2, or Backblaze).
  - Stores unique presigned download URLs with expiry times.
- **[Site Backup Time](press/press/doctype/site_backup_time/site_backup_time.py)**: Manages customizable backup cron schedules (daily, weekly, or hourly intervals) per site.

### [Site Migration](press/press/doctype/site_migration/site_migration.py)
- **Role**: Coordinates high-resilience migrations of active sites between different Benches or physical Servers.
- **Steps**:
  1. **Source Freeze**: Puts source site into maintenance mode (blocks writes).
  2. **Backup Generation**: Runs a complete database and files backup.
  3. **Target Setup**: Prepares database credentials and schema on the target server.
  4. **Data Sync**: Restores the database dump and copies the public/private files to the target bench directory.
  5. **DNS Swap**: Updates DNS/Proxy routing tables to point the domain/subdomain to the new server IP.
  6. **Cleanup**: Archiving the source site files post-migration verification.
- **[Site Migration Step](press/press/doctype/site_migration_step/site_migration_step.py)**: Child table tracking step execution success, traceback logs, and timing metrics.

### [Site Action](press/press/doctype/site_action/site_action.py)
- **Role**: Handles dynamic, user-triggered operations on a site: password reset, clear cache, rebuild config, update site configuration keys, and database console shell access.
- **[Site Action Step](press/press/doctype/site_action_step/site_action_step.py)**: Tracks execution of these tasks.

### Configurations & Credentials
- **[Site Config](press/press/doctype/site_config/site_config.py)** & **[Site Config Key](press/press/doctype/site_config_key/site_config_key.py)**: Manages site `common_site_config.json` parameter overrides.
- **[Site Config Key Blacklist](press/press/doctype/site_config_key_blacklist/site_config_key_blacklist.py)**: Prevents users from overriding sensitive internal parameters (like database credentials, encryption keys, or internal webhook secrets).
- **[Site Database User](press/press/doctype/site_database_user/site_database_user.py)** & **[Site Database Table Permission](press/press/doctype/site_database_table_permission/site_database_table_permission.py)**: Manages SQL playground read-only or read-write developer access credentials and enforces security restrictions.

### Analytics & Metrics
- **[Site Usage](press/press/doctype/site_usage/site_usage.py)**: Aggregates system metrics (database size, public/private file storage size, request count, bandwidth consumption) used for billing calculations.
- **Site Analytics Suite** (`site_analytics`, `site_analytics_active`, `site_analytics_app`, `site_analytics_doctype`, `site_analytics_login`, `site_analytics_user`): Tracks visitor statistics, popular doctypes accessed, and login histories for customer telemetry.

### Version Upgrades

### [Version Upgrade](press/press/doctype/version_upgrade/version_upgrade.py)
- **Role**: Schedules and executes Frappe framework version upgrades for a site (e.g. v14 → v15).
- **Key Fields**: `site`, `source_group`, `destination_group`, `status` (Scheduled / Pending / Running / Success / Failure / Cancelled), `scheduled_time`, `skip_backups`, `skip_failing_patches`, `deploy_private_bench`, `bench_deploy_successful`, `site_update`.
- **Key Methods**:
  - `validate()` — checks for duplicate in-progress upgrades, validates the version gap is exactly one major version, verifies all installed apps support the target version.
  - `start()` — calls `move_to_group()` to migrate the site to the destination release group.
  - `run_scheduled_upgrades()` (static) — picks up all scheduled upgrades past their `scheduled_time` and starts them.
  - `send_version_upgrade_failure_email()` — notifies site owner on failure with traceback.

### Site Replication

### [Site Replication](press/press/doctype/site_replication/site_replication.py)
- **Role**: Clones an existing site to a new subdomain, optionally on a different server/bench.
- **Key Fields**: `site`, `subdomain`, `new_site`, `server`, `bench`, `release_group`, `status` (Not Started / Running / Success / Failure).
- **Key Methods**:
  - `validate_duplicate()` — prevents duplicate replication jobs for the same source site.
  - `validate_site_name()` — checks subdomain availability and blacklist compliance.
  - `after_insert()` — triggers the replication workflow (backup source → restore to target bench under new subdomain).
  - `get_all_running_site_replications()` — limits concurrent replications to prevent server overload.

### Site Group Deploy
- **[Site Group Deploy](press/press/doctype/site_group_deploy/site_group_deploy.py)**: Orchestrates provisioning of a release group + site together as a single operation (used for new trial/SaaS site creation flows).
- **Key Fields**: `team`, `subdomain`, `version`, `release_group`, `bench`, `site`, `cluster`, `auto_provision_bench`, `status`.
- **Key Methods**: `create_release_group()`, `create_site()`, `check_if_team_can_create_site()`, `set_latest_version()`.
- **[Site Group Deploy App](press/press/doctype/site_group_deploy_app/site_group_deploy_app.py)**: Child table listing apps to include in the group deploy.

### Partner Leads & Storage

- **[Site Partner Lead](press/press/doctype/site_partner_lead/site_partner_lead.py)**: Sales lead record linked to a site — captures contact details (`first_name`, `last_name`, `email`, `company`, `domain`, `country`, `users`) of prospects who signed up via a partner's referral. Linked to `frappe_lead` CRM record.

- **[Storage Integration Bucket](press/press/doctype/storage_integration_bucket/storage_integration_bucket.py)**: Configures a MinIO-compatible bucket for site file storage integration (alternative to default S3). Fields: `bucket_name`, `minio_host_ip`, `minio_server_on`, `region`.
- **[Storage Integration Subscription](press/press/doctype/storage_integration_subscription/storage_integration_subscription.py)**: Tracks active storage integration subscriptions per site — billing and provisioning lifecycle for attached MinIO storage.

### Remote Files

- **[Remote File](press/press/doctype/remote_file/remote_file.py)**: Tracks S3-compatible backup file objects for sites. Fields: `file_path`, `file_name`, `file_size`, `bucket`, `status` (Available/Unavailable), `url`, `site`. Methods: `exists()`, `delete_remote_object()`, `get_download_link()` (generates presigned URL), `get_content()`. Used by `Site Backup` to reference offsite stored backup archives.
