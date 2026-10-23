-- PQ-04 Governed Metric Layer
-- All privacy-restricted outputs carry group_size and suppress groups below the
-- official minimum_group_size. Salary-level outputs are aggregated; no employee names are exposed.
CREATE SCHEMA IF NOT EXISTS metrics;
CREATE SCHEMA IF NOT EXISTS governance;

CREATE OR REPLACE VIEW metrics.m01_headcount AS
SELECT CAST(month_start_date AS DATE) AS month_start_date, department_id,
       SUM(headcount_end) AS headcount, SUM(headcount_end) AS group_size
FROM warehouse.fact_headcount_monthly
GROUP BY 1,2
HAVING SUM(headcount_end) >= 5;

CREATE OR REPLACE VIEW metrics.m02_hires AS
SELECT CAST(month_start_date AS DATE) AS month_start_date, department_id,
       SUM(hires) AS hires, SUM(headcount_end) AS group_size
FROM warehouse.fact_headcount_monthly
GROUP BY 1,2
HAVING SUM(headcount_end) >= 5;

CREATE OR REPLACE VIEW metrics.m03_exits AS
SELECT CAST(month_start_date AS DATE) AS month_start_date, department_id,
       SUM(exits) AS exits, SUM(headcount_end) AS group_size
FROM warehouse.fact_headcount_monthly
GROUP BY 1,2
HAVING SUM(headcount_end) >= 5;

CREATE OR REPLACE VIEW metrics.m04_attrition_rate_monthly AS
SELECT CAST(month_start_date AS DATE) AS month_start_date, department_id,
       SUM(exits) AS exits, SUM(headcount_start) AS headcount_start,
       ROUND(100.0 * SUM(exits) / NULLIF(SUM(headcount_start),0), 4) AS attrition_rate_monthly_pct,
       SUM(headcount_start) AS group_size
FROM warehouse.fact_headcount_monthly
GROUP BY 1,2
HAVING SUM(headcount_start) >= 10;

CREATE OR REPLACE VIEW metrics.m05_attrition_rate_rolling_12m AS
WITH w AS (
  SELECT CAST(month_start_date AS DATE) AS month_start_date, department_id,
         exits, headcount_end,
         SUM(exits) OVER (PARTITION BY department_id ORDER BY month_start_date ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) AS exits_12m,
         AVG(headcount_end) OVER (PARTITION BY department_id ORDER BY month_start_date ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) AS avg_headcount_12m,
         COUNT(*) OVER (PARTITION BY department_id ORDER BY month_start_date ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) AS months_in_window
  FROM warehouse.fact_headcount_monthly
)
SELECT month_start_date, department_id, exits_12m, avg_headcount_12m,
       ROUND(100.0 * exits_12m / NULLIF(avg_headcount_12m,0),4) AS attrition_rate_rolling_12m_pct,
       avg_headcount_12m AS group_size
FROM w
WHERE months_in_window = 12 AND avg_headcount_12m >= 10;

CREATE OR REPLACE VIEW metrics.m06_voluntary_attrition_rate AS
WITH w AS (
  SELECT CAST(month_start_date AS DATE) AS month_start_date, department_id,
         SUM(voluntary_exits) OVER (PARTITION BY department_id ORDER BY month_start_date ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) AS voluntary_exits_12m,
         AVG(headcount_end) OVER (PARTITION BY department_id ORDER BY month_start_date ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) AS avg_headcount_12m,
         COUNT(*) OVER (PARTITION BY department_id ORDER BY month_start_date ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) AS months_in_window
  FROM warehouse.fact_headcount_monthly
)
SELECT month_start_date, department_id, voluntary_exits_12m, avg_headcount_12m,
       ROUND(100.0 * voluntary_exits_12m / NULLIF(avg_headcount_12m,0),4) AS voluntary_attrition_rate_pct,
       avg_headcount_12m AS group_size
FROM w
WHERE months_in_window = 12 AND avg_headcount_12m >= 10;

CREATE OR REPLACE VIEW metrics.m07_gross_pay AS
SELECT CAST(period_end_date AS DATE) AS month_end_date, department_id,
       ROUND(SUM(gross_pay),2) AS gross_pay,
       COUNT(DISTINCT employee_id) AS group_size
FROM warehouse.fact_payroll
GROUP BY 1,2
HAVING COUNT(DISTINCT employee_id) >= 5;

CREATE OR REPLACE VIEW metrics.m08_net_pay AS
SELECT CAST(period_end_date AS DATE) AS month_end_date, department_id,
       ROUND(SUM(net_pay),2) AS net_pay,
       COUNT(DISTINCT employee_id) AS group_size
FROM warehouse.fact_payroll
GROUP BY 1,2
HAVING COUNT(DISTINCT employee_id) >= 5;

CREATE OR REPLACE VIEW metrics.m09_employer_cost AS
SELECT CAST(period_end_date AS DATE) AS month_end_date, department_id,
       ROUND(SUM(employer_cost),2) AS employer_cost,
       COUNT(DISTINCT employee_id) AS group_size
FROM warehouse.fact_payroll
GROUP BY 1,2
HAVING COUNT(DISTINCT employee_id) >= 5;

CREATE OR REPLACE VIEW metrics.m10_cost_per_head AS
SELECT CAST(period_end_date AS DATE) AS month_end_date, department_id,
       ROUND(SUM(employer_cost) / NULLIF(COUNT(DISTINCT employee_id),0),2) AS cost_per_head,
       COUNT(DISTINCT employee_id) AS group_size
FROM warehouse.fact_payroll
GROUP BY 1,2
HAVING COUNT(DISTINCT employee_id) >= 5;

CREATE OR REPLACE VIEW metrics.m11_overtime_share AS
SELECT CAST(period_end_date AS DATE) AS month_end_date, department_id,
       ROUND(100.0 * SUM(overtime_pay) / NULLIF(SUM(employer_cost),0),4) AS overtime_share_pct,
       COUNT(DISTINCT employee_id) AS group_size
FROM warehouse.fact_payroll
GROUP BY 1,2
HAVING COUNT(DISTINCT employee_id) >= 5;

CREATE OR REPLACE VIEW metrics.m12_variable_pay_share AS
SELECT CAST(period_end_date AS DATE) AS month_end_date, department_id,
       ROUND(100.0 * SUM(variable_pay) / NULLIF(SUM(gross_pay),0),4) AS variable_pay_share_pct,
       COUNT(DISTINCT employee_id) AS group_size
FROM warehouse.fact_payroll
GROUP BY 1,2
HAVING COUNT(DISTINCT employee_id) >= 5;

CREATE OR REPLACE VIEW metrics.m13_attendance_rate AS
SELECT CAST(period_end_date AS DATE) AS month_end_date, department_id,
       (SUM(present_days) + 0.5 * SUM(half_days_unpaid)) / NULLIF(SUM(scheduled_days),0) AS attendance_rate,
       COUNT(DISTINCT employee_id) AS group_size
FROM warehouse.fact_attendance_monthly
GROUP BY 1,2
HAVING COUNT(DISTINCT employee_id) >= 5;

CREATE OR REPLACE VIEW metrics.m14_late_arrival_rate AS
SELECT CAST(period_end_date AS DATE) AS month_end_date, department_id,
       SUM(late_arrivals) / NULLIF(SUM(present_days),0) AS late_arrivals_per_present_day,
       COUNT(DISTINCT employee_id) AS group_size
FROM warehouse.fact_attendance_monthly
GROUP BY 1,2
HAVING COUNT(DISTINCT employee_id) >= 5;

CREATE OR REPLACE VIEW metrics.m15_leave_without_pay_days AS
SELECT CAST(period_end_date AS DATE) AS month_end_date, department_id,
       SUM(lop_days) AS leave_without_pay_days,
       COUNT(DISTINCT employee_id) AS group_size
FROM warehouse.fact_payroll
GROUP BY 1,2
HAVING COUNT(DISTINCT employee_id) >= 5;

CREATE OR REPLACE VIEW metrics.m16_revenue AS
SELECT CAST(CAST(l.posting_period AS VARCHAR) || '-01' AS DATE) AS month_start_date,
       COALESCE(l.cost_center_department_id,'ALL') AS department_id,
       l.account_code,
       ROUND(-SUM(l.signed_amount_debit_positive),2) AS revenue
FROM warehouse.fact_ledger l
WHERE CAST(l.account_code AS VARCHAR) IN ('4001','4002','4003','4004')
GROUP BY 1,2,3;

CREATE OR REPLACE VIEW metrics.m17_net_profit AS
SELECT CAST(CAST(posting_period AS VARCHAR) || '-01' AS DATE) AS month_start_date, 'ALL' AS department_id,
       ROUND(-SUM(signed_amount_debit_positive),2) AS net_profit
FROM warehouse.fact_ledger
WHERE CAST(account_code AS VARCHAR) LIKE '4%' OR CAST(account_code AS VARCHAR) LIKE '5%'
GROUP BY 1;

CREATE OR REPLACE VIEW metrics.m18_operating_margin AS
WITH rev AS (
 SELECT posting_period, -SUM(signed_amount_debit_positive) AS revenue
 FROM warehouse.fact_ledger
 WHERE CAST(account_code AS VARCHAR) IN ('4001','4002','4003','4004')
 GROUP BY 1
), profit AS (
 SELECT posting_period, -SUM(signed_amount_debit_positive) AS net_profit
 FROM warehouse.fact_ledger
 WHERE CAST(account_code AS VARCHAR) LIKE '4%' OR CAST(account_code AS VARCHAR) LIKE '5%'
 GROUP BY 1
)
SELECT CAST(CAST(p.posting_period AS VARCHAR) || '-01' AS DATE) AS month_start_date, 'ALL' AS department_id,
       p.net_profit, r.revenue,
       ROUND(100.0 * p.net_profit / NULLIF(r.revenue,0),4) AS operating_margin_pct
FROM profit p LEFT JOIN rev r USING(posting_period);

CREATE OR REPLACE VIEW metrics.m19_payroll_as_pct_revenue AS
-- The official metric caveat explicitly requires ledger payroll accounts 5001–5005
-- for the numerator, avoiding a false pass when payroll and ledger disagree.
WITH ledger_payroll AS (
 SELECT CAST(posting_period AS VARCHAR) AS month_key,
        SUM(signed_amount_debit_positive) AS payroll_cost_ledger
 FROM warehouse.fact_ledger
 WHERE CAST(account_code AS VARCHAR) IN ('5001','5002','5003','5004','5005')
 GROUP BY 1
), payroll_source AS (
 SELECT STRFTIME(CAST(period_end_date AS DATE),'%Y-%m') AS month_key,
        SUM(employer_cost) AS payroll_cost_fact
 FROM warehouse.fact_payroll
 GROUP BY 1
), revenue AS (
 SELECT CAST(posting_period AS VARCHAR) AS month_key,
        -SUM(signed_amount_debit_positive) AS revenue
 FROM warehouse.fact_ledger
 WHERE CAST(account_code AS VARCHAR) IN ('4001','4002','4003','4004')
 GROUP BY 1
)
SELECT CAST(lp.month_key || '-01' AS DATE) AS month_start_date,
       'ALL' AS department_id,
       lp.payroll_cost_ledger,
       ps.payroll_cost_fact,
       r.revenue,
       ROUND(100.0 * lp.payroll_cost_ledger / NULLIF(r.revenue,0),4) AS payroll_pct_revenue,
       ROUND(lp.payroll_cost_ledger - ps.payroll_cost_fact,2) AS ledger_vs_payroll_difference
FROM ledger_payroll lp
LEFT JOIN payroll_source ps USING(month_key)
LEFT JOIN revenue r USING(month_key);

CREATE OR REPLACE VIEW metrics.m20_days_sales_outstanding AS
WITH months AS (
 SELECT DISTINCT CAST(month_end_date AS DATE) AS report_date
 FROM warehouse.dim_date
 WHERE CAST(is_month_end AS VARCHAR) = 'Y'
   AND CAST(month_end_date AS DATE) <= (SELECT MAX(CAST(period_end_date AS DATE)) FROM warehouse.fact_payroll)
), receivables AS (
 SELECT m.report_date,
        SUM(CASE WHEN CAST(i.invoice_date AS DATE) <= m.report_date
                      AND CAST(i.status AS VARCHAR) NOT IN ('DRAFT','CANCELLED')
                 THEN GREATEST(0, i.total_amount - COALESCE((
                    SELECT SUM(pay.amount) FROM warehouse.fact_invoice_payment pay
                    WHERE pay.invoice_id=i.invoice_id AND CAST(pay.payment_date AS DATE)<=m.report_date
                 ),0)) ELSE 0 END) AS closing_receivables,
        SUM(CASE WHEN CAST(i.invoice_date AS DATE) > m.report_date - INTERVAL 90 DAY
                      AND CAST(i.invoice_date AS DATE) <= m.report_date
                 THEN i.total_amount ELSE 0 END) AS sales_90d
 FROM months m CROSS JOIN warehouse.fact_invoice i
 GROUP BY m.report_date
)
SELECT report_date AS month_end_date, 'ALL' AS department_id, closing_receivables, sales_90d,
       90.0 * closing_receivables / NULLIF(sales_90d,0) AS dso_days
FROM receivables;

CREATE OR REPLACE VIEW metrics.m21_overdue_receivables AS
WITH cutoff AS (SELECT MAX(CAST(period_end_date AS DATE)) AS report_date FROM warehouse.fact_payroll)
SELECT c.report_date, i.client_id, 'ALL' AS department_id,
       ROUND(SUM(i.balance_due),2) AS overdue_receivables
FROM warehouse.fact_invoice i CROSS JOIN cutoff c
WHERE CAST(i.due_date AS DATE) < c.report_date
  AND CAST(i.status AS VARCHAR) NOT IN ('DRAFT','CANCELLED')
  AND i.balance_due > 0
GROUP BY 1,2;

CREATE OR REPLACE VIEW metrics.m22_task_completion_rate AS
SELECT s.sprint_id, t.team_id,
       COUNT(*) FILTER (WHERE t.status='Done') * 1.0 /
       NULLIF(COUNT(*) FILTER (WHERE t.status <> 'Cancelled'),0) AS task_completion_rate,
       COUNT(*) FILTER (WHERE t.status <> 'Cancelled') AS group_size
FROM warehouse.fact_task t
JOIN warehouse.dim_sprint s USING(sprint_id)
GROUP BY 1,2
HAVING COUNT(*) FILTER (WHERE t.status <> 'Cancelled') >= 5;

CREATE OR REPLACE VIEW metrics.m23_on_time_delivery_rate AS
SELECT t.sprint_id, t.team_id,
       COUNT(*) FILTER (WHERE t.status='Done' AND t.completed_on_time='Y') * 1.0 /
       NULLIF(COUNT(*) FILTER (WHERE t.status='Done'),0) AS on_time_delivery_rate,
       COUNT(*) FILTER (WHERE t.status <> 'Cancelled') AS group_size
FROM warehouse.fact_task t
GROUP BY 1,2
HAVING COUNT(*) FILTER (WHERE t.status <> 'Cancelled') >= 5;

CREATE OR REPLACE VIEW metrics.m24_velocity AS
SELECT sprint_id, team_id, SUM(story_points) FILTER (WHERE status='Done') AS velocity_story_points
FROM warehouse.fact_task
GROUP BY 1,2;

CREATE OR REPLACE VIEW metrics.m25_average_cycle_time AS
SELECT sprint_id, team_id,
       AVG(DATE_DIFF('day', CAST(started_date AS DATE), CAST(completed_date AS DATE))) AS average_cycle_time_days,
       COUNT(*) FILTER (WHERE status='Done') AS group_size
FROM warehouse.fact_task
WHERE status='Done' AND started_date IS NOT NULL AND completed_date IS NOT NULL
GROUP BY 1,2
HAVING COUNT(*) FILTER (WHERE status='Done') >= 5;

CREATE OR REPLACE VIEW metrics.m26_anomaly_flag_rate AS
SELECT CAST(DATE_TRUNC('month',CAST(period AS DATE)) AS DATE) AS month_start_date,
       source_dataset, 'ALL' AS department_id,
       COUNT(*) AS scored_records,
       COUNT(*) FILTER (WHERE flagged='Y') AS flagged_records,
       COUNT(*) FILTER (WHERE flagged='Y') * 1.0 / NULLIF(COUNT(*),0) AS anomaly_flag_rate
FROM warehouse.fact_anomaly
GROUP BY 1,2;

CREATE OR REPLACE VIEW metrics.m27_high_risk_share AS
SELECT CAST(as_of_date AS DATE) AS as_of_date, department_id,
       COUNT(*) FILTER (WHERE risk_band='High') * 1.0 / NULLIF(COUNT(*),0) AS high_risk_share,
       COUNT(DISTINCT employee_id) AS group_size
FROM warehouse.fact_attrition_risk
GROUP BY 1,2
HAVING COUNT(DISTINCT employee_id) >= 10;

-- The supplied forecast horizon begins after the last actual month. Return forecast rows
-- with an explicit NULL MAPE/status until an actual period exists; never fabricate error.
CREATE OR REPLACE VIEW metrics.m28_forecast_error_mape AS
WITH f AS (
 SELECT forecast_month, department_id, forecast_value
 FROM warehouse.fact_forecast WHERE metric='headcount_end'
), a AS (
 SELECT CAST(month_start_date AS DATE) AS actual_month, department_id, headcount_end AS actual_value
 FROM warehouse.fact_headcount_monthly
)
SELECT f.forecast_month AS month_start_date, f.department_id, f.forecast_value,
       a.actual_value,
       CASE WHEN a.actual_value IS NULL OR a.actual_value=0 THEN NULL
            ELSE ABS(a.actual_value-f.forecast_value)/a.actual_value*100 END AS mape_pct,
       CASE WHEN a.actual_value IS NULL THEN 'NOT_YET_MEASURABLE_NO_OVERLAPPING_ACTUALS'
            WHEN a.actual_value=0 THEN 'NOT_MEASURABLE_ZERO_ACTUAL'
            ELSE 'MEASURED' END AS measurement_status
FROM f LEFT JOIN a ON f.forecast_month=a.actual_month AND f.department_id=a.department_id;

CREATE OR REPLACE VIEW governance.metric_catalog AS
SELECT metric_id, metric_name, business_definition, formula, source_table, grain,
       time_period, owner_team, unit, minimum_group_size, caveat
FROM governance.metric_dictionary;
