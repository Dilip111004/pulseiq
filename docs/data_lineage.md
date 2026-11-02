# PulseIQ — PQ-19 Analytics API and Data Lineage

## API
- Application: `src/api.py`
- Start locally: `.\.venv\Scripts\python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8000`
- OpenAPI documentation: `http://127.0.0.1:8000/docs`
- Health: `GET /health`
- Metric catalog: `GET /metrics`
- Metric result: `GET /metrics/{metric_id}`

Monthly metrics require `month=YYYY-MM`. M22 requires `sprint_id` because its governed grain is team x sprint.

## Governed metric lineage

| Metric | Source | Calculation | Grain | Owner |
|---|---|---|---|---|
| M01 Headcount | `fact_headcount_monthly.csv`; dictionary also references `dim_employee` | Sum of department month-end headcount values | Department x month, returned as company total | HR Analytics |
| M07 Gross pay | `fact_payroll.csv` | SUM(gross_pay) | Employee x month, returned as company total | Payroll |
| M09 Employer cost | `fact_payroll.csv` | SUM(employer_cost) | Employee x month, returned as company total | Finance |
| M13 Attendance rate | `fact_attendance_monthly.csv` | (SUM(present_days) + 0.5 x SUM(half_days_unpaid)) / SUM(scheduled_days) | Department x month, returned as company ratio | HR Analytics |
| M22 Task completion | `fact_task.csv` | COUNT(status = Done) / COUNT(status != Cancelled) x 100 | Team x sprint, returned for requested sprint | Engineering Ops |

## Data flow

1. Source/clean warehouse CSV tables in `data/clean`.
2. `metric_dictionary.csv` supplies the metric name, business definition, formula, source, grain, owner, unit and caveat.
3. `src/api.py` reads the governed source table and applies the metric calculation.
4. FastAPI returns the value with definition, source, owner, grain, group-size threshold and source freshness date.
5. Dashboard or API consumer reads the documented endpoint.

## Freshness and coverage

The API reports the latest valid date found in the relevant source column at request time. This is a source-file date, not a claim that an automated refresh has run.

Inspected source coverage:
- Headcount: 2020-01-01 to 2026-09-01 (`month_start_date`)
- Payroll: 2025-04-30 to 2026-09-30 (`period_end_date`)
- Attendance: 2025-04-30 to 2026-09-30 (`period_end_date`)
- Tasks: 2025-04-08 to 2026-09-30 (`completed_date`)

## Limitations and controls

- These endpoints return company-level results; no department or individual breakdown is exposed.
- M22 is sprint-based and must not be interpreted as a monthly KPI.
- M13 is returned as a ratio, consistent with the dictionary unit; e.g. 0.95 represents 95%.
- The minimum-group-size rule is checked before returning a metric result.
- The API reads local CSV files. Hosting, authentication, authorization and scheduled hosted refresh are not implemented by this local API.
- M01 is calculated from the monthly headcount fact table's department-level `headcount_end` values. The dictionary's distinct-employee definition references `dim_employee`; validate reconciliation before treating the fact-table aggregate as an independently recomputed distinct count.
