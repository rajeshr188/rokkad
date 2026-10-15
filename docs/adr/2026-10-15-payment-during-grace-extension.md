---
status: accepted
owner: project
updated: 2026-10-15
tags: [billing, access, grace, razorpay]
---

# Permit payment during a plain access extension

The owner cannot start JSK's monthly payment after the requested grace extension.
Both monthly and annual eligibility currently reject every access-decision row,
making operational continuity prevent the purchase that it was intended to support.

Share one narrow access-history check between selected monthly and annual offers.
An access decision is compatible only when it grants full access, has no separate
Plan and freezes no alternate entitlements. All history must satisfy that rule;
restrictions, return-to-default decisions and separately provisioned grants retain
the existing review requirement. Expired plain extensions are also compatible.
This does not change free-trial eligibility or public rollout scope.

Purchase preparation rechecks under the Company lock shared with the administrator
access service. Preserve immutable grants and original trial dates. A grant neither
creates a payment nor moves the paid period: monthly uses verified provider dates,
annual starts on verified capture. When the extension ends, ordinary paid access
continues if valid. No additional free days are added to the paid term.

Owner consent, billing history, unused-mandate release, lifecycle, seat limits,
mode, price and overlapping-purchase checks remain. Annual capture repeats its
existing eligibility check; no receipt or paid access is invented by this change.
The original access policy and its restriction precedence remain unchanged.
