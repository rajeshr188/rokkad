---
status: active
owner: project
updated: 2026-10-17
tags: [testing, browser, fixtures]
---

# Offline browser layout verification

Install runtime requirements and `requirements-browser.txt` in the developer
environment, then `python -m playwright install chromium`. Use a disposable test
database configured as in [testing and migrations](testing-and-migrations.md).
Browser installation is a separate preparation step; ordinary layout runs make
no external asset requests. Bootstrap 5.3.8 is a checked-in, integrity-verified
[fixture](../../scripts/fixtures/bootstrap-5.3.8/README.md).

```sh
python scripts/browser_fixtures.py
python manage.py test \
  scripts.check_loan_detail_layouts.NativeLayouts.test_browser \
  scripts.check_loan_detail_layouts.ImportedLayouts.test_browser \
  scripts.check_completed_payout_layouts.CompletedPayoutLayouts.test_browser \
  scripts.check_loan_architecture_layouts.PolicyLayouts.test_browser \
  scripts.check_loan_architecture_layouts.CohortLayouts.test_browser \
  scripts.check_monitoring_evidence_layouts.MonitoringEvidenceLayouts.test_browser \
  scripts.check_counter_workflow_layouts.CounterEntryLayouts.test_review \
  scripts.check_counter_workflow_layouts.CounterNativeLayouts.test_review \
  scripts.check_counter_workflow_layouts.CounterPaperDisclosure.test_review \
  --settings django_project.settings.test --noinput
```

Select these methods explicitly: their base classes contain other domain tests.
The scripts render fictional Django records, intercept browser network traffic,
and write HTML/screenshots/metrics under ignored `outputs/` task folders. No
pre-existing `outputs` or `staticfiles` directory is needed; Django finders load
authoritative static sources. Browser acceptance remains opt-in; fixture integrity
and directory/unsaved-entry JavaScript checks run in foundation CI.
