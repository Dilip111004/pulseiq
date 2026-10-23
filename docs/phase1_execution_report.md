# PulseIQ Phase 1 â€” Execution Report
Updated: 23 October 2026
Deadline: 24 October 2026

## Scope
Phase 1 means the first four official foundation tasks in the project playbook:
1. PQ-01 ETL Pipeline & Data Contracts
2. PQ-02 Star-Schema Warehouse
3. PQ-03 Data Quality Gatekeeper
4. PQ-04 Governed Metric Layer

## Verified in this environment
- ZIP integrity check passed; 47 archive members.
- Workbook contains 30 sheets: README plus 29 data/governance sheets.
- All 29 CSV exports match the workbook sheets by row count and column count.
- ETL processed 29 CSVs and 62,770 total rows.
- Accepted rows: 62,732; quarantined rows: 38; row accounting passed exactly.
- The quarantine includes 4 payroll rows, 4 attendance rows, 5 attrition-risk rows, 20 task rows, 2 leave rows, 1 invoice row, 1 dependent invoice-payment row, and 1 expense row.
- One SCD2 `valid_to` repair is documented in `logs/etl_transform_log.csv`; raw source data remains unchanged.
- Thirteen automated tests pass (`pytest -q`) after adding schema-drift, M19, metric-catalog and DQ SQL-structure regression checks.
- ETL rerun check: all 58 clean/rejected CSV outputs were byte-identical across two consecutive runs.
- Schema drift policy is fail-closed: a missing or unexpected column is logged and the pipeline stops before overwriting clean outputs.
- The independent PQ-03 checks were run before opening the planted-issues list. All 11 planted issues are matched in `docs/planted_issue_reconciliation.md`.
- Static checks confirm exactly 28 metric-view definitions and all 14 DQ check IDs in SQL.
- SQL defines `dq.dq_results` and `dq.v_bad_rows`. SQL runtime checks and metric views were executed. The baseline DQ-C14 result was PASS with zero violations; the separate suppression-removal mutation test detected 81 below-threshold groups, as documented in `outputs/dq_mutation_test_evidence.csv`.
- M19 was corrected after metric-dictionary review: payroll-as-%-of-revenue now uses ledger accounts 5001-5005 for payroll cost, while exposing payroll-file cost only for reconciliation.

## PQ-03 check results against raw source data
| check_id   | check_name                         | status              |   bad_row_count |
|:-----------|:-----------------------------------|:--------------------|----------------:|
| DQ-C01     | Payroll equals ledger              | FAIL                |               5 |
| DQ-C02     | Ledger balanced                    | PASS                |               0 |
| DQ-C03     | Unique payroll rows                | FAIL                |               4 |
| DQ-C04     | No orphan employees                | FAIL                |               2 |
| DQ-C05     | No attendance after exit           | FAIL                |               4 |
| DQ-C06     | Unpaid leave deducted              | FAIL                |               1 |
| DQ-C07     | Invoice arithmetic                 | FAIL                |               1 |
| DQ-C08     | Expense arithmetic                 | FAIL                |               1 |
| DQ-C09     | Task dates sensible                | FAIL                |              20 |
| DQ-C10     | Leave dates sensible               | FAIL                |               2 |
| DQ-C11     | AI feeds are fresh                 | FAIL                |             410 |
| DQ-C12     | Dimension history does not overlap | FAIL                |               1 |
| DQ-C13     | Pipeline freshness                 | PASS                |               0 |
| DQ-C14     | Minimum group size                 | PASS                |               0 |

The DQ suite is intended to find defects, so `FAIL` means the raw source contains a quality issue to report, not that the detector failed. The 11 planted issues are all detected. DQ-C11 additionally reports that all 405 anomaly scores are older than 24 hours relative to the current run because this is a static training snapshot; distinguish that freshness warning from the five planted stale attrition predictions.

## Critical unresolved reconciliation
After quarantining the four bad payroll rows, the monthly payroll-vs-ledger check passes for all months except June 2026. June payroll employer cost is INR 54,664,233.35 and ledger salary-related expense is INR 54,682,683.35, leaving a difference of INR 18,450.00. The journal entry balances but the salary expense total does not reconcile to payroll. The source issue is detected and documented; do not change a valid row or ledger posting without evidence.

## Runtime verification status

- PQ-01: ETL completed successfully for 29 input tables and 62,770 rows. There are 62,732 clean rows and 38 rejected rows; row accounting passed.
- PQ-02: Warehouse build completed with 25 warehouse tables; all 25 table reconciliations matched.
- PQ-03: Python DQ checks and SQL DQ checks ran. Raw-source failures identify data-quality findings; they do not by themselves mean the clean warehouse contains those defects. The baseline DQ-C14 result was PASS with zero minimum-group-size violations; its separate mutation test detected 81 violations when suppression was temporarily removed in the test copy.
- PQ-04: All 28 metric views executed successfully. Six independent hand-checks matched their metric views. The metric catalog contains 28 entries with the documented governance fields.
- M01 independently matched active employee counts for all 891 department-month rows. M19 uses ledger accounts 5001–5005 for payroll cost, with payroll-file cost retained for reconciliation visibility.
- Thirteen automated tests passed (`python -m pytest`).
- The 11 planted issues are covered in `docs/planted_issue_reconciliation.md`. DQ-C11 also flags 405 stale anomaly scores from the static training snapshot, separately from the five planted stale prediction rows.
- SQL-backed bad-row mutation tests for all 14 checks were executed in the separate test copy. Results and observed validation are recorded in `outputs/dq_mutation_test_evidence.csv`; the test database contains deliberate mutations and is not the production baseline.
- The June 2026 payroll-to-ledger difference of INR 18,450.00 remains unresolved and documented. Do not silently adjust source data or ledger postings; formal acceptance is needed before treating this exception as signed off.
- `docs/dq_gate_policy.md` defines the fail-closed Critical/Warning decision. Review any remaining approval requirements before final sign-off.

## Remaining sign-off items

- Confirm the authoritative allowed values for anomaly `reason_code` with the project owner; do not invent or assume an approved list.
- Review the June 2026 payroll-to-ledger difference of INR 18,450.00 and obtain an explanation or formal acceptance before sign-off.
- Ensure the final submission PDF includes the actual execution results, limitations, and unresolved items.
