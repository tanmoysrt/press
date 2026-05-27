# SaaS DocType Group Research

This module manages the automated SaaS trial and subscription model, including instant site provisioning via pre-built standby pools, remote single-sign-on (SSO), and signup page generation.

## DocType Reference & Role

### [Product Trial](press/press/saas/doctype/product_trial/product_trial.py)
- **Role**: Coordinates the instant-provisioning standby pools and trial settings for SaaS apps.
- **Standby Pooling Architecture**:
  - If `enable_pooling = 1` is configured, a scheduled background job `replenish_standby_sites()` executes to keep a pool of pre-created sites (`is_standby = 1`) on active clusters.
  - When a user requests a trial, the system fetches a standby site using `get_preferred_site()`. It filters for active, standby sites and selects one **hosted on a server with no active Incidents** (confirmed, validating, or acknowledged).
  - **Claiming a Site**: Instantly marks `is_standby = 0`, updates the owner `team`, trial plan, signup timestamps, app subscription details, and configures the user's custom subdomain mapping (`set_site_domain()`). This bypasses the typical 5-10 minute wait time for fresh docker container provisioning.
  - If no standby site is available, it gracefully falls back to normal in-place site creation on the cluster.
  - Prefills suggested subdomains using corporate email domain structures (extracting domain name, ignoring generic providers like gmail/outlook).
  - Sends verification OTP codes using whitelisted mail delivery configurations.
  - Sends automated expired suspension warnings using `send_suspend_mail()`.

### [Product Trial Request](press/press/saas/doctype/product_trial_request/product_trial_request.py)
- **Role**: Logs trial registration requests containing signup fields, subdomain, target email, validation codes, and reference team metadata.

### [Saas Remote Login](press/press/saas/doctype/saas_remote_login/saas_remote_login.py)
- **Role**: Manages authenticated Single Sign-On (SSO) redirects from the Press dashboard directly into specific customer sites. Generates secure, short-lived tokens and coordinates auth protocols.

### SaaS Apps & Versioning
- **[Saas App](press/press/saas/doctype/saas_app/saas_app.py)**: Configures core SaaS catalog apps, specifying details like required dependencies, features, and target versions.
- **[Saas App Plan](press/press/saas/doctype/saas_app_plan/saas_app_plan.py)** & **[Saas App Subscription](press/press/saas/doctype/saas_app_subscription/saas_app_subscription.py)**: Configures tier-based recurring SaaS pricing schemas and tracks active/trialing/suspended SaaS customer subscriptions.
- **[Saas App Version](press/press/saas/doctype/saas_app_version/saas_app_version.py)**: Maps specific app versions to SaaS availability pipelines.

### Setup & Portals
- **[Saas Settings](press/press/saas/doctype/saas_settings/saas_settings.py)**: Centralizes SaaS pooling metrics, retry timeouts, limits, and administrator verification settings.
- **[Saas Signup Generator](press/press/saas/doctype/saas_signup_generator/saas_signup_generator.py)** & **[Saas Setup Account Generator](press/press/saas/doctype/saas_setup_account_generator/saas_setup_account_generator.py)**: Implements Frappe `WebsiteGenerator` controllers to serve dynamic, custom-branded landing pages for trial signups and setup wizards.
- **[Site Access Token](press/press/saas/doctype/site_access_token/site_access_token.py)**: Stores and refreshes secure, signed API keys to interact with customer sites.
