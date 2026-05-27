# Press Codebase — Architecture Overview

High-level map of all subsystems and their research files.

> **Maintenance Note**: Research files are living documentation. When you modify a doctype — adding fields, changing workflows, refactoring logic — update the corresponding file in this folder. Stale docs are worse than no docs.

---

## Subsystem Map

1. **Identity & Access** — teams, members, account requests, SSH CAs, 2FA, support access → [`teams.md`](teams.md), [`security.md`](security.md)
2. **Async Orchestration** — stateful workflow engine, exception pickling, exponential backoff → [`../../../../workflow_engine/doctype/research.md`](../../../../workflow_engine/doctype/research.md)
3. **App & Release Pipeline** — app repos, sources, versioned releases, approval gates, yanked releases → [`apps.md`](apps.md)
4. **Bench & Deploy** — bench provisioning, deploy candidates, Docker builds, release groups → [`bench.md`](bench.md)
5. **Site Lifecycle** — provisioning, domains, SSL, backups, migrations, analytics, version upgrades → [`sites.md`](sites.md)
6. **Server Fleet** — app/DB/proxy/monitor/self-hosted server types, plans, snapshots → [`servers.md`](servers.md)
7. **Cloud Infrastructure** — clusters, VMs, cloud providers, auto-scaling, backup buckets → [`cluster.md`](cluster.md)
8. **Agent Communication** — agent jobs, updates, callbacks, job types → [`jobs.md`](jobs.md)
9. **Incidents & Alerts** — alertmanager webhooks, silenced alerts, incident triage, remediation → [`alerts.md`](alerts.md), [`../../../../incident_management/doctype/research.md`](../../../../incident_management/doctype/research.md)
10. **Security & Network** — TLS certs, SSH certificates/keys, WireGuard VPN, 2FA, blocked domains → [`security.md`](security.md)
11. **Ops & Monitoring** — Ansible, audit logs, security updates, Telegram alerts, build metrics → [`ops.md`](ops.md)
12. **Billing** — usage records, invoices, Stripe, balance transactions, subscriptions → [`billing.md`](billing.md)
13. **SaaS** — standby pools, trials, remote login, site access tokens → [`../../../../saas/doctype/research.md`](../../../../saas/doctype/research.md)
14. **Marketplace** — app audits, publisher profiles, plans, subscriptions, reviews → [`../../../../marketplace/doctype/research.md`](../../../../marketplace/doctype/research.md)
15. **Partner Network** — approvals, certifications, leads, territories → [`../../../../partner/doctype/research.md`](../../../../partner/doctype/research.md)
16. **Infrastructure Ops** — VM migrations, disk resize, SSH fleet audit, ARM builds → [`../../../../infrastructure/doctype/research.md`](../../../../infrastructure/doctype/research.md)
17. **Dashboard & UI** — notification banners, add-ons, common site config, cookie preferences → [`dashboard.md`](dashboard.md)
18. **Experimental** — referral bonus → [`../../../../experimental/doctype/research.md`](../../../../experimental/doctype/research.md)

---

## Files in This Folder

| File | Doctypes Covered |
|------|-----------------|
| [`apps.md`](apps.md) | App, AppSource, AppRelease, AppPatch, AppTag, AppGroup, YankedAppRelease, AppRename |
| [`bench.md`](bench.md) | Bench, Deploy, DeployCandidate (+ children), ReleaseGroup (+ children), ReleasePipeline, FrappeVersion, SiteUpdate, BenchUpdate |
| [`billing.md`](billing.md) | Invoice, Subscription, UsageRecord, BalanceTransaction, SitePlan, ServerPlan, PlanChange, Stripe*, Razorpay*, MPesa* |
| [`cluster.md`](cluster.md) | Cluster, VirtualMachine, CloudProvider, RootDomain, AutoScaleRecord, BackupBucket, Region, DiskPerformance |
| [`alerts.md`](alerts.md) | Incident, AlertmanagerWebhookLog, SilencedAlert, PrometheusAlertRule, PressWebhook, GithubWebhookLog |
| [`jobs.md`](jobs.md) | AgentJob, AgentJobType, AgentUpdate, PressJob, PressJobType |
| [`ops.md`](ops.md) | AuditLog, AnsiblePlay, SecurityUpdate, TelegramGroup, BuildMetric, SerialConsoleLog |
| [`security.md`](security.md) | TLSCertificate, SSHCertificate, WireguardPeer, User2FA, SupportAccess, BlockedDomain, CodeServer |
| [`servers.md`](servers.md) | Server, DatabaseServer, ProxyServer, MonitorServer, AnalyticsServer, SelfHostedServer, MariaDBStalk, MariaDBUpgrade, PhysicalBackupGroup, ProxyFailover, NATFailover, OnPremFailover, RegistryServer |
| [`sites.md`](sites.md) | Site, SiteDomain, SiteBackup, SiteMigration, VersionUpgrade, SiteReplication, SiteGroupDeploy, StorageIntegration*, RemoteFile |
| [`teams.md`](teams.md) | Team, TeamMember, AccountRequest, PressRole, PressNotification, DripEmail, ERPNextConsultant, OAuthDomainMapping |
| [`dashboard.md`](dashboard.md) | DashboardBanner, AddOnSettings, CommonSiteConfig, CookiePreferenceLog |

## Deep-Dive How-To Guides

| File | Topic |
|------|-------|
| [`virtual_machine.md`](virtual_machine.md) | VirtualMachine deep dive — all fields, methods, multi-cloud implementations, image/snapshot lifecycle |
| [`ansible.md`](ansible.md) | How to write Ansible playbooks, invoke from Python, variable passing, output capture |
| [`agent_jobs.md`](agent_jobs.md) | Agent job architecture, @job/@step decorators, callback flow, how to add a new job type |
| [`press_jobs.md`](press_jobs.md) | PressJob architecture, @flow/@task decorators, KV store, hooks, how to write a new job |
| [`ui.md`](ui.md) | Frontend patterns — object.js, document/list resources, whitelisted methods, Frappe UI components |

## Other Module Research Files

| File | Module | Doctypes Covered |
|------|--------|-----------------|
| [`../../../../workflow_engine/doctype/research.md`](../../../../workflow_engine/doctype/research.md) | workflow_engine | PressWorkflow, PressWorkflowTask, PressWorkflowKV |
| [`../../../../saas/doctype/research.md`](../../../../saas/doctype/research.md) | saas | ProductTrial, SaasApp, SaasRemoteLogin, SiteAccessToken |
| [`../../../../incident_management/doctype/research.md`](../../../../incident_management/doctype/research.md) | incident_management | IncidentInvestigator, IncidentPattern, ActionStep |
| [`../../../../infrastructure/doctype/research.md`](../../../../infrastructure/doctype/research.md) | infrastructure | VirtualDiskResize, VirtualMachineMigration, SSHAccessAudit |
| [`../../../../marketplace/doctype/research.md`](../../../../marketplace/doctype/research.md) | marketplace | MarketplaceAppAudit, MarketplaceAppPlan, AppUserReview |
| [`../../../../partner/doctype/research.md`](../../../../partner/doctype/research.md) | partner | PartnerApprovalRequest, PartnerCertificate, PartnerLead |
| [`../../../../experimental/doctype/research.md`](../../../../experimental/doctype/research.md) | experimental | ReferralBonus |
