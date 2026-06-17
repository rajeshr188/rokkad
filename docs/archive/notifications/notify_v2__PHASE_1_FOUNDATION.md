---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Notify V2 Phase 1 Foundation

This folder contains the initial `notify_v2` scaffold created from the clean-slate redesign plan.

## Implemented in Phase 1

- tenant app registration in `django_project/settings/base.py`
- foundational models for:
  - `NotificationEventType`
  - `NotificationPolicy`
  - `NotificationRecipient`
  - `NotificationTemplate`
  - `NotificationBatch`
  - `NotificationEvent`
  - `NotificationJob`
  - `NotificationArtifact`
  - `NotificationAttemptLog`
- admin registration for operational visibility
- `emit_event()` service entry point
- placeholder app URL/view scaffold
- initial model tests

## Status after Phase 1 verification

Phase 1 is complete as the foundation layer:

- schema and migration are in place
- admin is registered
- `emit_event()` is available
- Phase 1 tests pass

## Handover into Phase 2

Phase 2 has now started with the first Girvi batch reminder workflow slice:

- renderer interface bridge for printable Girvi notices
- batch creation service for selected loans
- merged print bundle generation helper
- documentation for the manual print/post workflow

Remaining follow-up work for the next slice:

- batch list/detail/print UI actions
- explicit `PRINTED` / `POSTED` operator views
- dedicated `notify_v2` PDF layouts beyond the legacy bridge helper

