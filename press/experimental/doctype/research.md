# Experimental DocType Group Research

This module contains experimental features under development or trial in the Press system.

## DocType Overview

Currently, this group contains a single DocType:

### [Referral Bonus](press/press/experimental/doctype/referral_bonus/referral_bonus.py)

- **Purpose**: Manages and processes referral rewards when a newly referred team starts spending.
- **Key Fields**:
  - `for_team` (Link to `Team`): The newly referred team that joined.
  - `referred_by` (Link to `Team`): The team that referred the new team and is eligible to receive credits.
  - `credits_allocated` (Check): Set to `1` once the referral reward has been successfully credited.

---

### Key Functions & Methods

1. **`allocate_credits(self)`** (Whitelisted controller method):
   - Ensures the referred team (`for_team`) has spent at least the minimum threshold using `team_has_spent()`.
   - Reads the credit amount from single DocType `Press Settings` (using `free_credits_inr` or `free_credits_usd` depending on `referred_by` team's currency).
   - Calls `team.allocate_credit_amount(...)` to allocate the reward.
   - Marks `credits_allocated = True`.

2. **`team_has_spent(team, usd_amount=25.0, inr_amount=1800.0)`**:
   - Queries `Invoice` documents where `team` is the referred team, `status` is `Paid`, and `transaction_amount > 0`.
   - Sums up the transaction amounts and compares it with the threshold depending on the team's currency (`INR` vs `USD`).

3. **`credit_referral_bonuses()`**:
   - Scheduled / background task that queries all `Referral Bonus` records with `credits_allocated = False`.
   - Iterates through them and triggers `allocate_credits()` on any that now meet the spending criteria.
