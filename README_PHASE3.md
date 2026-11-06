# PulseIQ — Phase 3: Money and Insight

Phase 3 extends PulseIQ with financial performance analytics, receivables and cash-flow visibility, cross-department impact analysis, AI-assisted signals, and an executive scorecard.

## Phase 3 dashboards

| Task | Dashboard | Streamlit page |
|---|---|---|
| PQ-11 | P&L and Expense Analytics | `pages/13_PL_and_Expense_Analytics.py` |
| PQ-12 | Invoices, Receivables and Cash Flow | `pages/14_Invoices_Receivables_Cash_Flow.py` |
| PQ-13 | Cross-Department Impact | `pages/9_Cross_Department_Impact.py` |
| PQ-14 | AI Signals | `pages/10_AI_Signals.py` |
| PQ-15 | Executive Scorecard | `pages/11_Executive_Scorecard.py` |

The Phase 3 entry point is `app_phase3.py`. It provides navigation to the five Phase 3 dashboards and keeps the Attendance and Leave and Attrition pages hidden in this Phase 3 navigation.

## Dashboard capabilities

### PQ-11 — P&L and Expense Analytics
- Presents operating revenue, other income, total expenses, operating profit, and net profit.
- Shows operating and net profit margins.
- Supports monthly financial analysis and expense breakdowns.
- Includes vendor-level expense analysis.

### PQ-12 — Invoices, Receivables and Cash Flow
- Summarizes open invoices and outstanding receivables.
- Separates not-yet-due balances from overdue balances.
- Presents receivables ageing.
- Summarizes recorded payments and paid-expense cash outflow.

**Interpretation note:** The cash-outflow figure represents paid expense records in the underlying data; it should not be interpreted as the company's complete cash outflow.

### PQ-13 — Cross-Department Impact
- Compares department-level monthly workforce and cost measures.
- Includes employer cost, overtime cost, and approved leave measures.
- Uses department-month comparison outputs for reconciliation.

### PQ-14 — AI Signals
- Presents detected anomaly signals and associated money-at-risk estimates.
- Includes a forecast horizon from October 2026 through March 2027, trained on data through September 2026.
- Forecast accuracy cannot be measured for this horizon until actual observations for the forecast months are available.

**Interpretation note:** Signals and forecasts should be reviewed in context and are not a substitute for financial or operational approval.

### PQ-15 — Executive Scorecard
- Presents eight selected headline KPIs with target, trend, and status context.
- Links headline measures to their detailed analytics pages.
- Includes financial targets stored in `data/clean/financial_kpi_targets.csv`.

**Target note:** The financial KPI thresholds in that configuration are proposed management targets, not independently verified or approved company targets. Confirm them with the relevant stakeholders before using them for formal performance evaluation.

## Recorded validation highlights

The following results were recorded during Phase 3 validation:

- **PQ-11:** Operating revenue of ₹1,259,204,600; total expenses of ₹1,036,264,914.42; net profit of ₹224,665,137.58; weighted operating margin of 17.70%.
- **PQ-12:** 62 open invoices and open receivables of ₹139,394,278; 708 payment records; recorded paid-expense outflow of ₹185,647,035.90.
- **PQ-13:** 198 department-month rows covering April 2025 to September 2026 across 11 departments. No duplicate department-month keys or missing department names/employer costs were reported in the validation summary.
- **PQ-14:** 405 anomaly rows were reported; 178 records had positive money-at-risk values. Total estimated money at risk was ₹31,421,239.07. The forecast horizon has no overlapping actuals yet, so forecast accuracy is not available.
- **PQ-15:** Eight headline KPIs were selected for the executive scorecard. Forecast accuracy and task completion were excluded because the required actual overlap or metric view was unavailable.

These are recorded project validation results, not guarantees that every future refresh will produce the same values. Results depend on the source data and the pipeline run.

## Technology

- Python
- Streamlit
- DuckDB
- Pandas
- Plotly
- ETL and warehouse-building scripts in `src/`

See `requirements.txt` for the project's Python dependencies.

## Run Phase 3 locally

Run the following commands from the repository root in an activated Python environment.

```powershell
# Install project dependencies
python -m pip install -r requirements.txt

# Build clean data from the tracked raw inputs
python src/run_etl.py

# Build or refresh the DuckDB warehouse and metric outputs
python src/build_warehouse.py

# Launch the Phase 3 Streamlit application
streamlit run app_phase3.py
```

The application expects the project data folders and scripts to be available in the repository. The warehouse builder creates `outputs/pulseiq.duckdb`. The database is generated locally and is not intended to be committed as a source file; the project ignores DuckDB database files.

## Cloud deployment

For Streamlit Community Cloud, configure the application to use:

- **Repository:** `Dilip111004/pulseiq`
- **Branch:** `phase-3-money-and-insight`
- **Main file:** `app_phase3.py`

The Phase 3 entry point checks whether the DuckDB warehouse is usable. If it is missing or unusable, it runs the ETL script and warehouse builder to initialize it from the repository's available data files. The full `run_all.py` workflow is not used for this startup step.

No live dashboard URL is included in this README.

## Repository and release

- **Repository:** `https://github.com/Dilip111004/pulseiq`
- **Phase 3 branch:** `phase-3-money-and-insight`
- **Phase 3 tag:** `phase-3`
- **Phase 3 feature commit:** `e1ad2bb` — `Complete Phase 3 - Money and Insight`
- **Cloud database initialization fix:** `4a575a0` — `Fix Phase 3 cloud database initialization`

Phase 1 and Phase 2 history are preserved on their respective branches/tags.

## Data and responsible use

PulseIQ analytics are only as reliable as the source data, transformations, and business definitions supplied to the project. Validate source completeness, reconcile material financial differences, and confirm KPI definitions and targets before making operational decisions.

Before deploying a repository publicly, verify that its tracked data and generated outputs do not expose personal, payroll, invoice, or other confidential information. Do not commit database files, credentials, secrets, or private records.

## Known limitations

- Forecast accuracy for October 2026–March 2027 is not yet measurable because actuals for those months are not available in the recorded validation period.
- The paid-expense cash-outflow measure is based on paid expense records and is not a complete company-wide cash-flow statement.
- Financial KPI thresholds are proposed configuration values and require stakeholder approval before formal use.
- AI anomaly signals and forecasts require human review and contextual validation.
