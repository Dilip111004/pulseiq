# PulseIQ Phase 2 — Workforce Analytics & Intelligence (PQ-06 to PQ-10)

**Project:** PulseIQ — Workforce Analytics Platform.\
**Organization:** Fictional Zenith Nova Technologies training environment.\
**Scope:** PQ-06 Attendance and Leave, PQ-07 Attrition Analytics, PQ-08 Team Productivity, PQ-09 Payroll Cost, and PQ-10 Budget vs Actual.

> Verification note: Phase 2 extends the PulseIQ data foundation with interactive workforce analytics dashboards. The implementation includes attendance and leave analysis, attrition analytics, team productivity, payroll cost analysis, and budget-versus-actual reporting. Supporting application code, SQL analysis, and exported outputs are maintained in the repository.

## What is included

- `app.py`: Streamlit application entry point and dashboard navigation.
- `pages/2_Attendance_and_Leave.py`: PQ-06 attendance and leave analytics.
- `pages/3_Attrition_Analytics.py`: PQ-07 employee attrition analysis.
- `pages/4_Team_Productivity.py`: PQ-08 team productivity analysis.
- `pages/5_Payroll_Cost.py`: PQ-09 payroll cost analysis.
- `pages/6_Budget_vs_Actual.py`: PQ-10 budget-versus-actual analysis.
- `sql/04_budget_vs_actual.sql`: budget-versus-actual SQL analysis.
- `outputs/pq10_*.csv`: exported budget-versus-actual analysis evidence.
- `outputs/submission/`: Phase 2 submission documents.

## Run on your computer

Use Python 3.11 or newer. From the project root:

```
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

python -m pip install -r requirements.txt
streamlit run app.py
```

The command starts the Streamlit application locally. Use the application navigation to access the Phase 2 dashboards.

### Expected outputs

- Streamlit application with five workforce analytics dashboards.
- Attendance and leave analysis.
- Employee attrition analysis.
- Team productivity analysis.
- Payroll cost analysis.
- Budget-versus-actual analysis.
- `outputs/pq10_*.csv`: exported budget analysis evidence.
- `outputs/submission/`: final Phase 2 submission artifacts.

## Phase 2 dashboard coverage

### PQ-06 — Attendance and Leave

Interactive analysis of workforce attendance and leave patterns.

### PQ-07 — Attrition Analytics

Analysis of employee attrition patterns and workforce trends.

### PQ-08 — Team Productivity

Team-level productivity analysis and operational comparisons.

### PQ-09 — Payroll Cost

Payroll cost analysis and supporting workforce cost metrics.

### PQ-10 — Budget vs Actual

Comparison of budgeted and actual expenditure using dashboard visualizations and supporting SQL analysis.

## Technology stack

- Python
- Streamlit
- Pandas
- DuckDB
- Plotly
- SQL

## Important design decisions

- Phase 2 is maintained on a separate Git branch so that Phase 1 work on `master` remains unchanged.
- Each dashboard is maintained as a separate Streamlit page.
- SQL analysis is maintained separately under the `sql/` directory.
- Exported analytical outputs are retained under `outputs/`.
- Workforce data represents a fictional training environment.

## Task acceptance checklist

### PQ-06 — Attendance and Leave Analytics

- Attendance dashboard implemented.
- Leave analysis included.
- Dashboard maintained in `pages/2_Attendance_and_Leave.py`.

### PQ-07 — Attrition Analytics

- Attrition dashboard implemented.
- Workforce attrition analysis included.
- Dashboard maintained in `pages/3_Attrition_Analytics.py`.

### PQ-08 — Team Productivity

- Team productivity dashboard implemented.
- Team-level analysis included.
- Dashboard maintained in `pages/4_Team_Productivity.py`.

### PQ-09 — Payroll Cost

- Payroll cost dashboard implemented.
- Supporting analysis maintained in `pages/5_Payroll_Cost.py`.

### PQ-10 — Budget vs Actual

- Budget-versus-actual dashboard implemented.
- SQL analysis maintained in `sql/04_budget_vs_actual.sql`.
- Supporting CSV outputs maintained under `outputs/`.

## Submission

Final Phase 2 report:

`outputs/submission/DataAnalytics_Dilip_Phase2_Report.pdf`

## Repository

- GitHub repository: https://github.com/Dilip111004/pulseiq
- Phase 2 branch: `phase-2-pq13-cross-department-impact-view`
- Phase 2 tag: `phase-2`

## About

**Dilip D**

PulseIQ — Workforce Analytics Platform

---
