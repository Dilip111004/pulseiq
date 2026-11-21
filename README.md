# PulseIQ Unified Workforce, Financial and Business Analytics Platform

PulseIQ brings the Phase 1, Phase 2 and Phase 3 dashboards together in one Streamlit application while keeping phase-specific submission evidence organized in separate folders.

## Live Dashboard

[Open PulseIQ Live Dashboard](https://pulseiq-0c9f.onrender.com/)

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

### Phase 1 - Workforce & Headcount
- Workforce & Headcount Dashboard

### Phase 2 - Official Tasks
- PQ-06 Attendance & Leave
- PQ-07 Attrition Analytics
- PQ-08 Team Productivity
- PQ-09 Payroll Cost
- PQ-10 Budget vs Actual
- Custom KPI Builder

### Phase 3 - Money and Insight
- PQ-11 P&L and Expense Analytics
- PQ-12 Invoices, Receivables and Cash Flow
- PQ-13 Cross-Department Impact
- PQ-14 AI Signals
- PQ-15 Executive Scorecard

## Repository structure

```text
pulseiq/
  app.py
  app_phase1_backup.py
  app_phase3.py
  pages/
  phase-1/
  phase-2/
  phase-3/
  data/
  src/
  sql/
  docs/
  outputs/
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

- `app.py` is the unified entry point for Phases 1-3.
- `app_phase1_backup.py` is retained as a backup of the original standalone Phase 1 dashboard.
- `app_phase3.py` is retained as the original Phase 3 entry point; use `app.py` for the unified application.
- Shared data and outputs are not duplicated into the phase folders.
- Do not commit `.venv`, `__pycache__`, generated database files, credentials, secrets, or confidential records.
- Review data privacy and project validation evidence before public deployment.


## Monthly Excel Report

### Environment setup
Run from the repository root:
`powershell -ExecutionPolicy Bypass -File .\scripts\setup_environment.ps1`

### Generate a report manually
Run:
`.\.venv\Scripts\python.exe .\src\build_monthly_report.py --month 2026-09`

Replace `2026-09` with the required month in YYYY-MM format.

Output: `outputs/monthly_reports/PulseIQ_Monthly_Report_YYYY-MM.xlsx`

The workbook contains five sheets: Executive Finance, Workforce Movement, Payroll & Employer Cost, Attendance & Leave, and Department Scorecard.

### Data availability
The builder checks required monthly source metrics and refuses to create an incomplete report when data is missing. The latest common source month is the data coverage cut-off, not an extraction timestamp.

### Automatic monthly report
The Windows Task Scheduler task `PulseIQ Monthly Report Builder` runs `scripts/run_monthly_report.ps1` on the 5th of each month at 07:00. It generates the previous month's report using `.venv`.

Logs are saved in `logs/monthly_report_YYYY-MM.log`. Ensure the project environment is installed before scheduled execution.

## PulseIQ Phase 4 - Authenticated Analytics API

Phase 4 adds a FastAPI service for controlled access to workforce and business metrics.

### Features
- FastAPI analytics API
- Bearer-token authentication
- Role-based access control
- Governed metric access
- Minimum group-size privacy suppression
- Metric definitions and metadata
- Interactive Swagger documentation
- Localhost-only configuration

### Technology
- Python, FastAPI, Uvicorn, Pandas, DuckDB and SQL

### Project Files
- src/api.py - API implementation
- src/auth.py - Authentication and authorization
- tests/test_pq19_api.py - API tests

### Run the API

    .\.venv_day16_test\Scripts\python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8000

### API Documentation
- Swagger UI: http://127.0.0.1:8000/docs
- OpenAPI: http://127.0.0.1:8000/openapi.json

### API Endpoints
| Method | Endpoint | Access |
|---|---|---|
| GET | /health | Public |
| POST | /auth/login | Login |
| GET | /metrics | ADMIN, EXECUTIVE |
| GET | /metrics/{metric_id} | ADMIN, EXECUTIVE; M22 ADMIN only |

### Supported Metrics
- M01, M07, M09, M13 and M22
- EXECUTIVE users cannot access M22.
- M01, M07, M09 and M13 require month=YYYY-MM.
- M22 requires sprint_id.
- Responses include metric value, unit, period, definition, formula, source, owner, minimum group size, population count, source-data date and caveat.

### Authentication
- Token expiry: 1,800 seconds (30 minutes).
- PULSEIQ_AUTH_USERS: user configuration.
- PULSEIQ_TOKEN_SECRET: signing secret, minimum 32 characters.
- Supported roles: ADMIN, EXECUTIVE, HR and MANAGER.
- Never commit real credentials or secrets.

### Privacy and Data Freshness
- Results below the configured minimum group size are suppressed (HTTP 403).
- Invalid minimum-group-size configuration fails closed.
- Unsupported metrics return HTTP 404.
- latest_source_date represents the latest date in source data.
- The API listens on 127.0.0.1.
- Review authentication, privacy and deployment security before public exposure.

### Testing

    .\.venv_day16_test\Scripts\python.exe -m pytest tests/test_pq19_api.py -q

### Repository
https://github.com/Dilip111004/pulseiq