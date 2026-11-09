# PulseIQ — Unified Workforce, Financial and Business Analytics Platform

PulseIQ brings the Phase 1, Phase 2 and Phase 3 dashboards together in one Streamlit application while keeping phase-specific submission evidence organized in separate folders.

## Run the unified application

Run these commands from the repository root in PowerShell:

```powershell
# Activate your existing virtual environment if it is not already active
.\.venv\Scripts\Activate.ps1

# Install dependencies if required
python -m pip install -r requirements.txt

# Launch all phases from one application
streamlit run app.py
```

The sidebar is organized into three groups:

### Phase 1 — Workforce & Headcount
- Workforce & Headcount Dashboard

### Phase 2 — Official Tasks
- PQ-06 Attendance & Leave
- PQ-07 Attrition Analytics
- PQ-08 Team Productivity
- PQ-09 Payroll Cost
- PQ-10 Budget vs Actual
- Custom KPI Builder

### Phase 3 — Money and Insight
- PQ-11 P&L and Expense Analytics
- PQ-12 Invoices, Receivables and Cash Flow
- PQ-13 Cross-Department Impact
- PQ-14 AI Signals
- PQ-15 Executive Scorecard

## Repository structure

```text
pulseiq/
├── app.py
├── app_phase1_backup.py        # retained source backup; not the launcher
├── app_phase3.py               # retained Phase 3 launcher for reference
├── pages/                      # shared runnable dashboard pages
├── phase-1/                    # Phase 1 report and execution evidence
├── phase-2/                    # Phase 2 report, board pack and demo script
├── phase-3/                    # Phase 3 report and technical README
├── data/                       # shared raw, clean and rejected data
├── src/                        # ETL and warehouse pipeline
├── sql/                        # DQ and metric SQL
├── docs/                       # shared technical documentation
└── outputs/                    # generated metric, DQ and analysis outputs
```

The phase folders hold phase-specific deliverables and indexes. The actual runnable dashboard pages, data, scripts and warehouse remain in their shared root-level locations so the application does not maintain duplicate copies of the same runtime assets.

## Data warehouse initialization

The unified launcher checks `outputs/pulseiq.duckdb`. If the database is missing or unusable, it runs:

1. `src/run_etl.py`
2. `src/build_warehouse.py`

Only the generated DuckDB file is removed if it is unusable. The launcher does not delete source CSV files.

## Technology

- Python
- Streamlit
- Pandas
- Plotly
- DuckDB
- SQL

## Repository

- GitHub: https://github.com/Dilip111004/pulseiq

## Important notes

- `app.py` is the unified entry point for Phases 1–3.
- `app_phase1_backup.py` is retained as a backup of the original standalone Phase 1 dashboard.
- `app_phase3.py` is retained as the original Phase 3 entry point; use `app.py` for the unified application.
- Shared data and outputs are not duplicated into the phase folders.
- Do not commit `.venv`, `__pycache__`, generated database files, credentials, secrets, or confidential records.
- Review data privacy and project validation evidence before public deployment.
