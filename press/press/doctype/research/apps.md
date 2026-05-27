# Press Core: Apps & Sources Research

This document covers app metadata management, repository source tracking, release versioning, app grouping, and patch mechanisms in the Press engine.

## Core DocTypes

### [App](press/press/doctype/app/app.py)
- **Role**: Canonical definition of a Frappe application registered in Press.
- **Key Fields**: `name`, `title`, `repo`, `team`, `enabled`, `frappe` (boolean — auto-set if name == "frappe").
- **Key Methods**:
  - `add_source()` — create or reuse `App Source` records for given branch/version combos.
  - `before_save()` — auto-flags apps named `frappe` as the core framework.
- **Module Functions**: `poll_new_releases()` — periodic scheduler task that queries GitHub for new commits across all enabled app sources and creates `App Release` records automatically.

### [App Source](press/press/doctype/app_source/app_source.py)
- **Role**: Maps an `App` to a specific GitHub repository URL, branch, and supported Frappe versions.
- **Key Fields**: `app`, `repository_url`, `branch`, `enabled`, `versions` (child table of `App Source Version`), `required_apps`, `github_installation_id`.
- **Key Methods**:
  - `create_release()` — fetches latest commit SHA from GitHub and creates a new `App Release` document.
  - `validate_dependent_apps()` — parses the app's `hooks.py` to auto-populate `required_apps`.
  - `get_commit_info()` — polls GitHub API for commit metadata (author, timestamp, message).
  - `get_auth_headers()` / `get_repo_url()` — handles GitHub App installation auth token injection.

### [App Release](press/press/doctype/app_release/app_release.py)
- **Role**: A versioned snapshot of an app tied to a specific git commit hash.
- **Key Fields**: `app`, `source`, `hash`, `status` (Draft / Approved / Awaiting Approval / Rejected / Yanked), `team`, `public`.
- **Key Methods**:
  - `_clone()` — fetches the repo code into a local `clone_directory` for audit/build use.
  - `auto_deploy()` — triggers deployment on benches that have `enable_auto_deploy` set.
  - `create_marketplace_app_audit()` — kicks off a `Marketplace App Audit` on new marketplace releases.
  - `validate_repo()` — checks Python/TOML syntax validity of the committed code.
  - `get_changed_files_between_hashes()` — git diff between two release hashes for changelog generation.

### [App Release Approval Request](press/press/doctype/app_release_approval_request/app_release_approval_request.py)
- **Role**: Formal audit log where system reviewers approve or reject custom/third-party app versions before they are cleared for bench deployment.
- **Workflow**: Created when a new release needs manual vetting. Reviewer marks `approved` or provides rejection reason. Approved releases unblock deployment queues.

### [Yanked App Release](press/press/doctype/yanked_app_release/yanked_app_release.py)
- **Role**: Immutable blacklist record that immediately marks a specific commit/release as invalid.
- **Trigger**: Created by `Marketplace App Audit` when a critical security vulnerability, backdoor, or breaking regression is detected.
- **Effect**: All deploy pipelines check this table before deploying — matching releases are hard-blocked.

### [App Release Difference](press/press/doctype/app_release_difference/app_release_difference.py)
- **Role**: Stores the diff between two consecutive releases — schema changes, migration files, and code file changes.
- **Use**: Deploy Candidate uses this to decide whether DB migrations must run or whether a soft restart suffices.

### [App Group](press/press/doctype/app_group/app_group.py)
- **Role**: Logical grouping of apps for shared deployment, permissions, or marketplace categorization.

### [App Tag](press/press/doctype/app_tag/app_tag.py)
- **Role**: Free-form taxonomy tags attached to apps for filtering and discovery in the marketplace.

### [App Patch](press/press/doctype/app_patch/app_patch.py)
- **Role**: Manages temporary code patches applied on top of a release without a full git commit — used for emergency hotfixes on production benches.

### [App Rename](press/press/doctype/app_rename/app_rename.py)
- **Role**: Tracks and executes renaming of an app identifier across the system (DocType links, bench config, proxy entries) when an app is renamed.

### [App Source Version](press/press/doctype/app_source_version/app_source_version.py)
- **Role**: Child table on `App Source` mapping a source to the specific Frappe framework versions it supports.

### [Required Apps](press/press/doctype/required_apps/required_apps.py)
- **Role**: Child table on `App Source` listing apps that must be present in a bench before this app can be installed (dependency declaration).
