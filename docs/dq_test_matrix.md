# PQ-03 — Bad-Row Test Matrix

The official playbook requires each of the 14 checks to be challenged with a deliberately bad row in a copy of the data. The rules below specify the minimal mutation and expected outcome. SQL-backed mutation tests were executed against `outputs/pulseiq_mutation_test.duckdb`, a separate test copy. The original `outputs/pulseiq.duckdb` was kept unchanged. Observed test results are recorded in `outputs/dq_mutation_test_evidence.csv`. The mutation-test database contains deliberate changes and must not be used as the production baseline.

| Check | Test copy mutation | Expected result | Severity / action |
|---|---|---|---|
| DQ-C01 | Change one month’s salary-ledger account total by INR 1.00 without changing payroll. | FAIL; affected month appears in the difference output. | Critical: block sign-off; investigate posting. |
| DQ-C02 | Increase debit on one journal entry by INR 1.00 without changing its credit. | FAIL; entry_id returned. | Critical: block load/sign-off. |
| DQ-C03 | Append a duplicate employee_id/run_id payroll row. | FAIL; duplicate group returned. | Critical: quarantine duplicate and trace source. |
| DQ-C04 | Append a payroll row with an employee_id absent from dim_employee. | FAIL; orphan row returned. | Critical: quarantine or fix approved key. |
| DQ-C05 | Append attendance for an employee after the exit month. | FAIL; attendance row returned. | Warning: review with HR. |
| DQ-C06 | Increase unpaid_absence_days by more than 0.5 over payroll lop_days for one employee-month. | FAIL; employee-month returned. | Warning: review payroll mapping. |
| DQ-C07 | Set amount_paid above total_amount or balance_due below -0.01. | FAIL; invoice_id returned. | Warning: correct invoice/payment source. |
| DQ-C08 | Change total_amount so it differs from amount_excl_gst + gst_amount by more than INR 0.01. | FAIL; expense_id returned. | Warning: correct bill entry. |
| DQ-C09 | Set completed_date before started_date, or set status=Done with no completed_date. | FAIL; task_id returned. | Warning: correct task board. |
| DQ-C10 | Set end_date one day before start_date on a leave row. | FAIL; leave_request_id returned. | Warning: correct leave dates. |
| DQ-C11 | Set an attrition prediction as_of_date more than seven days behind the latest batch, or make scored_at older than 24 hours. | FAIL; stale prediction/anomaly row returned. | Warning: request a fresh feed; distinguish static-snapshot age from model quality. |
| DQ-C12 | Overlap two validity intervals for the same employee_id. | FAIL; overlapping employee version returned. | Critical: repair history with logged old/new values. |
| DQ-C13 | Use a test run log whose latest SUCCESS finished more than 24 hours ago. | FAIL; freshness result is 1 bad row. | Critical: check scheduler/source availability. |
| DQ-C14 | Temporarily remove the HAVING/minimum-group suppression from a restricted metric view and create a group below its threshold. | FAIL; privacy violation returned. | Critical: do not publish; restore suppression. |

## Evidence status

- Actual source-data run: all 14 check IDs are present in the independent pandas summary; source defects are reported as failures rather than hidden.
- Static SQL audit: 14 SQL check IDs are declared.
- Mutation tests: all 14 checks were challenged in the separate `outputs/pulseiq_mutation_test.duckdb` test copy. The recorded observations and final accumulated test-database counts are in `outputs/dq_mutation_test_evidence.csv`.
- DQ-C01 through DQ-C12: the introduced violations were detected by the corresponding checks.
- DQ-C13: a fresh successful test run changed the check to PASS; making that run 48 hours old changed it to FAIL.
- DQ-C14: temporarily removing the M01 suppression filter exposed 81 below-threshold groups and changed the check to FAIL. The production suppression rule must remain in place.
- Important: the test database contains accumulated deliberate mutations. Its final counts are not isolated per-mutation counts and must not be presented as production results. The original `outputs/pulseiq.duckdb` remains the production baseline.
