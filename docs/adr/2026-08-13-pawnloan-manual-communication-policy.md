---
status: accepted
owner: loans
updated: 2026-08-13
tags: [loans, risk, communication, policy, kiss]
related: [../flows/pawn-risk-alert-borrower-communication.md]
---

# PawnLoan manual communication policy

## Context

The manual PawnLoan risk-notice pilot needs workspace operating rules without
turning Notify v2 into an automated collections engine. Contact, consent,
current risk, approved templates, provider readiness, and deduplication already
remain mandatory per notice.

## Decision

Loans owns one tenant-scoped `PawnLoanCommunicationPolicy` per workspace:

- preferred channel chooses the initial manual preview only;
- optional quiet hours block preview and confirmation on every enabled channel;
- a channel-specific cooldown blocks a repeat notice of the same kind to the
  same borrower;
- an escalation DPD threshold displays internal operator guidance only.

The policy identity and values participate in the confirmation fingerprint and
are frozen into notice evidence. A policy change therefore invalidates an old
preview. Email and WhatsApp remain explicit operator choices; there is no
automatic send, fallback, scheduling, bulk conversion, or borrower escalation.

## Consequences

The workflow gains predictable workspace controls and auditable evidence while
remaining KISS: one row, one setup form, and enforcement at the existing Loans
readiness boundary. Notify v2 continues to own rendering and delivery, not the
business decision to communicate. Any future automation requires a separate
decision and acceptance evidence.
