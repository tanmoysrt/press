# Press Core: Billing & Payments Research

This document covers invoicing pipelines, balance transactions, currency conversions, payment gateways, webhooks, publisher payouts, and resource usage calculations.

## Core DocTypes

### [Invoice](press/press/doctype/invoice/invoice.py)
- **Role**: High-level billing document generated monthly or ad-hoc for each team.
- **Key Relationships**: Links to `Team` (the customer), `Site` (site-specific charges), and Stripe/Razorpay accounts.
- **Core Responsibilities**:
  - Compiles itemized charges (`invoice_item`) based on database and file storage consumption, site plan hours, and server usage.
  - Automatically calculates discounts (`invoice_discount`), applicable local taxes, and payment gateway fees (`invoice_transaction_fee`).
  - Coordinates invoice state transitions: `Draft`, `Unpaid`, `Paid`, `Refunded`, `Partially Paid`, or `Cancelled`.
  - Implements **[Invoice Credit Allocation](press/press/doctype/invoice_credit_allocation/invoice_credit_allocation.py)**: automatically draws down from the team's free or promotional credit balances before charging credit cards.

### [Balance Transaction](press/press/doctype/balance_transaction/balance_transaction.py)
- **Role**: The foundational financial ledger. Tracks every debit, credit, refund, chargeback, or promotional bonus against a team.
- **Mechanics**:
  - Distinguishes between Paid Credits (real money deposited by the user) and Free Credits (referral rewards, promotional credits, trial credits).
  - Enforces strict database transaction locks to prevent double-spending or concurrency bugs during checkout.
  - Implements **[Balance Transaction Allocation](press/press/doctype/balance_transaction_allocation/balance_transaction_allocation.py)**: tracks exactly which deposit/credit is consumed by which invoice for clear audit trails.

### [Usage Record](press/press/doctype/usage_record/usage_record.py)
- **Role**: Central hourly/daily resource meter.
- **Workflow**:
  - Scheduled background cron tasks scan all active sites and servers to record hourly operational states.
  - Aggregates data: site hours, database size (MB), backup storage volume (GB), custom domain usage, and server CPU/RAM sizes.
  - Generates billing usage lines that feed directly into the month-end billing invoice generator.

### Payment Gateways & Webhooks
- **[Payment Gateway](press/press/doctype/payment_gateway/payment_gateway.py)**: Configures credentials, API keys, and endpoint configurations for Stripe, Razorpay, or MPesa integrations.
- **Stripe Suite**:
  - `stripe_payment_method`: Stores secure, tokenized customer card representations (never raw PANs).
  - `stripe_payment_event`: Logs all transaction webhook calls to match card charges to invoices.
  - `stripe_webhook_log`: Debugging logs for raw incoming JSON payloads from Stripe.
- **Razorpay Suite** (`razorpay_mandate`, `razorpay_payment_record`, `razorpay_webhook_log`): Handles India-specific auto-recurring subscription mandates and captures UPI/Netbanking payments.
- **MPesa Suite** (`mpesa_setup`, `mpesa_payment_record`, `mpesa_request_log`): Handles mobile money processing (e.g. Kenya regions).

### Payouts & Marketplace Share
- **[Partner Payment Payout](press/press/doctype/partner_payment_payout/partner_payment_payout.py)** & **[Partner Payment Payout Item](press/press/doctype/partner_payment_payout_item/partner_payment_payout_item.py)**: Orchestrates monthly payout calculations to third-party publishers.
- **Workflow**:
  - Sums up subscription payments collected for a publisher's app, subtracts Frappe's marketplace commission share, and compiles the net payout due.
- **[Payout Order](press/press/doctype/payout_order/payout_order.py)** & **[Payout Order Item](press/press/doctype/payout_order_item/payout_order_item.py)**: Prepares net batch payouts for bank transfer execution.

### Extensions & Discounts
- **[Payment Due Extension](press/press/doctype/payment_due_extension/payment_due_extension.py)**: Extends due dates for invoices to allow customers time to resolve billing disputes without site suspension.
- **[Payment Dispute](press/press/doctype/payment_dispute/payment_dispute.py)**: Audits contested chargebacks or incorrect bill reports.
- **[Payment Partner Transaction](press/press/doctype/payment_partner_transaction/payment_partner_transaction.py)**: Records revenue-share transactions between Frappe and reseller/partner teams.

### Subscriptions & Plans

#### [Subscription](press/press/doctype/subscription/subscription.py)
- **Role**: Tracks active billing subscription for any billable resource (site, server, marketplace app).
- **Key Fields**: `team`, `plan`, `document_type`, `document_name`, `enabled`, `interval` (Hourly/Daily/Monthly).
- **Key Methods**: `create_usage_record()` — generates `Usage Record` on schedule; `enable()` / `disable()` — controls billing state; `is_valid_subscription()`, `can_charge_for_subscription()`.

#### [Site Plan](press/press/doctype/site_plan/site_plan.py)
- **Role**: Defines site hosting tier with resource limits and pricing.
- **Key Fields**: `plan_title`, `cpu_time_per_day`, `max_database_usage`, `max_storage_usage`, `price_inr`, `price_usd`, `vcpu`, `memory`, `disk`, `offsite_backups`.
- **Child Tables**: `site_plan_allowed_app` — restricts which marketplace apps can be installed on this plan. `site_plan_release_group` — maps this plan to specific release groups.

#### [Server Plan](press/press/doctype/server_plan/server_plan.py)
- **Role**: Defines server infrastructure tier for billing.
- **Key Fields**: `title`, `server_type`, `platform` (x86_64/arm64), `vcpu`, `memory`, `disk`, `price_inr`, `price_usd`, `machine_unavailable`.
- **Key Methods**: `sync_machine_availability_status_of_plans()` — polls cloud provider to mark plans unavailable when instance types are out of stock.
- **Related**: `server_storage_plan`, `server_snapshot_plan` — separate plans for extra attached storage and snapshot retention billing.

#### [Plan Change](press/press/doctype/plan_change/plan_change.py)
- **Role**: Audit log for every plan upgrade or downgrade on a site/server.
- **Key Fields**: `document_type`, `document_name`, `from_plan`, `to_plan`, `type` (Initial/Upgrade/Downgrade).
- **Key Methods**: `after_insert()` — creates or switches the linked `Subscription`; `change_subscription_plan()`.

#### [Plan Feature](press/press/doctype/plan_feature/plan_feature.py)
- **Role**: Child table listing human-readable feature bullets for a plan (e.g. "Daily Backups", "Custom Domain") used in the pricing page UI.

#### [Site Plan Change](press/press/doctype/site_plan_change/site_plan_change.py)
- **Role**: Site-specific plan change record. Extends `Plan Change` with site context and triggers prorated billing adjustments.

### Currency & Cost Management

- **[Currency Exchange](press/press/doctype/currency_exchange/currency_exchange.py)**: Stores USD/INR exchange rates used for billing calculations. Updated periodically.
- **[AWS Savings Plan Recommendation](press/press/doctype/aws_savings_plan_recommendation/aws_savings_plan_recommendation.py)**: Records AWS Compute Savings Plan recommendations fetched from AWS Cost Explorer — used by ops to optimize reserved instance spend.
