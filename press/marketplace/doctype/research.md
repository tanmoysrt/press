# Marketplace DocType Group Research

This module manages the Frappe Cloud app marketplace features: publisher profiles, user reviews, promotion banners, plans, payments, subscriptions, and automated security/compliance app audits.

## DocType Reference & Role

### [Marketplace App Audit](press/press/marketplace/doctype/marketplace_app_audit/marketplace_app_audit.py)
- **Role**: Automatically clones, reviews, and runs compliance/security gates on new marketplace app submissions and releases.
- **Audit Pipeline**:
  - Automatically enqueued on new app release submissions (`App Release`).
  - Clones the git repo to a temporary directory.
  - Runs six modular check suites:
    1. **Metadata Checks**: Verifies description, publisher details, categories, logo files, and support/documentation URLs.
    2. **Versioning Checks**: Ensures semantic versioning syntax and that the version is bumped compared to the last active release.
    3. **Dependency Checks**: Validates that all required/optional dependency apps are valid and registered.
    4. **Code Quality Checks**: Inspects python syntax and general syntax compliance.
    5. **Compatibility Checks**: Ensures the app is compatible with core Frappe/ERPNext framework versions.
    6. **Semgrep Rules**: Scans python/JS code using custom security rulesets to flag dangerous patterns (unsafe SQL execution, raw terminal execution, insecure private key usage, etc.).
- **Triage & Remediation Actions**:
  - tallies checks by severity: `Critical` (any fail causes fail status), `Major` (fail/warn results in overall warn/fail), `Minor` (needs improvement), and `Info`.
  - If the audit fails (`Fail`) and automated actions are enabled in `Marketplace Settings`:
    - Auto-rejects all open `App Release Approval Request` logs with a detailed rejection reason.
    - If hard blocking failures are found, it inserts a `Yanked App Release` record to prevent deployments and sets the app's health status to `Attention Required`.
  - Whitelists a method `send_report_to_publisher` to email a structured HTML/CSS report of non-internal failing checks to the publisher's email address.

### [Marketplace Publisher Profile](press/press/marketplace/doctype/marketplace_publisher_profile/marketplace_publisher_profile.py)
- **Role**: Details developer profile info: organization name, developer credentials, and linked team.

### Marketplace Plans & Subscriptions
- **[Marketplace App Plan](press/press/marketplace/doctype/marketplace_app_plan/marketplace_app_plan.py)**: Defines pricing (USD/INR), billing intervals, free trials, and feature limits of paid marketplace apps.
- **[Marketplace App Subscription](press/press/marketplace/doctype/marketplace_app_subscription/marketplace_app_subscription.py)**: Tracks active, trialing, paused, or cancelled team subscriptions to marketplace apps.
- **[Marketplace App Payment](press/press/marketplace/doctype/marketplace_app_payment/marketplace_app_payment.py)**: Logs purchases, payouts, and revenue share for paid apps.

### Reviews & Banners
- **[App User Review](press/press/marketplace/doctype/app_user_review/app_user_review.py)** & **[Developer Review Reply](press/press/marketplace/doctype/developer_review_reply/developer_review_reply.py)**: Manages customer reviews (star rating, title, text) and developer replies.
- **[Featured App](press/press/marketplace/doctype/featured_app/featured_app.py)** & **[Marketplace Promotional Banner](press/press/marketplace/doctype/marketplace_promotional_banner/marketplace_promotional_banner.py)**: Manages promotion banners and showcase slots.

### Settings & Addons
- **[Marketplace Settings](press/press/marketplace/doctype/marketplace_settings/marketplace_settings.py)**: Core configurations: auto-approve releases, enable/disable automated audits, configure alert recipients, and email review alerts.
- **[Marketplace Add On](press/press/marketplace/doctype/marketplace_add_on/marketplace_add_on.py)**: Manages supplementary app additions.
