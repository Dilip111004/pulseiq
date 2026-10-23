# PulseIQ Phase 1 — Data Foundations & Governance (PQ-01 to PQ-04)

**Deadline:** 24 October 2026 (user-provided)  
**Dataset:** Fictional Zenith Nova Technologies training data, cutoff 30 September 2026.  
**Scope:** PQ-01 ETL, PQ-02 star-schema warehouse, PQ-03 data quality gatekeeper, PQ-04 governed metric layer.

> Verification note: the ETL, DuckDB warehouse, SQL data-quality checks, and metric views have been executed locally. Warehouse reconciliation, SQL check outputs, metric hand checks, and 14 SQL mutation-test validations are documented in the outputs and docs. The original `outputs/pulseiq.duckdb` is the production baseline; `outputs/pulseiq_mutation_test.duckdb` is a deliberately mutated test copy. Critical source-data findings, including the unresolved June 2026 payroll-ledger difference, remain subject to review.

## What is included

- `data/raw/`: all 29 CSV exports, unchanged.
- `data/PulseIQ_Dataset.xlsx`: supplied workbook.
- `src/run_etl.py`: PQ-01 ETL, official contract validation, baseline data-dictionary checks, business-key/reference checks, quarantine outputs, logs, and explicit SCD2 repair log.
- `src/build_warehouse.py`: loads raw/clean data into DuckDB, creates constrained warehouse tables, extends the date dimension for the forecast horizon, creates temporal employee-history views, executes metric/DQ SQL, exports metric views.
- `src/run_dq_checks.py`: independently runs PQ-03 checks against raw data and exports summary plus row-level evidence.
- `sql/03_metric_views.sql`: all 28 PQ-04 metric views plus metric catalog.
- `sql/02_data_quality_checks.sql`: all 14 SQL quality checks, a persisted `dq.dq_results` summary with table/status/count/run time, and a standardized `dq.v_bad_rows` evidence view.
- `tests/test_etl.py`: ETL row accounting, keys, foreign-key integrity, SCD2 history, quarantine counts, transformation logging, schema-drift policy, and an M19 SQL regression guard.
- `docs/star_schema.mmd`: schema diagram source.
- `docs/data_mapping.md`: source mapping, decisions, data-contract coverage gap, and known unresolved reconciliation.
- `docs/task1_contract_notes.md`: column promises for the four contracted feeds and the schema-drift policy.
- `docs/dq_test_matrix.md`: the bad-row mutation plan and recorded validation results for all 14 SQL quality checks; evidence is saved in `outputs/dq_mutation_test_evidence.csv`.
- `docs/metric_hand_checks.md`: five required hand checks plus an additional M19 ledger-based check.
- `docs/task_by_task_guide.md`: beginner-friendly run steps and evidence for each of the four tasks.
- `docs/metric_hand_checks.md`: five required independent metric calculations plus an additional M19 reconciliation check.
- `docs/metric_definition_audit.md`: all 28 metric IDs, official grain/unit/privacy threshold and static review findings.
- `docs/dq_gate_policy.md`: decision for Critical versus Warning checks and the current sign-off blocker.
- `docs/planted_issue_reconciliation.md`: comparison of the independent checks with the 11 PQ-03 planted issues, performed only after running the checks.
- `outputs/dq/`: current raw-data check report and bad-row evidence.
- `logs/`: ETL run/table logs and explicit transformation log.

## Run on your computer

Use Python 3.11 or newer. From the project root:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

python -m pip install -r requirements.txt
python src/run_all.py
pytest -q
```

`src/run_all.py` runs the ETL, pandas DQ report, and DuckDB warehouse/metric build in the correct order. If using Windows PowerShell, activate the environment with the Windows command shown above.

### Expected outputs

- `data/clean/*.csv`: accepted rows.
- `data/rejected/*_rejected.csv`: rejected rows with `source_table`, original source row number, and explicit `reject_reasons`.
- `logs/etl_run_log.csv`, `logs/etl_table_log.csv`, `logs/etl_transform_log.csv`.
- `outputs/dq/dq_results.csv` and `outputs/dq/dq_bad_rows.csv`: independent source-data quality evidence.
- `outputs/pulseiq.duckdb`: raw, clean, governance, warehouse, metrics, and DQ schemas.
- `outputs/warehouse_row_reconciliation.csv`: clean-to-warehouse row counts.
- `outputs/dq_sql_results.csv`: the 14 SQL DQ check results, including source table and run time; review all Critical failures before sign-off.
- `outputs/dq_sql_bad_rows.csv`: row-level evidence returned by the SQL DQ view.
- `outputs/m01_*.csv` … `outputs/m28_*.csv`: exported metric-view results.

## Current ETL execution evidence

The most recent ETL run completed with:
- 29 CSV tables processed.
- 62,770 input rows across all source/governance exports.
- 62,732 accepted rows.
- 38 quarantined rows.
- Row accounting passed: **62,770 = 62,732 + 38**.
- One SCD2 interval repair was logged; raw source remains unchanged.
- `pytest -q`: 13 tests passed in the current environment.

The total includes metadata/governance tables, not just fact rows.

## Current quality findings (raw source, before quarantine)

The independent PQ-03 run detected:
- C01 payroll-to-ledger mismatch in five months before quarantine.
- C02 ledger entries balance.
- C03 four rows participate in duplicate employee/run groups; ETL quarantines only the later duplicate occurrences.
- C04 two payroll rows have orphan employee IDs/keys.
- C05 four attendance rows occur after the employee exit month.
- C06 one employee-month has unpaid absence not reflected within tolerance.
- C07 one invoice has an invalid balance.
- C08 one expense fails amount-plus-GST arithmetic.
- C09 twenty task rows have invalid completion-date conditions.
- C10 two leave requests have end date before start date.
- C11 five risk predictions have stale batch dates and 405 anomaly records are older than 24 hours relative to the current run. The anomaly feed is a static training snapshot; this is a freshness warning, not evidence that the scoring model itself is wrong.
- C12 one employee-history overlap exists in the raw source and is repaired in the clean SCD2 layer with an explicit log.
- C13 ETL run freshness passes.
- C14 SQL check execution and mutation validation are documented in `docs/dq_test_matrix.md` and `outputs/dq_mutation_test_evidence.csv`.

After quarantining the four bad payroll rows, one payroll-to-ledger mismatch remains for June 2026: ledger salary-related expense exceeds payroll employer cost by **₹18,450.00**. This is intentionally documented as unresolved rather than silently deleting or changing a valid row. Investigate the June ledger posting/source mapping before claiming C01 passes.

## Data-contract coverage limitation

The supplied `data_contracts.csv` has 42 column rules for only four feeds (`fact_task`, `fact_anomaly`, `fact_attrition_risk`, `fact_forecast`). Other tables are checked using `data_dictionary.csv` types, primary-key rules, and documented table-specific business checks. This is explicitly recorded in `docs/data_mapping.md`.

## Important design decisions

- Preserve raw data and do not open validation answer keys before implementing/running independent checks. The PQ-03 planted-issues list was opened only after the independent checks were implemented and run; the PQ-09 and PQ-13 answer/reference files remain unopened.
- Use `employee_key` for employee history joins whenever available; `employee_id` repeats across SCD2 versions.
- Never expose individual salary or attrition-risk data through metric views. Metric outputs are aggregated and restricted by `minimum_group_size`.
- Forecasts start in October 2026, after the last actual month in September 2026. M28 reports `NULL` MAPE with a clear status until actuals overlap with forecast months.
- The warehouse date dimension extends through March 2027 to support forecast keys. Generated future public-holiday flags are not invented.
- All data is fictional training data. Keep any GitHub repository private unless the project owner explicitly authorizes publication.

## Task acceptance checklist

### PQ-01 — ETL Pipeline & Data Contracts
- [x] Repeatable command runs against all CSV exports.
- [x] Contract checks for the four feeds with official contracts.
- [x] Fail-closed schema-drift detection against the complete data dictionary; tests cover missing and unexpected columns.
- [x] Data-dictionary type checks and primary-key checks for remaining tables.
- [x] Rejected rows preserve source row numbers and reason codes.
- [x] Input = clean + rejected row accounting passes.
- [x] SCD2 repair is explicitly logged.
- [ ] Confirm the authoritative list of allowed anomaly `reason_code` values with the project owner; the contract says “published codes” but the ZIP does not provide a separate authoritative code list. Plain-English fields also need a human semantic review.

### PQ-02 — Star-Schema Warehouse
- [x] Warehouse DDL and loading script authored with primary/foreign keys.
- [x] Employee temporal join views authored for facts without employee_key.
- [x] Forecast calendar extension authored.
- [x] Run DuckDB build and inspect `outputs/warehouse_row_reconciliation.csv` (25 tables; zero row-count mismatches).
- [x] Verify warehouse foreign-key constraints (39 found) and representative fact-to-dimension joins (zero orphan rows in five tested joins).

### PQ-03 — Data Quality Gatekeeper
- [x] Fourteen checks authored in Python/SQL.
- [x] SQL result schema includes check ID, name, source table, severity, status, bad-row count, run time and detail.
- [x] Standardized SQL bad-row evidence view authored for all 14 checks.
- [x] Raw-data summary and row-level evidence generated independently.
- [x] Planted issue list/answer keys not opened before checks.
- [x] Execute SQL DQ results after the warehouse/metric build and inspect the summary and row-level evidence.
- [x] Run all 14 bad-row mutation tests in `docs/dq_test_matrix.md`; evidence saved in `outputs/dq_mutation_test_evidence.csv`.
- [ ] Review and explain all Critical failures and the remaining June payroll-ledger mismatch.

### PQ-04 — Governed Metric Layer
- [x] 28 metric views authored from `metric_dictionary.csv`.
- [x] M19 corrected to use ledger payroll accounts 5001–5005 for its numerator, with payroll-file cost retained only for reconciliation visibility.
- [x] Metric catalog view authored.
- [x] Minimum group size filters included in restricted metric views.
- [x] Five independent calculations documented.
- [x] Execute all 28 metric views and compare five independent hand checks plus the M19 check to SQL outputs.
- [x] Confirm all 28 metric views execute; M28 returns `NOT_YET_MEASURABLE_NO_OVERLAPPING_ACTUALS`.
