# PQ-03 — Planted-Issue Reconciliation

The independent ETL and DQ checks were written and run before opening the PQ-03 planted-issues reference. The reference lists 11 issues; each is detected by the corresponding check below. The separate PQ-09 and PQ-13 reconciliation/reference files remain unopened.

| Planted issue | Independent check | Result |
|---|---|---|
| DQ-01 | DQ-C05 | PASS — 4/4 affected attendance rows detected and quarantined |
| DQ-02 | DQ-C03 | PASS — duplicate groups detected; only later duplicate rows PI-X0001 and PI-X0002 quarantined; original rows retained |
| DQ-03 | DQ-C04 | PASS — both orphan payroll rows detected and quarantined |
| DQ-04 | DQ-C01 | PASS — June 2026 mismatch detected. After bad payroll rows are quarantined, ₹18,450 remains and is documented as unresolved; do not silently adjust it. |
| DQ-05 | DQ-C07 | PASS — overpaid invoice detected; invoice and dependent payment quarantined |
| DQ-06 | DQ-C09 | PASS — 12 completed-before-started task rows detected and quarantined |
| DQ-07 | DQ-C09 | PASS — 8 Done tasks without completion dates detected and quarantined |
| DQ-08 | DQ-C10 | PASS — both reversed leave date rows detected and quarantined |
| DQ-09 | DQ-C11 | PASS — all 5 stale prediction rows detected and quarantined |
| DQ-10 | DQ-C08 | PASS — expense total mismatch detected and quarantined |
| DQ-11 | DQ-C12 | PASS — source SCD2 overlap detected; clean layer repaired with old/new values logged |

## Important interpretation

- Duplicate payroll rows: the check reports four rows participating in duplicate employee/run groups. ETL quarantines only the two added duplicate rows, not the two original valid payroll rows.
- June payroll-to-ledger difference: journal entry `JE-002094` remains balanced, but the salary expense total is ₹18,450 higher than payroll employer cost. The issue is reported and not silently patched.
- SCD Type 2: the source overlap is visible in the raw DQ result. The clean dimension clips the earlier version's `valid_to` to the day before the next version begins, and `logs/etl_transform_log.csv` preserves the old/new value and reason.
- Freshness: the five stale attrition predictions are planted issues. A separate warning also flags the 405 anomaly scores because the training snapshot is older than 24 hours relative to the current runtime; this is a snapshot freshness warning, not one of the 11 planted defects.
