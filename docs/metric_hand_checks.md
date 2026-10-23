# PQ-04 — Five Independent Metric Hand Checks

These values were independently calculated from the ETL-cleaned CSVs using the official metric formulas and compared with the corresponding metric views in the original `outputs/pulseiq.duckdb` database. The original database was opened read-only for verification. The separate `outputs/pulseiq_mutation_test.duckdb` database contains deliberate test mutations and is not the production baseline.

## M01 — Headcount
- **Selection:** D01, 2026-09
- **Inputs:** headcount_end = 167
- **Formula:** `headcount_end`
- **Independent result:** **167**
- **Group size:** 167
- **Status:** Independent calculation matches DuckDB metric view

## M04 — Monthly attrition rate
- **Selection:** D01, 2026-09
- **Inputs:** exits = 2; headcount_start = 160
- **Formula:** `exits / headcount_start * 100`
- **Independent result:** **1.2500%**
- **Group size:** 160
- **Status:** Independent calculation matches DuckDB metric view

## M07 — Gross pay
- **Selection:** D01, 2026-09
- **Inputs:** sum(gross_pay) = 20720901.38; distinct employees = 169
- **Formula:** `SUM(gross_pay) grouped by department and month`
- **Independent result:** **20720901.38**
- **Group size:** 169
- **Status:** Independent calculation matches DuckDB metric view

## M13 — Attendance rate
- **Selection:** D01, 2026-09
- **Inputs:** present_days = 3301; half_days_unpaid = 17; scheduled_days = 3441
- **Formula:** `(present_days + 0.5 * half_days_unpaid) / scheduled_days`
- **Independent result:** **0.961784**
- **Group size:** 169
- **Status:** Independent calculation matches DuckDB metric view

## M22 — Task completion rate
- **Selection:** T01, SP-01
- **Inputs:** Done tasks = 50; non-cancelled tasks = 55
- **Formula:** `Done tasks / non-cancelled tasks`
- **Independent result:** **0.909091**
- **Group size:** 55
- **Status:** Independent calculation matches DuckDB metric view



## M19 — Payroll as % of revenue (additional check)
- **Selection:** company-wide, June 2026
- **Official numerator:** ledger salary-related expense, accounts 5001–5005 (not the payroll file total)
- **Ledger payroll cost:** INR 54,682,683.35
- **Payroll fact employer cost for reconciliation only:** INR 54,664,233.35
- **Revenue:** INR 81,787,200.00 from ledger accounts 4001–4004
- **Formula:** `ledger payroll cost / ledger revenue * 100`
- **Independent result:** **66.8597%**
- **Reconciliation note:** ledger exceeds payroll by INR 18,450.00. This is a known unresolved source difference, not a reason to change the numerator or silently alter a source row.
- **Status:** Independent calculation matches DuckDB metric view; INR 18,450 payroll-ledger reconciliation remains open.
