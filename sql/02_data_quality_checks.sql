-- PQ-03 Data Quality Gatekeeper
-- Run after src/build_warehouse.py and sql/03_metric_views.sql.
-- Checks inspect raw source data so ETL quarantine does not hide the original defects.
CREATE SCHEMA IF NOT EXISTS dq;

CREATE OR REPLACE VIEW dq.v_min_group_size_violations AS
SELECT 'M01' AS metric_id, CAST(month_start_date AS VARCHAR) AS period_key, department_id, group_size
FROM metrics.m01_headcount WHERE group_size < 5
UNION ALL SELECT 'M02', CAST(month_start_date AS VARCHAR), department_id, group_size
FROM metrics.m02_hires WHERE group_size < 5
UNION ALL SELECT 'M03', CAST(month_start_date AS VARCHAR), department_id, group_size
FROM metrics.m03_exits WHERE group_size < 5
UNION ALL SELECT 'M04', CAST(month_start_date AS VARCHAR), department_id, group_size
FROM metrics.m04_attrition_rate_monthly WHERE group_size < 10
UNION ALL SELECT 'M05', CAST(month_start_date AS VARCHAR), department_id, group_size
FROM metrics.m05_attrition_rate_rolling_12m WHERE group_size < 10
UNION ALL SELECT 'M06', CAST(month_start_date AS VARCHAR), department_id, group_size
FROM metrics.m06_voluntary_attrition_rate WHERE group_size < 10
UNION ALL SELECT 'M07', CAST(month_end_date AS VARCHAR), department_id, group_size
FROM metrics.m07_gross_pay WHERE group_size < 5
UNION ALL SELECT 'M08', CAST(month_end_date AS VARCHAR), department_id, group_size
FROM metrics.m08_net_pay WHERE group_size < 5
UNION ALL SELECT 'M09', CAST(month_end_date AS VARCHAR), department_id, group_size
FROM metrics.m09_employer_cost WHERE group_size < 5
UNION ALL SELECT 'M10', CAST(month_end_date AS VARCHAR), department_id, group_size
FROM metrics.m10_cost_per_head WHERE group_size < 5
UNION ALL SELECT 'M11', CAST(month_end_date AS VARCHAR), department_id, group_size
FROM metrics.m11_overtime_share WHERE group_size < 5
UNION ALL SELECT 'M12', CAST(month_end_date AS VARCHAR), department_id, group_size
FROM metrics.m12_variable_pay_share WHERE group_size < 5
UNION ALL SELECT 'M13', CAST(month_end_date AS VARCHAR), department_id, group_size
FROM metrics.m13_attendance_rate WHERE group_size < 5
UNION ALL SELECT 'M14', CAST(month_end_date AS VARCHAR), department_id, group_size
FROM metrics.m14_late_arrival_rate WHERE group_size < 5
UNION ALL SELECT 'M15', CAST(month_end_date AS VARCHAR), department_id, group_size
FROM metrics.m15_leave_without_pay_days WHERE group_size < 5
UNION ALL SELECT 'M22', sprint_id, team_id, group_size
FROM metrics.m22_task_completion_rate WHERE group_size < 5
UNION ALL SELECT 'M23', sprint_id, team_id, group_size
FROM metrics.m23_on_time_delivery_rate WHERE group_size < 5
UNION ALL SELECT 'M25', sprint_id, team_id, group_size
FROM metrics.m25_average_cycle_time WHERE group_size < 5
UNION ALL SELECT 'M27', CAST(as_of_date AS VARCHAR), department_id, group_size
FROM metrics.m27_high_risk_share WHERE group_size < 10;

CREATE OR REPLACE VIEW dq.v_check_results AS
WITH
c01 AS (
 SELECT COUNT(*) AS n FROM (
  SELECT COALESCE(p.month_key,l.month_key) AS month_key,
         COALESCE(p.payroll_cost,0)-COALESCE(l.ledger_cost,0) AS diff
  FROM (
   SELECT STRFTIME(CAST(period_end_date AS DATE),'%Y-%m') AS month_key, SUM(employer_cost) AS payroll_cost
   FROM raw.fact_payroll GROUP BY 1
  ) p FULL OUTER JOIN (
   SELECT posting_period AS month_key, SUM(signed_amount_debit_positive) AS ledger_cost
   FROM raw.fact_ledger WHERE CAST(account_code AS VARCHAR) IN ('5001','5002','5003','5004','5005')
   GROUP BY 1
  ) l USING(month_key)
 ) q WHERE ABS(diff) > 0.01
),
c02 AS (
 SELECT COUNT(*) AS n FROM (
  SELECT entry_id FROM raw.fact_ledger GROUP BY entry_id
  HAVING ABS(SUM(debit)-SUM(credit)) > 0.005
 ) q
),
c03 AS (
 SELECT COALESCE(SUM(cnt),0) AS n FROM (
  SELECT COUNT(*) AS cnt FROM raw.fact_payroll GROUP BY employee_id,run_id HAVING COUNT(*)>1
 ) q
),
c04 AS (
 SELECT
   (SELECT COUNT(*) FROM raw.fact_payroll f WHERE NOT EXISTS (SELECT 1 FROM raw.dim_employee d WHERE d.employee_id=f.employee_id)) +
   (SELECT COUNT(*) FROM raw.fact_attendance_monthly f WHERE NOT EXISTS (SELECT 1 FROM raw.dim_employee d WHERE d.employee_id=f.employee_id)) +
   (SELECT COUNT(*) FROM raw.fact_leave f WHERE NOT EXISTS (SELECT 1 FROM raw.dim_employee d WHERE d.employee_id=f.employee_id)) +
   (SELECT COUNT(*) FROM raw.fact_anomaly f WHERE NOT EXISTS (SELECT 1 FROM raw.dim_employee d WHERE d.employee_id=f.employee_id)) +
   (SELECT COUNT(*) FROM raw.fact_attrition_risk f WHERE NOT EXISTS (SELECT 1 FROM raw.dim_employee d WHERE d.employee_id=f.employee_id)) +
   (SELECT COUNT(*) FROM raw.fact_task f WHERE NOT EXISTS (SELECT 1 FROM raw.dim_employee d WHERE d.employee_id=f.assignee_employee_id)) AS n
),
c05 AS (
 SELECT COUNT(*) AS n
 FROM raw.fact_attendance_monthly a
 JOIN raw.dim_employee d ON a.employee_id=d.employee_id AND d.is_current='Y'
 WHERE d.exit_date IS NOT NULL
   AND DATE_TRUNC('month',CAST(a.period_end_date AS DATE)) > DATE_TRUNC('month',CAST(d.exit_date AS DATE))
),
c06 AS (
 SELECT COUNT(*) AS n FROM (
  SELECT a.employee_id, STRFTIME(CAST(a.period_end_date AS DATE),'%Y-%m') AS month_key,
         SUM(a.unpaid_absence_days) AS unpaid_days, COALESCE(MAX(p.lop_days),0) AS lop_days
  FROM raw.fact_attendance_monthly a
  LEFT JOIN (
    SELECT employee_id, STRFTIME(CAST(period_end_date AS DATE),'%Y-%m') AS month_key, SUM(lop_days) AS lop_days
    FROM raw.fact_payroll GROUP BY 1,2
  ) p ON p.employee_id=a.employee_id AND p.month_key=STRFTIME(CAST(a.period_end_date AS DATE),'%Y-%m')
  GROUP BY 1,2
 ) q WHERE unpaid_days > lop_days + 0.5
),
c07 AS (
 SELECT COUNT(*) AS n FROM raw.fact_invoice WHERE amount_paid > total_amount + 0.01 OR balance_due < -0.01
),
c08 AS (
 SELECT COUNT(*) AS n FROM raw.fact_expense WHERE ABS(total_amount-(amount_excl_gst+gst_amount)) > 0.01
),
c09 AS (
 SELECT COUNT(*) AS n FROM raw.fact_task
 WHERE (completed_date IS NOT NULL AND started_date IS NOT NULL AND CAST(completed_date AS DATE)<CAST(started_date AS DATE))
    OR (status='Done' AND completed_date IS NULL)
),
c10 AS (
 SELECT COUNT(*) AS n FROM raw.fact_leave WHERE CAST(end_date AS DATE)<CAST(start_date AS DATE)
),
c11 AS (
 SELECT
  (SELECT COUNT(*) FROM raw.fact_attrition_risk
   WHERE CAST(as_of_date AS DATE) < (SELECT MAX(CAST(as_of_date AS DATE)) FROM raw.fact_attrition_risk) - INTERVAL 7 DAY)
  +
  (SELECT COUNT(*) FROM raw.fact_anomaly
   WHERE scored_at IS NULL OR CAST(scored_at AS TIMESTAMP) < CURRENT_TIMESTAMP - INTERVAL 24 HOUR) AS n
),
c12 AS (
 SELECT COUNT(DISTINCT b.employee_key) AS n
 FROM raw.dim_employee a
 JOIN raw.dim_employee b ON a.employee_id=b.employee_id AND a.employee_key < b.employee_key
  AND CAST(a.valid_from AS DATE) <= CAST(b.valid_to AS DATE)
  AND CAST(b.valid_from AS DATE) <= CAST(a.valid_to AS DATE)
),
c13 AS (
 SELECT CASE WHEN MAX(CAST(finished_at AS TIMESTAMPTZ)) >= CURRENT_TIMESTAMP - INTERVAL 24 HOUR THEN 0 ELSE 1 END AS n
 FROM dq.etl_run_log WHERE status='SUCCESS'
),
c14 AS (
 SELECT COUNT(*) AS n FROM dq.v_min_group_size_violations
)
SELECT 'DQ-C01' AS check_id,'Payroll equals ledger' AS check_name,'fact_payroll + fact_ledger' AS table_name,'Critical' AS severity,
       CASE WHEN n=0 THEN 'PASS' ELSE 'FAIL' END AS status,n AS bad_row_count,CURRENT_TIMESTAMP AS run_at,
       'Monthly employer cost vs ledger accounts 5001–5005; tolerance INR 0.01' AS detail FROM c01
UNION ALL SELECT 'DQ-C02','Ledger balanced','fact_ledger','Critical',CASE WHEN n=0 THEN 'PASS' ELSE 'FAIL' END,n,CURRENT_TIMESTAMP,
       'Debit and credit totals per journal entry differ by no more than INR 0.005' FROM c02
UNION ALL SELECT 'DQ-C03','Unique payroll rows','fact_payroll','Critical',CASE WHEN n=0 THEN 'PASS' ELSE 'FAIL' END,n,CURRENT_TIMESTAMP,
       'Rows belonging to duplicate employee_id/run_id groups' FROM c03
UNION ALL SELECT 'DQ-C04','No orphan employees','employee-bearing fact tables','Critical',CASE WHEN n=0 THEN 'PASS' ELSE 'FAIL' END,n,CURRENT_TIMESTAMP,
       'Across payroll, attendance, leave, anomaly, attrition-risk and task assignee feeds' FROM c04
UNION ALL SELECT 'DQ-C05','No attendance after exit','fact_attendance_monthly','Warning',CASE WHEN n=0 THEN 'PASS' ELSE 'FAIL' END,n,CURRENT_TIMESTAMP,
       'Attendance month must not be after employee exit month' FROM c05
UNION ALL SELECT 'DQ-C06','Unpaid leave deducted','fact_attendance_monthly + fact_payroll','Warning',CASE WHEN n=0 THEN 'PASS' ELSE 'FAIL' END,n,CURRENT_TIMESTAMP,
       'Unpaid absence days must be reflected in payroll LOP within 0.5-day tolerance' FROM c06
UNION ALL SELECT 'DQ-C07','Invoice arithmetic','fact_invoice','Warning',CASE WHEN n=0 THEN 'PASS' ELSE 'FAIL' END,n,CURRENT_TIMESTAMP,
       'Paid amount cannot exceed invoice total; balance due cannot be negative' FROM c07
UNION ALL SELECT 'DQ-C08','Expense arithmetic','fact_expense','Warning',CASE WHEN n=0 THEN 'PASS' ELSE 'FAIL' END,n,CURRENT_TIMESTAMP,
       'Total must equal amount excluding GST plus GST within INR 0.01' FROM c08
UNION ALL SELECT 'DQ-C09','Task dates sensible','fact_task','Warning',CASE WHEN n=0 THEN 'PASS' ELSE 'FAIL' END,n,CURRENT_TIMESTAMP,
       'Done tasks need completion dates; completion cannot precede start' FROM c09
UNION ALL SELECT 'DQ-C10','Leave dates sensible','fact_leave','Warning',CASE WHEN n=0 THEN 'PASS' ELSE 'FAIL' END,n,CURRENT_TIMESTAMP,
       'Leave end date must not precede leave start date' FROM c10
UNION ALL SELECT 'DQ-C11','AI feeds are fresh','fact_attrition_risk + fact_anomaly','Warning',CASE WHEN n=0 THEN 'PASS' ELSE 'FAIL' END,n,CURRENT_TIMESTAMP,
       'Stale prediction batch plus anomaly scores older than 24 hours at runtime' FROM c11
UNION ALL SELECT 'DQ-C12','Dimension history does not overlap','dim_employee','Critical',CASE WHEN n=0 THEN 'PASS' ELSE 'FAIL' END,n,CURRENT_TIMESTAMP,
       'SCD2 employee validity intervals must not overlap' FROM c12
UNION ALL SELECT 'DQ-C13','Pipeline freshness','dq.etl_run_log','Critical',CASE WHEN n=0 THEN 'PASS' ELSE 'FAIL' END,n,CURRENT_TIMESTAMP,
       'Latest successful ETL run must finish within 24 hours' FROM c13
UNION ALL SELECT 'DQ-C14','Minimum group size','metrics.* restricted views','Critical',CASE WHEN n=0 THEN 'PASS' ELSE 'FAIL' END,n,CURRENT_TIMESTAMP,
       'No restricted metric view may expose a group below its dictionary threshold' FROM c14;

-- Standardized row-level evidence: each row identifies the check, source table, source key and failure detail.
CREATE OR REPLACE VIEW dq.v_bad_rows AS
WITH payroll_month AS (
 SELECT STRFTIME(CAST(period_end_date AS DATE),'%Y-%m') AS month_key, SUM(employer_cost) AS payroll_cost
 FROM raw.fact_payroll GROUP BY 1
), ledger_month AS (
 SELECT posting_period AS month_key, SUM(signed_amount_debit_positive) AS ledger_cost
 FROM raw.fact_ledger WHERE CAST(account_code AS VARCHAR) IN ('5001','5002','5003','5004','5005') GROUP BY 1
), c01 AS (
 SELECT COALESCE(p.month_key,l.month_key) AS row_key,
        COALESCE(p.payroll_cost,0)-COALESCE(l.ledger_cost,0) AS diff
 FROM payroll_month p FULL OUTER JOIN ledger_month l USING(month_key)
 WHERE ABS(COALESCE(p.payroll_cost,0)-COALESCE(l.ledger_cost,0)) > 0.01
), c06 AS (
 SELECT a.employee_id || '|' || STRFTIME(CAST(a.period_end_date AS DATE),'%Y-%m') AS row_key,
        SUM(a.unpaid_absence_days) AS unpaid_days, COALESCE(MAX(p.lop_days),0) AS lop_days
 FROM raw.fact_attendance_monthly a
 LEFT JOIN (SELECT employee_id, STRFTIME(CAST(period_end_date AS DATE),'%Y-%m') AS month_key, SUM(lop_days) AS lop_days
            FROM raw.fact_payroll GROUP BY 1,2) p
   ON p.employee_id=a.employee_id AND p.month_key=STRFTIME(CAST(a.period_end_date AS DATE),'%Y-%m')
 GROUP BY 1
 HAVING SUM(a.unpaid_absence_days) > COALESCE(MAX(p.lop_days),0) + 0.5
), c12 AS (
 SELECT CAST(b.employee_key AS VARCHAR) AS row_key,
        'employee_id=' || CAST(a.employee_id AS VARCHAR) || '; validity intervals overlap' AS detail
 FROM raw.dim_employee a JOIN raw.dim_employee b
   ON a.employee_id=b.employee_id AND a.employee_key < b.employee_key
  AND CAST(a.valid_from AS DATE) <= CAST(b.valid_to AS DATE)
  AND CAST(b.valid_from AS DATE) <= CAST(a.valid_to AS DATE)
)
SELECT 'DQ-C01' AS check_id,'fact_payroll + fact_ledger' AS table_name,CAST(row_key AS VARCHAR) AS row_key,
       'Monthly payroll-ledger difference=' || CAST(ROUND(diff,2) AS VARCHAR) AS detail FROM c01
UNION ALL SELECT 'DQ-C02','fact_ledger',CAST(entry_id AS VARCHAR),
       'debit=' || CAST(SUM(debit) AS VARCHAR) || '; credit=' || CAST(SUM(credit) AS VARCHAR)
FROM raw.fact_ledger GROUP BY entry_id HAVING ABS(SUM(debit)-SUM(credit)) > 0.005
UNION ALL SELECT 'DQ-C03','fact_payroll',CAST(employee_id AS VARCHAR) || '|' || CAST(run_id AS VARCHAR),
       'duplicate employee_id/run_id group count=' || CAST(COUNT(*) AS VARCHAR)
FROM raw.fact_payroll GROUP BY employee_id,run_id HAVING COUNT(*) > 1
UNION ALL SELECT 'DQ-C04','fact_payroll',CAST(f.employee_id AS VARCHAR),'employee_id missing from dim_employee'
FROM raw.fact_payroll f WHERE NOT EXISTS (SELECT 1 FROM raw.dim_employee d WHERE d.employee_id=f.employee_id)
UNION ALL SELECT 'DQ-C04','fact_attendance_monthly',CAST(f.attendance_fact_id AS VARCHAR),'employee_id missing from dim_employee'
FROM raw.fact_attendance_monthly f WHERE NOT EXISTS (SELECT 1 FROM raw.dim_employee d WHERE d.employee_id=f.employee_id)
UNION ALL SELECT 'DQ-C04','fact_leave',CAST(f.leave_request_id AS VARCHAR),'employee_id missing from dim_employee'
FROM raw.fact_leave f WHERE NOT EXISTS (SELECT 1 FROM raw.dim_employee d WHERE d.employee_id=f.employee_id)
UNION ALL SELECT 'DQ-C04','fact_anomaly',CAST(f.result_id AS VARCHAR),'employee_id missing from dim_employee'
FROM raw.fact_anomaly f WHERE NOT EXISTS (SELECT 1 FROM raw.dim_employee d WHERE d.employee_id=f.employee_id)
UNION ALL SELECT 'DQ-C04','fact_attrition_risk',CAST(f.prediction_id AS VARCHAR),'employee_id missing from dim_employee'
FROM raw.fact_attrition_risk f WHERE NOT EXISTS (SELECT 1 FROM raw.dim_employee d WHERE d.employee_id=f.employee_id)
UNION ALL SELECT 'DQ-C04','fact_task',CAST(f.task_id AS VARCHAR),'assignee_employee_id missing from dim_employee'
FROM raw.fact_task f WHERE NOT EXISTS (SELECT 1 FROM raw.dim_employee d WHERE d.employee_id=f.assignee_employee_id)
UNION ALL SELECT 'DQ-C05','fact_attendance_monthly',CAST(a.attendance_fact_id AS VARCHAR),
       'attendance month after employee exit month'
FROM raw.fact_attendance_monthly a JOIN raw.dim_employee d ON a.employee_id=d.employee_id AND d.is_current='Y'
WHERE d.exit_date IS NOT NULL AND DATE_TRUNC('month',CAST(a.period_end_date AS DATE)) > DATE_TRUNC('month',CAST(d.exit_date AS DATE))
UNION ALL SELECT 'DQ-C06','fact_attendance_monthly + fact_payroll',row_key,
       'unpaid_absence_days=' || CAST(unpaid_days AS VARCHAR) || '; lop_days=' || CAST(lop_days AS VARCHAR) FROM c06
UNION ALL SELECT 'DQ-C07','fact_invoice',CAST(invoice_id AS VARCHAR),'invoice paid exceeds total or balance_due is negative'
FROM raw.fact_invoice WHERE amount_paid > total_amount + 0.01 OR balance_due < -0.01
UNION ALL SELECT 'DQ-C08','fact_expense',CAST(expense_id AS VARCHAR),'total_amount differs from amount_excl_gst + gst_amount'
FROM raw.fact_expense WHERE ABS(total_amount-(amount_excl_gst+gst_amount)) > 0.01
UNION ALL SELECT 'DQ-C09','fact_task',CAST(task_id AS VARCHAR),'invalid task completion dates/status'
FROM raw.fact_task WHERE (completed_date IS NOT NULL AND started_date IS NOT NULL AND CAST(completed_date AS DATE)<CAST(started_date AS DATE))
 OR (status='Done' AND completed_date IS NULL)
UNION ALL SELECT 'DQ-C10','fact_leave',CAST(leave_request_id AS VARCHAR),'end_date precedes start_date'
FROM raw.fact_leave WHERE CAST(end_date AS DATE)<CAST(start_date AS DATE)
UNION ALL SELECT 'DQ-C11','fact_attrition_risk',CAST(prediction_id AS VARCHAR),'prediction batch date is more than seven days stale'
FROM raw.fact_attrition_risk WHERE CAST(as_of_date AS DATE) < (SELECT MAX(CAST(as_of_date AS DATE)) FROM raw.fact_attrition_risk) - INTERVAL 7 DAY
UNION ALL SELECT 'DQ-C11','fact_anomaly',CAST(result_id AS VARCHAR),'scored_at is missing or older than 24 hours'
FROM raw.fact_anomaly WHERE scored_at IS NULL OR CAST(scored_at AS TIMESTAMP) < CURRENT_TIMESTAMP - INTERVAL 24 HOUR
UNION ALL SELECT 'DQ-C12','dim_employee',row_key,detail FROM c12
UNION ALL SELECT 'DQ-C13','dq.etl_run_log','latest_success','No successful ETL run finished within the last 24 hours'
WHERE NOT EXISTS (SELECT 1 FROM dq.etl_run_log WHERE status='SUCCESS' AND TRY_CAST(finished_at AS TIMESTAMPTZ) >= CURRENT_TIMESTAMP - INTERVAL 24 HOUR)
UNION ALL SELECT 'DQ-C14','metrics.*',metric_id || '|' || period_key || '|' || department_id,
       'group_size=' || CAST(group_size AS VARCHAR) || ' is below required threshold'
FROM dq.v_min_group_size_violations;
