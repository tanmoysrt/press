# Press Core: Teams & Access Control Research

This document covers account/team structures, onboarding workflows, role permissions, method permissions, deletion safety checks, and support impersonation audit trails.

## Core DocTypes

### [Team](press/press/doctype/team/team.py)
- **Role**: The foundational multi-tenant ownership entity. Every site, server, billing record, and developer access key is owned by a specific Team.
- **Key Relationships**: Links to `Team Tier` (Bronze/Silver/Gold/Platinum), users, and active site plans.
- **Core Responsibilities**:
  - Encapsulates organizational details: company name, partner affiliation email, tax registration info, and active billing currency (USD/INR).
  - Tracks and enforces team-wide usage allocations (e.g. maximum sites, maximum servers, and maximum member seats).
  - Handles credit balance allocations and holds the subscription state of the account.

### Onboarding & Requests
- **[Account Request](press/press/doctype/account_request/account_request.py)**: Initiates account and team creation. Collects company name, email domain, phone, country, and requested system permissions.
- **[Account Request Press Role](press/press/doctype/account_request_press_role/account_request_press_role.py)**: Child table mapping requested internal operational roles during onboarding.
- **[Team Onboarding](press/press/doctype/team_onboarding/team_onboarding.py)**: Coordinates onboarding checklists (welcome emails, verification steps, setup guides).

### Members & Impersonation
- **[Team Member](press/press/doctype/team_member/team_member.py)** & **[Child Team Member](press/press/doctype/child_team_member/child_team_member.py)**: Connects standard system `User` records to `Team` organizations, mapping specific user roles (Owner, Developer, Billing, Viewer).
- **[Team Member Impersonation](press/press/doctype/team_member_impersonation/team_member_impersonation.py)**: Highly secure support log.
  - Generates audit trails whenever a Frappe Cloud support engineer impersonates a customer user for debugging purposes.
  - Implements automatic expiration timeouts for support tokens and logs all session activity.

### Roles & Permissions
- **[Press Role](press/press/doctype/press_role/press_role.py)**: Defines internal operational roles (e.g. Server Admin, Support Agent, Billing Manager, Developer Reviewer).
- **[Press Role Permission](press/press/doctype/press_role_permission/press_role_permission.py)** & **[Press Role Resource](press/press/doctype/press_role_resource/press_role_resource.py)**: Fine-grained resource-level access control list (ACL) mapping roles to specific servers, clusters, or sites.
- **[Press Method Permission](press/press/doctype/press_method_permission/press_method_permission.py)**: Restricts direct whitelisted API endpoint executions to specific internal user roles to prevent unauthorized system actions.

### Deletion Safety & Lifecycle
- **[Team Deletion Request](press/press/doctype/team_deletion_request/team_deletion_request.py)** & **[Team Member Deletion Request](press/press/doctype/team_member_deletion_request/team_member_deletion_request.py)**: Implements asynchronous deletion gates.
  - Prevents instant accidental deletion of customer data.
  - Verifies safety rules before purging: checks that all linked sites are archived, all outstanding invoices are paid, and no active servers are registered. Enforces a multi-day retention/grace period before permanent DB wipe.

### Settings & Configs
- **[Press Settings](press/press/doctype/press_settings/press_settings.py)**: Global single DocType controlling crucial configurations: free referral credit amounts, system domain keys, default cluster maps, and automated alert limits.

### Team Metadata

- **[Team Change](press/press/doctype/team_change/team_change.py)**: Audit record of ownership transfers — when a site or server is moved from one team to another.
- **[Team Tier](press/press/doctype/team_tier/team_tier.py)**: Defines tier levels (e.g. Free, Growth, Business, Enterprise) with limits on sites, servers, seats, and discount percentages.
- **[Team Member Resource](press/press/doctype/team_member_resource/team_member_resource.py)**: Child table tracking which specific resources (sites, servers, release groups) a team member has access to, enabling per-resource access control within a team.
- **[Communication Info](press/press/doctype/communication_info/communication_info.py)**: Stores communication preferences and contact metadata for a team (notification emails, escalation contacts, timezone).
- **[Press Role User](press/press/doctype/press_role_user/press_role_user.py)**: Child table on `Press Role` mapping which users hold a given internal role.

### Notifications & Feedback

- **[Press Notification](press/press/doctype/press_notification/press_notification.py)**: In-app notification for a team. Types: Site Update, Deploy, Recovery, Agent Failure, etc. Fields: `type`, `document_type`, `document_name`, `title`, `message`, `traceback`, `is_actionable`, `is_addressed`, `read`, `team`. Methods: `mark_as_addressed()`, `mark_as_read()`. Module function: `create_new_notification()`.
- **[Press Feedback](press/press/doctype/press_feedback/press_feedback.py)**: User-submitted feedback with `rating`, `message`, `note`, team context, and current `route`. Purely a data capture doctype.
- **[Press Tag](press/press/doctype/press_tag/press_tag.py)**: Simple tag attached to a doctype record for a team (`tag`, `doctype_name`, `team`). Enables custom labeling in the dashboard.

### Drip & Onboarding Emails

- **[Drip Email](press/press/doctype/drip_email/drip_email.py)**: Automated email campaign system for site onboarding and product trials. Fields: `email_type` (Drip/Sign Up/Subscription Activation/Whitepaper/Onboarding), `subject`, `sender`, `product_trial`, `send_after`, `send_after_payment`. Methods: `send()`, `send_drip_email()`, `evaluate_condition()`, `select_consultant()`, `send_to_sites()`. Supports conditional sends based on site age and payment status.
- **[Module Setup Guide](press/press/doctype/module_setup_guide/module_setup_guide.py)**: Configures step-by-step setup guides surfaced in the dashboard after trial signup — maps Frappe modules to tutorial steps.

### ERPNext Integration

- **[ERPNext App](press/press/doctype/erpnext_app/erpnext_app.py)**: Maps Frappe/ERPNext app identifiers to consultant skill tags for matchmaking in lead assignment.
- **[ERPNext Consultant](press/press/doctype/erpnext_consultant/erpnext_consultant.py)**: Consultant registry with round-robin territory allocation. Fields: `user`, `active`, `territories`. Methods: `get_one_for_country()` (round-robin by region), `list_for_region()`.
  - `erpnext_consultant_region` — child table of territories assigned to a consultant.
- **[ERPNext Site Settings](press/press/doctype/erpnext_site_settings/erpnext_site_settings.py)**: Per-site ERPNext configuration overrides — links a site to specific ERPNext module enablement flags.

### OAuth & Misc

- **[OAuth Domain Mapping](press/press/doctype/oauth_domain_mapping/oauth_domain_mapping.py)**: Maps external OAuth provider domains to internal team/user records for SSO login flows.
