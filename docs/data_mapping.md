# Data Mapping and Design Decisions

## Dataset source of truth
- Source workbook: `data/PulseIQ_Dataset.xlsx`
- CSV exports: `data/raw/*.csv`
- Source files are immutable; ETL writes to `data/clean/` and `data/rejected/`.
- The workbook/CSV exports have matching row and column counts for all 29 non-README sheets.

## Data-contract coverage gap
The supplied `data_contracts.csv` contains 42 column rules for only four feeds: `fact_task`, `fact_anomaly`, `fact_attrition_risk`, and `fact_forecast`. The playbook refers to all fact sheets, so the ETL supplements the official contracts with:
1. data-dictionary type parseability checks for every dataset;
2. primary-key and duplicate-row checks;
3. explicit business/reference checks for payroll employee keys and employee/run uniqueness, attendance after exit, reversed leave dates, invoice/expense arithmetic, and payments referencing quarantined invoices;
4. explicit SCD Type 2 interval repair with a row-level transformation log.

This gap is documented rather than claiming the source has a complete contract for every table.

## Table layers
- `raw`: original CSV exports loaded without correction.
- `clean`: ETL-accepted rows after validation; row-level rejects go to `data/rejected/`.
- `warehouse`: dimensions and facts with primary keys and selected foreign keys.
- `governance`: data dictionary, contracts, metric dictionary, and DQ catalogue.
- `metrics`: 28 reusable views based on official metric formulas.
- `dq`: 14-check SQL summary view and ETL freshness logs.

## SCD Type 2 rules
- `dim_employee.employee_key` is the unique version key.
- `employee_id` is a natural person identifier and repeats across history versions; do not use it as the history join key when a fact already supplies `employee_key`.
- Payroll, attendance, leave, and attrition-risk facts use `employee_key`.
- `fact_task` and `fact_anomaly` carry only natural employee IDs; `warehouse.v_fact_task_employee_history` and `warehouse.v_fact_anomaly_employee_history` use event date/period to resolve the correct history row.
- One overlapping source interval was found for employee version `employee_key=100000`. The clean layer clips `valid_to` to the day before the next `valid_from`, and records the old/new value in `logs/etl_transform_log.csv`. Raw data is unchanged. The DQ suite still reports the source defect against `raw.dim_employee`.

## Quarantine policy implemented
- Payroll: 4 rows rejected — duplicate employee/run extras and two orphan employee/key rows. Keep the first row for each employee/run; do not reject the original valid row.
- Attendance: 4 rows rejected because the attendance month is after the employee exit month.
- Attrition risk: 5 rows rejected because their `as_of_date` differs from the dominant batch date (2026-09-30).
- Task board: 20 rows rejected for completed-before-started dates or Done status without completion date.
- Leave: 2 rows rejected for end date before start date.
- Invoice: 1 row rejected for impossible invoice balance; the payment referencing that rejected invoice is also quarantined to preserve referential integrity.
- Expense: 1 row rejected because total amount does not equal amount excluding GST plus GST.
- Other source rows remain available; warnings are captured by PQ-03 instead of silently being discarded.

## Known unresolved check result
After the four bad payroll rows are quarantined, one payroll-to-ledger difference remains for 2026-06: payroll employer cost is INR 54,664,233.35 and ledger salary-related expense is INR 54,682,683.35 (ledger exceeds payroll by INR 18,450.00). Do not patch or exclude another row without evidence; investigate the ledger posting/source mapping. The raw DQ check also reports five monthly differences before quarantine.

## Metric privacy and grain
- Each metric view is based on `metric_dictionary.csv`; view names are `metrics.m01_*` through `metrics.m28_*`.
- Views with a minimum group size include `group_size` and filter groups below the official threshold.
- Salary measures are aggregated by department/month; no employee names or individual salary rows are exposed through the metric views.
- The supplied forecast horizon starts in October 2026, after the last actual month (September 2026). M28 therefore returns forecast rows with `mape_pct = NULL` and an explicit status until overlapping actuals arrive; it does not invent backtest values.
- `dim_date` in the warehouse is extended through the forecast horizon (March 2027). The source workbook/CSV remains unchanged; future holiday flags are not invented (weekends are computed, public holidays are marked unknown/not set in the source extension).


## Schema drift policy
- The full `data_dictionary.csv` is the schema authority because `data_contracts.csv` specifies selected columns for four feeds rather than every exported column.
- If a table is missing a dictionary-defined column or contains an unrecognized column, ETL fails closed before overwriting clean outputs and writes `logs/etl_schema_drift.csv`.
- This policy is tested with synthetic missing-column and unexpected-column cases.
- The contract's “one of the published codes” rule for anomaly `reason_code` cannot be validated against an authoritative allow-list because no separate list is supplied. Do not derive a production allow-list from observed data without owner approval.
