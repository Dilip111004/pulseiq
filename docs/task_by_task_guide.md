# Beginner Guide — Phase 1 Tasks 1–4

This guide follows the official task numbers in `reference/02_Task_Playbook.html`. These are the four foundation tasks (PQ-01 to PQ-04), not the later dashboard tasks.

## Before starting

1. Keep the supplied workbook and `data/raw/*.csv` unchanged.
2. Open a terminal in the `pulseiq_phase1_solution` project folder.
3. Use Python 3.11 or newer.
4. Install dependencies using `python -m pip install -r requirements.txt`.

## Task 1 — PQ-01: ETL Pipeline & Data Contracts

**Purpose:** read every CSV, validate its columns and business rules, keep valid records in the clean layer, and quarantine invalid records with reasons.

**Run:** `python src/run_etl.py`

**Outputs to inspect:**
- `data/clean/`: accepted rows.
- `data/rejected/`: rejected rows and reason codes.
- `logs/etl_run_log.csv`: run status and total row accounting.
- `logs/etl_table_log.csv`: input/clean/rejected counts per table.
- `logs/etl_transform_log.csv`: explicit SCD Type 2 repair details.

**Important:** input rows must equal clean rows plus rejected rows for every table. The latest verified run accounts for 62,770 input rows = 62,732 clean + 38 rejected. The four payroll rejects are two duplicate additions and two orphan-key rows; the original payroll rows are preserved.

## Task 2 — PQ-02: Star-Schema Warehouse

**Purpose:** create dimension and fact tables with primary keys, selected foreign keys, and employee history joins that respect SCD Type 2.

**Run:** after Task 1, `python src/build_warehouse.py`

This script requires DuckDB. It loads `raw`, `clean`, `governance`, and `warehouse` schemas, creates the warehouse tables, creates employee-history views for task/anomaly records that only have natural employee IDs, extends the warehouse date dimension to cover forecast dates, and writes row-count reconciliation.

**Evidence to inspect after a successful run:**
- `outputs/pulseiq.duckdb`
- `outputs/warehouse_row_reconciliation.csv`
- `docs/star_schema.mmd`

Do not use `employee_id` alone to join a fact to a particular employee history version if the fact already has `employee_key`. The employee ID repeats across versions.

## Task 3 — PQ-03: Data Quality Gatekeeper

**Purpose:** run all 14 catalogued checks, record failures, and show the issue evidence.

**Run:** `python src/run_dq_checks.py` for independent pandas checks. The DuckDB SQL summary is created by `src/build_warehouse.py` after the metric views exist.

**Evidence to inspect:**
- `outputs/dq/dq_results.csv`
- `outputs/dq/dq_bad_rows.csv`
- `outputs/dq/planted_issue_reconciliation.csv`
- `docs/planted_issue_reconciliation.md`
- `outputs/dq_sql_results.csv` from the completed DuckDB execution
- `outputs/dq_sql_bad_rows.csv` for standardized row-level SQL evidence
- `dq.dq_results` table inside `outputs/pulseiq.duckdb`

The source contains defects on purpose. A `FAIL` means the check detected a source-data problem; it does not mean the detector failed. All 11 planted PQ-03 issues were matched after the independent checks were written and run. All 14 SQL mutation checks were executed against the separate `outputs/pulseiq_mutation_test.duckdb` test copy; results are recorded in `outputs/dq_mutation_test_evidence.csv`. The mutation database contains deliberate test changes and is not the production baseline. The PQ-09 and PQ-13 answer/reference files were not opened.

## Task 4 — PQ-04: Governed Metric Layer

**Purpose:** implement the 28 official metrics as reusable SQL views, apply the minimum-group-size rule, and publish a catalog.

`src/build_warehouse.py` executes `sql/03_metric_views.sql` and exports each view to `outputs/m01_*.csv` through `outputs/m28_*.csv`.

**Evidence from the completed DuckDB execution:**
- `outputs/m01_*.csv` through `outputs/m28_*.csv`
- `governance.metric_catalog` view in DuckDB
- `docs/metric_hand_checks.md`
- `docs/metric_definition_audit.md`
- DQ-C14 in `outputs/dq_sql_results.csv`

No individual salary rows or employee names are exposed through the metric views. M28 is deliberately marked not-yet-measurable because the provided forecast horizon begins after the last actual month; it must not fabricate forecast accuracy.

## One unresolved item to explain honestly

The payroll-to-ledger check detects five monthly differences in raw data. Four are resolved by quarantining the four invalid payroll rows. One difference remains for June 2026: ledger salary-related expense exceeds payroll employer cost by INR 18,450. The ledger journal entry balances, but the two totals do not. Investigate the posting/source mapping and document the evidence instead of silently changing a row.

## Final review and remaining sign-off

1. Confirm the final report accurately records the ETL, warehouse, SQL DQ, mutation-test, and metric-view results.
2. Keep the original `outputs/pulseiq.duckdb` as the production baseline and the mutated test database clearly labelled as test-only.
3. Confirm all six independent metric checks match their DuckDB views; see `docs/metric_hand_checks.md` and `outputs/metric_hand_checks.csv`.
4. Keep the June 2026 INR 18,450 payroll-to-ledger difference documented as unresolved until explained or formally accepted by the project owner.
5. Confirm the authoritative allowed anomaly `reason_code` values with the project owner; do not invent an approved list.
6. Prepare the required final 2-3 page PDF report and verify its contents and file size before submission.
