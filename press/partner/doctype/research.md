# Partner DocType Group Research

This module manages the Frappe Partner network: partner approvals, certified developer link requests, leads, tiers, territory management, audits, and non-conformance items.

## DocType Reference & Role

### [Partner Approval Request](press/press/partner/doctype/partner_approval_request/partner_approval_request.py)
- **Role**: Coordinates the partnership link between a customer team (`requested_by`) and a certified partner team (`partner`).
- **Workflow**:
  - Generates a unique 15-character hash `key` upon insertion.
  - Requires dual approvals: `approved_by_partner` and `approved_by_frappe`.
  - When the partner triggers `approve_partner_request` (whitelisted), it sets `approved_by_partner = True` and queries the Frappe success manager email using billing connector API client, then sends an email request via the `partner_approval` template.
  - Once both parties approve, status becomes `Approved` and updates the customer team's partnership date and `partner_email` with the partner's credentials.

### [Certificate Link Request](press/press/partner/doctype/certificate_link_request/certificate_link_request.py)
- **Role**: Links an individual developer's professional certification to a partner team.
- **Workflow**:
  - Upon insertion, emails a confirmation URL to the certified developer (`user_email`) containing a unique hash token.
  - When the developer approves the request, status becomes `Approved`, which triggers the post-save hook to find the matching `Partner Certificate` for that developer and course, and updates its owner partnership affiliation (`partner_team`).

### Certified Assets & Compliance
- **[Partner Certificate](press/press/partner/doctype/partner_certificate/partner_certificate.py)** & **[Partner Certificate Request](press/press/partner/doctype/partner_certificate_request/partner_certificate_request.py)**: Tracks course certs, exam passing data, validity ranges, and certificate generation requests.
- **[Partner Audit](press/press/partner/doctype/partner_audit/partner_audit.py)** & **[Partner Non Conformance](press/press/partner/doctype/partner_non_conformance/partner_non_conformance.py)**: Manages audit logs of partner performance and tracks non-compliance violations or remediation activities.
- **[Partner Consent](press/press/partner/doctype/partner_consent/partner_consent.py)**: Tracks signed legal consents and partnership terms.

### Lead & Pipeline Management
- **[Partner Lead](press/press/partner/doctype/partner_lead/partner_lead.py)**: Captures prospective customer inquiries assigned or routed to partners.
- **[Lead Followup](press/press/partner/doctype/lead_followup/lead_followup.py)**: Logs structured follow-up calls, emails, and reminders against leads.
- **Partner Lead Origin & Lead Type**: Configures categorization tags for partner lead acquisition pipelines.

### Framework & Territorials
- **[Partner Tier](press/press/partner/doctype/partner_tier/partner_tier.py)**: Defines levels (e.g. Bronze, Silver, Gold, Platinum) with resource limits, discount percentages, and minimum requirements.
- **[Territory](press/press/partner/doctype/territory/territory.py)**: Utilizes Frappe's hierarchical `NestedSet` database model to define nested sales/support geographic territories.
