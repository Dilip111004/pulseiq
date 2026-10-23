# PulseIQ Phase 1 — Initial ZIP Audit
Date: 19 October 2026
Deadline supplied by user: 24 October 2026

## Scope and integrity
- ZIP: `drive-download-20261019T053838Z-1-001.zip`
- ZIP CRC check: PASS
- Files in archive: 47
- Main Excel workbook: `03_Data/PulseIQ_Dataset.xlsx` (4,898,186 bytes)
- Workbook sheets: 30 (README + 29 data/governance sheets)
- CSV exports: 29; each non-README workbook sheet has a matching CSV export.
- Workbook/CSV row and column count mismatches: 0 excluding README.
- Starter files include a DuckDB bronze loader, metric-view SQL examples, and requirements.
- Validation vault contains task-specific answer/reference files. These were NOT opened during this initial audit.

## Confirmed task scope
1. PQ-01 — ETL Pipeline & Data Contracts: repeatable pipeline; validate data; quarantine rejects with reasons; log input/output counts.
2. PQ-02 — Star-Schema Warehouse: build dimensions/facts; use `employee_key` for SCD Type 2 joins; ensure facts join to dimensions; reconcile row counts; include schema diagram.
3. PQ-03 — Data Quality Gatekeeper: implement all 14 catalogued checks; run automatically; record pass/fail and bad rows; compare with planted issues only after checks are written and run.
4. PQ-04 — Governed Metric Layer: implement 28 official metrics as reusable views; respect grain and minimum-group-size privacy; include metric catalog; manually verify at least five metrics.

## Dataset inventory
- Total CSV files: 29
- Total rows across CSV exports (metadata/governance tables included): 62,770
- Key fact sizes: payroll 7,344; attendance 7,343; leave 3,441; headcount 891; ledger 6,784; invoice 743; invoice payments 709; expenses 501; tasks 28,868; anomalies 405; attrition-risk 430; forecasts 72.
- Employee dimension: 1,606 history rows for 745 employee IDs, using SCD Type 2 history.
- Metric dictionary: 28 definitions.
- Data-quality catalog: 14 checks.
- Data contracts: 42 column-level contract rows covering four feeds (`fact_task`, `fact_anomaly`, `fact_attrition_risk`, `fact_forecast`).

## Important gap to handle transparently
The playbook says PQ-01 should validate the feeds against data contracts, but `data_contracts.csv` contains contracts for only four feeds. The remaining tables still need baseline type/null/key/relation checks using `data_dictionary.csv` and explicit table-specific rules. Do not claim every table has a complete official contract unless the project adds those contracts.

## Initial profile observations
- No exact duplicate full rows were found in the 29 CSV exports during the initial profile.
- Candidate primary-key checks were unique for the tested dimension/fact IDs and composite monthly keys. Additional business-key and cross-table checks are still required; unique row IDs do not prove the data is valid.
- Several nullable fields are present by design (for example exit dates, payment dates, optional anomaly money exposure, and optional task dates). Nulls must be checked against the contract and business rules rather than rejected indiscriminately.
- The workbook's README labels the data fictional/training-only, with cutoff 30 September 2026. Preserve this notice in documentation.

## Guardrails
- Keep the source CSV/XLSX files unchanged.
- Do not open `unlock_PQ-03_dq_known_issues.csv` until the independent check suite is implemented and run.
- Do not open `unlock_PQ-09_reconciliation_answer_key.csv` or `unlock_PQ-13_reference_summary_dept_month.csv` as they belong to later tasks and are outside Tasks 1–4.
- Do not publish individual-level salary/risk information or commit secrets.
