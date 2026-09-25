---
status: accepted
owner: project
updated: 2026-09-25
tags: [loans, ui, accessibility]
---

# Trial four arrangements of the same loan detail

The owner prefers the tabbed mockup, but wants to compare Tabs, Service desk,
Expandable sections and the previous Classic layout during daily work.

Render the existing detail content once. Annotate its sections and move those
same DOM nodes into Bootstrap-based arrangements. Classic restores their original
locations using position markers. Never clone transaction forms, camera inputs,
CSRF fields or customer data into competing implementations. Switching preserves
control identity and unsaved selections; financial services, permissions and URLs
remain authoritative. It requires no HTTP request or database query.

Tabs is the initial layout. Store only the selected layout string in browser
storage, keyed by user and workspace. Cross-device synchronization is outside this
trial. Unknown saved options fall back to Tabs; unavailable storage permits a
session-local choice. Without JavaScript the original Classic detail remains.

Keep current balances, identity, warnings and recommended actions outside the
content sections. Print actions remain prominent. Deep links open the relevant
tab or expandable section; tabs support arrow keys, Home/End and ARIA state.
Preserve all original controls and conditional authority. This is a layout trial,
not a trial workspace: transactions remain real business records.

Retirement is a later owner decision based on staff experience. A future removal
must keep a known fallback for saved preferences and preserve every feature.
See the [staff guide](../flows/loan-detail-layouts.md) and
[feature inventory](../plans/loan-detail-redesign.md).
