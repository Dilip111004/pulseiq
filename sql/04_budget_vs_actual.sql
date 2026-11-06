CREATE OR REPLACE VIEW metrics.pq10_budget_vs_actual AS
SELECT
    CAST(b.month AS DATE) AS month,
    b.department_id,
    ROUND(b.budget_payroll_cost, 2) AS budget_payroll_cost,
    ROUND(a.employer_cost, 2) AS actual_employer_cost,
    CASE
        WHEN a.employer_cost IS NOT NULL
        THEN ROUND(a.employer_cost - b.budget_payroll_cost, 2)
        ELSE NULL
    END AS variance,
    CASE
        WHEN a.employer_cost IS NOT NULL
             AND b.budget_payroll_cost <> 0
        THEN ROUND(
            ((a.employer_cost - b.budget_payroll_cost)
             / b.budget_payroll_cost) * 100,
            2
        )
        ELSE NULL
    END AS variance_pct,
    a.group_size,
    CASE
        WHEN a.employer_cost IS NULL THEN 'Unavailable'
        WHEN a.employer_cost > b.budget_payroll_cost THEN 'Overspending'
        WHEN a.employer_cost < b.budget_payroll_cost THEN 'Underspending'
        ELSE 'On budget'
    END AS budget_status
FROM warehouse.budget_payroll_dept_month b
LEFT JOIN metrics.m09_employer_cost a
    ON b.department_id = a.department_id
    AND CAST(b.month AS DATE) =
        DATE_TRUNC('month', a.month_end_date)::DATE;
CREATE OR REPLACE VIEW metrics.pq10_kpi_vs_target_monthly AS

SELECT
    CAST(t.month AS DATE) AS month,
    t.department_id,
    'Attendance' AS metric_name,
    a.attendance_rate AS actual_value,
    t.attendance_rate_target AS target_value,
    'Higher is better' AS direction,
    CASE
        WHEN a.attendance_rate IS NULL THEN 'Unavailable'
        WHEN a.attendance_rate >= t.attendance_rate_target THEN 'Green'
        ELSE 'Red'
    END AS traffic_light,
    a.group_size
FROM warehouse.kpi_targets t
LEFT JOIN metrics.m13_attendance_rate a
    ON t.department_id = a.department_id
    AND CAST(t.month AS DATE) =
        DATE_TRUNC('month', a.month_end_date)::DATE

UNION ALL

SELECT
    CAST(t.month AS DATE),
    t.department_id,
    'Overtime',
    a.overtime_share_pct,
    t.overtime_share_target_pct,
    'Lower is better',
    CASE
        WHEN a.overtime_share_pct IS NULL THEN 'Unavailable'
        WHEN a.overtime_share_pct <= t.overtime_share_target_pct THEN 'Green'
        ELSE 'Red'
    END,
    a.group_size
FROM warehouse.kpi_targets t
LEFT JOIN metrics.m11_overtime_share a
    ON t.department_id = a.department_id
    AND CAST(t.month AS DATE) =
        DATE_TRUNC('month', a.month_end_date)::DATE

UNION ALL

SELECT
    CAST(t.month AS DATE),
    t.department_id,
    'Attrition',
    a.attrition_rate_monthly_pct,
    t.attrition_monthly_target_pct,
    'Lower is better',
    CASE
        WHEN a.attrition_rate_monthly_pct IS NULL THEN 'Unavailable'
        WHEN a.attrition_rate_monthly_pct <= t.attrition_monthly_target_pct THEN 'Green'
        ELSE 'Red'
    END,
    a.group_size
FROM warehouse.kpi_targets t
LEFT JOIN metrics.m04_attrition_rate_monthly a
    ON t.department_id = a.department_id
    AND CAST(t.month AS DATE) =
        CAST(a.month_start_date AS DATE);

-- PQ-10: Task completion reference comparison.
-- Actual grain: team x sprint.
-- Target grain: department x month.
-- This is a reference comparison, not a like-for-like monthly KPI.

CREATE OR REPLACE VIEW metrics.pq10_task_completion_vs_target AS
SELECT
    CAST(s.start_date AS DATE) AS sprint_start_date,
    CAST(s.end_date AS DATE) AS sprint_end_date,
    CAST(DATE_TRUNC('month', s.end_date) AS DATE) AS target_month,
    m.sprint_id,
    m.team_id,
    d.department_id,
    ROUND(m.task_completion_rate * 100, 2) AS actual_completion_pct,
    t.task_completion_target_pct AS target_completion_pct,
    CASE
        WHEN t.task_completion_target_pct IS NULL THEN 'Unavailable'
        WHEN m.task_completion_rate * 100 >= t.task_completion_target_pct THEN 'Green'
        ELSE 'Red'
    END AS traffic_light,
    m.group_size,
    'Team-sprint actual compared with department-month target; reference only'
        AS comparison_note
FROM metrics.m22_task_completion_rate m
JOIN warehouse.dim_sprint s
    ON m.sprint_id = s.sprint_id
JOIN warehouse.dim_team d
    ON m.team_id = d.team_id
LEFT JOIN warehouse.kpi_targets t
    ON d.department_id = t.department_id
   AND CAST(DATE_TRUNC('month', s.end_date) AS DATE) = CAST(t.month AS DATE);
