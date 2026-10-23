# PQ-04 â€” Metric Definition Audit

This audit reviews the supplied `metric_dictionary.csv`, confirms one view definition per official metric ID, and records privacy thresholds. Runtime verification has since been completed: all 28 metric views executed successfully, six independent hand-checks matched, and DQ-C14 passed with zero minimum-group-size violations.

| ID | Official metric | SQL view | Official grain | Unit | Minimum group |
|---|---|---|---|---|---:|
| M01 | Headcount | metrics.m01_headcount | Department x month | count | 5 |
| M02 | Hires | metrics.m02_hires | Department x month | count | 5 |
| M03 | Exits | metrics.m03_exits | Department x month | count | 5 |
| M04 | Attrition rate (monthly) | metrics.m04_attrition_rate_monthly | Department x month | percent | 10 |
| M05 | Attrition rate (rolling 12 months) | metrics.m05_attrition_rate_rolling_12m | Department x month | percent | 10 |
| M06 | Voluntary attrition rate | metrics.m06_voluntary_attrition_rate | Department x month | percent | 10 |
| M07 | Gross pay | metrics.m07_gross_pay | Employee x month | INR | 5 |
| M08 | Net pay | metrics.m08_net_pay | Employee x month | INR | 5 |
| M09 | Payroll cost (employer cost) | metrics.m09_employer_cost | Employee x month | INR | 5 |
| M10 | Cost per head | metrics.m10_cost_per_head | Department x month | INR | 5 |
| M11 | Overtime share | metrics.m11_overtime_share | Department x month | percent | 5 |
| M12 | Variable pay share | metrics.m12_variable_pay_share | Department x month | percent | 5 |
| M13 | Attendance rate | metrics.m13_attendance_rate | Department x month | ratio | 5 |
| M14 | Late arrival rate | metrics.m14_late_arrival_rate | Department x month | ratio | 5 |
| M15 | Leave without pay days | metrics.m15_leave_without_pay_days | Employee x month | days | 5 |
| M16 | Revenue | metrics.m16_revenue | Account x month | INR | â€” |
| M17 | Net profit | metrics.m17_net_profit | Month | INR | â€” |
| M18 | Operating margin | metrics.m18_operating_margin | Month | percent | â€” |
| M19 | Payroll as % of revenue | metrics.m19_payroll_as_pct_revenue | Month | percent | â€” |
| M20 | Days sales outstanding (DSO) | metrics.m20_days_sales_outstanding | Month | days | â€” |
| M21 | Overdue receivables | metrics.m21_overdue_receivables | Client x date | INR | â€” |
| M22 | Task completion rate | metrics.m22_task_completion_rate | Team x sprint | percent | 5 tasks |
| M23 | On-time delivery rate | metrics.m23_on_time_delivery_rate | Team x sprint | percent | 5 tasks |
| M24 | Velocity | metrics.m24_velocity | Team x sprint | points | â€” |
| M25 | Average cycle time | metrics.m25_average_cycle_time | Team x sprint | days | 5 tasks |
| M26 | Anomaly flag rate | metrics.m26_anomaly_flag_rate | Source x month | percent | â€” |
| M27 | High-risk share | metrics.m27_high_risk_share | Department | percent | 10 |
| M28 | Forecast error (MAPE) | metrics.m28_forecast_error_mape | Department x month | percent | â€” |

## Findings and decisions

- **28/28 metric views:** all 28 views executed successfully.
- **M01 cross-check:** all 891 department-month rows matched.
- **M19:** uses ledger accounts 5001–5005 for payroll cost. The June 2026 difference remains INR 18,450.00 and is not silently adjusted.
- **Percentage display:** M22, M23, M26 and M27 return fractions from 0 to 1; display as percentages. M13 and M14 remain ratio-formatted.
- **M28:** returns NULL MAPE and a not-yet-measurable status when actual months do not overlap forecast rows.
- **Hand checks:** all six independent calculations matched the metric views.
- **Governance:** `governance.metric_catalog` contains 28 entries with the required metadata fields.
- **Privacy:** DQ-C14 passed with zero minimum-group-size violations.

## Runtime verification results

1. All 28 metric views executed successfully.
2. All six independent hand-checks matched their metric views.
3. The metric catalog contains 28 entries with governance metadata.
4. DQ-C14 passed with zero violations.

**Still pending:** SQL-backed bad-row injection/mutation testing is not confirmed by the available evidence. The June 2026 INR 18,450.00 payroll-to-ledger difference remains unresolved and must not be silently adjusted.

