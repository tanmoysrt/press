# Press Core: Dashboard, Add-Ons & UI Config Research

This document covers dashboard notification banners, add-on services, common site config management, and user preference logging in Press.

## Core DocTypes

### Dashboard Banners

#### [Dashboard Banner](press/press/doctype/dashboard_banner/dashboard_banner.py)
- **Role**: Configures notification banners displayed to teams on the Frappe Cloud dashboard.
- **Key Fields**: `title`, `message`, `type` (Info / Success / Error / Warning), `enabled`, `is_global` (show to all teams), `is_dismissible`, `is_scheduled`, `scheduled_start_time`, `scheduled_end_time`, `action_label`, `action_script`.
- **Scoping**: A banner can be targeted globally or scoped to specific teams, sites, servers, or clusters via linked child tables.
- **Use Cases**: Planned maintenance notices, incident announcements, billing reminders, feature announcements.

#### Scoping Child Tables
- **[Dashboard Banner Team](press/press/doctype/dashboard_banner_team/dashboard_banner_team.py)**: Limits banner visibility to a specific list of teams.
- **[Dashboard Banner Site](press/press/doctype/dashboard_banner_site/dashboard_banner_site.py)**: Targets banner to users who own/manage specific sites.
- **[Dashboard Banner Server](press/press/doctype/dashboard_banner_server/dashboard_banner_server.py)**: Shows banner only to teams on a specific server.
- **[Dashboard Banner Cluster](press/press/doctype/dashboard_banner_cluster/dashboard_banner_cluster.py)**: Targets banner at all teams hosted on a given cluster.
- **[Dashboard Banner Dismissal](press/press/doctype/dashboard_banner_dismissal/dashboard_banner_dismissal.py)**: Tracks which teams have dismissed a dismissible banner — prevents re-showing after dismissal.

### Add-On Services

#### [Add On Settings](press/press/doctype/add_on_settings/add_on_settings.py)
- **Role**: Single-document configuration for add-on features (extra storage, static IPs, code servers) — enables/disables add-on availability and sets global pricing defaults.

#### [Add On Storage Log](press/press/doctype/add_on_storage_log/add_on_storage_log.py)
- **Role**: Audit log for extra storage add-on provisioning and de-provisioning events. Tracks the site, team, storage size delta, and timestamp for billing reconciliation.

### Common Site Config

#### [Common Site Config](press/press/doctype/common_site_config/common_site_config.py)
- **Role**: Global `common_site_config.json` key-value store applied cluster-wide or server-wide to all benches. Settings here propagate to every bench on the target server, overriding defaults set at the bench level.
- **Use Cases**: Configuring Redis URLs, APM settings, feature flags, and third-party API keys that apply uniformly across a fleet.

### User Preferences

#### [Cookie Preference Log](press/press/doctype/cookie_preference_log/cookie_preference_log.py)
- **Role**: Logs per-user cookie consent choices (analytics, marketing, functional cookies) from the Frappe Cloud dashboard consent banner. Stored for GDPR/legal compliance audit.
