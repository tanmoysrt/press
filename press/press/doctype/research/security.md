# Press Core: Network, Security & Access Research

This document covers TLS certificate management, SSH certificate authorities, WireGuard VPN, 2FA, support access workflows, and network security controls in Press.

## Core DocTypes

### TLS Certificates

#### [TLS Certificate](press/press/doctype/tls_certificate/tls_certificate.py)
- **Role**: Manages SSL/TLS certificates for hosted site domains and root domains.
- **Key Fields**: `domain`, `wildcard`, `provider` (Let's Encrypt / Other), `certificate`, `private_key`, `status`, `expires_on`.
- **Key Methods**:
  - `obtain_certificate()` — enqueues async Let's Encrypt ACME certificate request.
  - `_extract_certificate_details()` — parses X.509 cert to extract validity dates.
  - `validate_key_certificate_association()` — verifies private key matches certificate.
  - `trigger_server_tls_setup_callback()` — deploys cert to proxy/servers post-issuance.
- **Module Functions**: `renew_tls_certificates()` (scheduled renewal), `notify_custom_tls_renewal()`, `update_server_tls_certificate()`.

#### [Certificate Authority](press/press/doctype/certificate_authority/certificate_authority.py)
- **Role**: Internal CA for issuing TLS certificates to internal services and between cluster nodes (not ACME — used for inter-service mTLS).

### SSH Certificate System

#### [SSH Certificate Authority](press/press/doctype/ssh_certificate_authority/ssh_certificate_authority.py)
- **Role**: Root CA that signs short-lived SSH certificates for both users and host servers.
- **Design**: Replaces permanent `authorized_keys` with signed ephemeral certificates — compromised keys expire automatically (1h–30d TTL).

#### [SSH Certificate](press/press/doctype/ssh_certificate/ssh_certificate.py)
- **Role**: Represents a signed SSH certificate (user or host type) with a defined validity window.
- **Key Fields**: `ssh_public_key`, `certificate_type` (User / Host), `validity` (1h / 3h / 6h / 30d), `ssh_certificate_authority`.
- **Key Methods**:
  - `validate_public_key()` — parses SSH public key and computes key fingerprint.
  - `generate_certificate()` — calls the CA's sign method to produce a signed certificate.
  - `extract_certificate_details()` — parses validity timestamps from `ssh-keygen -L` output.

#### [SSH Key](press/press/doctype/ssh_key/ssh_key.py)
- **Role**: Stores raw SSH public keys for servers and system accounts (not user keys — those are in `User SSH Key`).

#### [User SSH Key](press/press/doctype/user_ssh_key/user_ssh_key.py)
- **Role**: Stores individual user-submitted SSH public keys. Used to issue `User SSH Certificate` records for time-limited server access.

#### [User SSH Certificate](press/press/doctype/user_ssh_certificate/user_ssh_certificate.py)
- **Role**: Links a `User SSH Key` to a signed `SSH Certificate` for a specific validity window. Tracks when access was granted and to which servers.

### WireGuard VPN

#### [Wireguard Peer](press/press/doctype/wireguard_peer/wireguard_peer.py)
- **Role**: Manages WireGuard VPN peer configurations connecting servers across clusters into a private mesh network.
- **Key Fields**: `peer_name`, `server_name`, `server_type`, `peer_ip`, `private_ip`, `peer_private_network`, `private_key`, `public_key`, `peer_config`, `wireguard_network`, `allowed_ips`, `upstream_proxy`, `status`.
- **Key Methods**:
  - `next_ip_address()` — auto-assigns the next available IP from the WireGuard subnet.
  - `setup_wireguard()` — runs Ansible to configure WireGuard on the peer server.
  - `ping_peer()` — tests connectivity to the peer via the VPN tunnel.
  - `generate_config()` / `download_config()` — produces `wg0.conf` for peer configuration.

### Two-Factor Authentication

#### [User 2FA](press/press/doctype/user_2fa/user_2fa.py)
- **Role**: Manages TOTP-based two-factor authentication for Press dashboard users.
- **Key Fields**: `user`, `enabled`, `totp_secret`, `recovery_codes` (child table), `last_verified_at`, `recovery_codes_last_viewed_at`.
- **Key Methods**:
  - `validate()` — auto-generates TOTP secret on first enable.
  - `generate_secret()` — creates a `pyotp` TOTP base32 secret.
  - `generate_recovery_codes()` — generates one-time use alphanumeric backup codes.
  - `yearly_2fa_recovery_code_reminder()` — scheduled job reminding users to view/refresh recovery codes annually.

#### [User 2FA Recovery Code](press/press/doctype/user_2fa_recovery_code/user_2fa_recovery_code.py)
- **Role**: Child table on `User 2FA` storing hashed one-time recovery codes used as fallback authentication when TOTP device is unavailable.

### Support Access

#### [Support Access](press/press/doctype/support_access/support_access.py)
- **Role**: Time-limited, approval-gated access request workflow allowing Frappe support engineers to access a customer's team resources.
- **Key Fields**: `requested_by`, `requested_team`, `target_team`, `status` (Pending / Accepted / Rejected / Forfeited / Revoked), `access_allowed_till`, `allowed_for` (3/6/12/24/72/168 hrs), `resources` (table), `bench_ssh`, `login_as_administrator`.
- **Key Methods**:
  - `before_validate()` — sets expiry timestamp based on `allowed_for` duration.
  - `validate_status_change()` — enforces legal state transitions (e.g. can't re-accept a revoked request).
  - `notify_on_request()` / `notify_on_status_change()` — emails customer on request and decision.
- **Design**: Immutable audit trail — all access windows and decisions are permanently logged.

#### [Support Access Resource](press/press/doctype/support_access_resource/support_access_resource.py)
- **Role**: Child table on `Support Access` listing specific resources (sites, benches, servers) covered by the access grant.

### Network Policies

#### [Blocked Domain](press/press/doctype/blocked_domain/blocked_domain.py)
- **Role**: Blacklist of subdomain names that cannot be used for site creation (reserved words, brand-sensitive terms, known abuse patterns). Validated during site provisioning.

#### [Static IP Plan](press/press/doctype/static_ip_plan/static_ip_plan.py)
- **Role**: Defines the pricing and allocation rules for assigning Elastic IP / static IP addresses to sites or servers as an add-on service.

### Remote Development

#### [Code Server](press/press/doctype/code_server/code_server.py)
- **Role**: Provisions a browser-based VS Code server (code-server) on a bench for remote development. Manages session creation, authentication, and cleanup after idle timeout.
