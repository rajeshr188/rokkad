---
status: accepted
owner: project
updated: 2026-09-24
tags: [configuration, retirement, ui]
---

# Retire ineffective preferences while preserving existing data

The owner accepted the preferences/navigation readiness review and authorized its
implementation. Current business workflows have no discovered consumer of the
central preference service or legacy CompanyPreferences wrapper. Nonetheless,
dynamic-preferences still supplies model bases and app registration, so removing
the dependency is a schema/runtime cleanup rather than simply deleting a package.

Retire central and legacy end-user editing routes now. Preserve their bookmarks
as authenticated, canonically authorized, GET-only guidance pointing to actual
loan policies, licences, printing and business profile settings. POST returns 405
after authorization. Remove the generic package editor route and the Preferences
navigation entry. Make the retained Workspace preference admin read-only.

Retain existing models, registry/service compatibility code, migration history and
dependency for this bounded release. No data is deleted and no dormant financial
preference is connected to current lending calculations. Five rehearsal preference
and audit tables were privately inventoried, all empty; this does not establish
that every other database is empty. Full package/model cleanup requires a tested
fresh-install and existing-database migration path, not a last-minute uninstall.

Navigation visibility must use the same normalized actions as existing workspace
navigation. Reports/history belong outside Settings for data readers. All target
views retain their existing authorization and RLS enforcement.

## Completed dependency retirement

The next authorized increment removes django-dynamic-preferences and unused
persisting-theory, package app registration and dormant registries/services/forms.
Workspace/company preference records use ordinary Django fields with unchanged
tables. Retained global/user models explicitly map the former package tables;
the user foreign key stays in Django's deletion collector. They expose no runtime
preference API or new admin editing surface.

Migration 0003 separates model state from database adoption: retain existing
raw tables after validating their columns; create them if missing. Existing values
are never deserialized or transformed. Its reverse preserves the tables rather
than deleting retained data. Old package migration rows/content types remain as
history. Future table deletion requires a separate data-retention decision.

A fresh PostgreSQL database and a restored populated rehearsal clone both passed
migration and drift checks without the packages installed. Synthetic values in all
five preference/audit tables survived; 87 loan/party tables were unchanged. Rehearsal
migration and page checks passed before deployment. This supersedes the temporary
package-retention decision above; it does not connect old settings to lending rules.
