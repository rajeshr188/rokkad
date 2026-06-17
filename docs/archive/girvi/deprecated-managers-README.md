---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Deprecated Managers - Archive

## Timeline
- **Deprecated**: February 22, 2026
- **Phase Out**: Q2-Q3 2026
- **Removal Target**: September 30, 2026

## Files in This Directory

### Historical Reference

| File | Purpose | Status |
|------|---------|--------|
| `managers.py` | Original monolithic manager | âŒ ARCHIVED |
| `manager_improved.py` | Optimized version with modular chains | âŒ ARCHIVED |
| `new_manager.py` | Experimental manager | âŒ ARCHIVED |

## Migration Info

**New Manager**: `managers_refactored.py` (parent directory)

### What Changed
- âœ… Separate managers for GivenLoan and TakenLoan
- âœ… Removed loan_type conditionals
- âœ… All annotation methods preserved and enhanced
- âœ… Better semantic clarity

### How to Update
See: `docs/MIGRATION_TO_GIVENLOAN_TAKENLOAN.md`

## Current Manager Architecture

```python
# New (use this)
from girvi.managers_refactored import GivenLoanManager, TakenLoanManager

# Old (do NOT use)
# from girvi.managers import LoanManager  âŒ
# from girvi.manager_improved import ImprovedLoanManager  âŒ
```

## Reference: Method Mapping

See `managers_refactored.py` for:
- `GivenLoanQuerySet` - all given loan queries
- `TakenLoanQuerySet` - all taken loan queries
- `BaseLoanQuerySet` - shared methods

All original methods preserved and enhanced:
- `.for_table_display()`
- `.for_dashboard_metrics()`
- `.with_duration_metrics()`
- `.with_interest_metrics()`
- `.overdue()`
- etc.

## Legacy Loan Model Status

The old `Loan` model (in `models/loan.py`) still exists but is DEPRECATED:
- Used only for backward compatibility
- Data access is read-only
- Will be removed by Q3 2026
- Do NOT use for new code

---

**If you need anything from these archived files, refer to the main documentation or the refactored managers.**

