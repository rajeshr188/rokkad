"""Side-by-side standalone accounting successor package.

The tenant app persists accounting masters, external classifications, voucher
headers, and complete draft atomic transactions. It still has no URLs, admin,
or runtime posting integration. Authorized intent can be finalized into one
immutable posting batch and corrected only through new, exact opposite
evidence. Posted account transactions can carry non-financial open-item and
allocation evidence whose reversals are also compensating rows. DEA remains
the production accounting authority. MVP financial reports are read-only
projections over this persisted truth; no reporting balances are stored.
"""
