# PQ-01 — Contract Notes for Three Feeds

The official contract file contains rules for four feeds. The playbook asks for notes on at least three; this document records all four to avoid leaving one undocumented.

## Validation policy for schema drift

**Decision: fail the ETL run before overwriting clean outputs if a table has missing or unexpected columns.** The supplied data dictionary is the full schema reference because `data_contracts.csv` specifies only selected feed columns. This is safer than silently ignoring a new column or guessing its meaning. The raw files remain unchanged; inspect `logs/etl_schema_drift.csv` and update the approved dictionary/contract before rerunning.

## Contract coverage limitation

The 42 official contract rows cover four feeds, not every column in every fact table. The ETL applies those explicit rules and uses the full `data_dictionary.csv` for schema and type checks on the remaining columns/tables. Rules that require a separate authoritative reference (for example, the published anomaly `reason_code` vocabulary) must not be invented from the current data; the missing reference should be confirmed with the project owner.

## fact_task — Task board (fact_task)

| Column | Type | Nullable? | Rule / allowed values | Meaning |
|---|---|---:|---|---|
| task_id | string | no | unique TASK-nnnnn | Row id |
| team_id | string | no | exists in dim_team | Team |
| sprint_id | string | no | exists in dim_sprint | Sprint |
| assignee_employee_id | string | no | exists in dim_employee | Assignee |
| task_type | string | no | Feature \| Bug \| Chore \| Spike | Type |
| priority | string | no | P1..P4 | Priority |
| story_points | int | no | 1,2,3,5,8,13 | Effort |
| created_date | date | no | <= started_date | Created |
| started_date | date | yes | blank only when To Do | Started |
| due_date | date | no | sprint end date | Due |
| completed_date | date | yes | required when status = Done; >= started_date | Completed |
| status | string | no | Done \| In Progress \| Blocked \| To Do \| Cancelled | Status |
| reopened_count | int | no | >= 0 | Times reopened |

## fact_anomaly — AI anomaly results (fact_anomaly)

| Column | Type | Nullable? | Rule / allowed values | Meaning |
|---|---|---:|---|---|
| result_id | string | no | unique, format AN-nnnn | Row id |
| source_dataset | string | no | attendance_monthly_features \| payroll_monthly_features | Which dataset was scored |
| record_id | string | no | exists in source dataset | Scored record id |
| employee_id | string | no | exists in dim_employee | Employee |
| period | date | no | month end or start date | Period of the record |
| anomaly_score | decimal(4,3) | no | 0 to 1, higher is more unusual | Normalised score |
| flagged | char(1) | no | Y or N | Whether the threshold was crossed |
| reason_code | string | no | one of the published codes | Machine reason |
| reason_text | string | no | plain English | Reason for business users |
| money_at_risk | decimal(14,2) | yes | blank for attendance rows | Estimated money exposure for payroll rows |
| model_version | string | no | semantic version text | Model that produced it |
| scored_at | timestamp | no | UTC | When scored |

## fact_attrition_risk — AI attrition risk (fact_attrition_risk)

| Column | Type | Nullable? | Rule / allowed values | Meaning |
|---|---|---:|---|---|
| prediction_id | string | no | unique AR-nnnn | Row id |
| employee_id | string | no | exists in dim_employee and active | Employee |
| department_id | string | no | exists in dim_department | Department at as-of date |
| as_of_date | date | no | same for the whole batch | Prediction date |
| risk_score_12m | decimal(4,3) | no | 0 to 1 | Probability of leaving within 12 months |
| risk_band | string | no | Low \| Medium \| High | Band: High = top 10%, Medium = next 20% |
| top_reason_1..3 | string | yes | plain English | Main drivers |
| model_version | string | no | text | Model |

## fact_forecast — AI forecast (fact_forecast)

| Column | Type | Nullable? | Rule / allowed values | Meaning |
|---|---|---:|---|---|
| forecast_id | string | no | unique FC-nnnn | Row id |
| metric | string | no | headcount_end \| attrition_rate_monthly_pct | Forecast metric |
| department_id | string | no | dept id or ALL | Scope |
| forecast_month | date | no | first day of month | Forecast month |
| forecast_value | decimal | no | >= 0 | Point forecast |
| lower_80 | decimal | no | <= forecast_value | 80% lower bound |
| upper_80 | decimal | no | >= forecast_value | 80% upper bound |
| method | string | no | text | Method |
| trained_through | string | no | YYYY-MM | Last actual month used |

## Additional schema-only columns

Some workbook export columns are not explicitly listed in the feed contracts (for example, generated date keys and task convenience fields). They remain part of the approved dataset schema and are checked against the data dictionary. Do not treat an absent contract row as permission to drop a column.
