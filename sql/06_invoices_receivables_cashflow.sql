CREATE OR REPLACE VIEW metrics.pq12_receivables_ageing AS
WITH cutoff AS (
    SELECT MAX(CAST(period_end_date AS DATE)) AS cutoff_date
    FROM warehouse.fact_payroll
),
open_invoices AS (
    SELECT i.*, c.cutoff_date,
           GREATEST(DATE_DIFF('day', i.due_date, c.cutoff_date), 0) AS days_overdue
    FROM warehouse.fact_invoice i
    CROSS JOIN cutoff c
    WHERE i.status IN ('SENT', 'OVERDUE', 'PARTIALLY_PAID')
      AND i.balance_due > 0
)
SELECT
    CASE
        WHEN days_overdue = 0 THEN 'Current'
        WHEN days_overdue BETWEEN 1 AND 30 THEN '1-30 days'
        WHEN days_overdue BETWEEN 31 AND 60 THEN '31-60 days'
        WHEN days_overdue BETWEEN 61 AND 90 THEN '61-90 days'
        ELSE '90+ days'
    END AS ageing_bucket,
    COUNT(*) AS invoice_count,
    ROUND(SUM(balance_due), 2) AS receivables
FROM open_invoices
GROUP BY 1;

CREATE OR REPLACE VIEW metrics.pq12_client_payment_behaviour AS
SELECT
    c.client_id,
    c.client_name,
    COUNT(*) AS paid_invoices,
    ROUND(AVG(i.days_to_pay), 2) AS avg_days_to_pay,
    c.payment_terms_days AS payment_terms_days,
    ROUND(AVG(i.days_to_pay) - c.payment_terms_days, 2) AS avg_days_over_terms
FROM warehouse.fact_invoice i
JOIN warehouse.dim_client c USING (client_id)
WHERE i.status = 'PAID'
  AND i.days_to_pay IS NOT NULL
GROUP BY c.client_id, c.client_name, c.payment_terms_days;

CREATE OR REPLACE VIEW metrics.pq12_monthly_cash_flow AS
WITH cash_in AS (
    SELECT DATE_TRUNC('month', payment_date)::DATE AS month_start,
           SUM(amount) AS cash_in,
           COUNT(*) AS cash_in_payments
    FROM warehouse.fact_invoice_payment
    WHERE payment_date IS NOT NULL
    GROUP BY 1
),
cash_out AS (
    SELECT DATE_TRUNC('month', paid_date)::DATE AS month_start,
           SUM(total_amount) AS cash_out,
           COUNT(*) AS cash_out_payments
    FROM warehouse.fact_expense
    WHERE status = 'PAID' AND paid_date IS NOT NULL
    GROUP BY 1
)
SELECT
    COALESCE(i.month_start, o.month_start) AS month_start,
    ROUND(COALESCE(i.cash_in, 0), 2) AS cash_in,
    ROUND(COALESCE(o.cash_out, 0), 2) AS cash_out,
    ROUND(COALESCE(i.cash_in, 0) - COALESCE(o.cash_out, 0), 2) AS net_cash_movement,
    COALESCE(i.cash_in_payments, 0) AS cash_in_payments,
    COALESCE(o.cash_out_payments, 0) AS cash_out_payments
FROM cash_in i
FULL OUTER JOIN cash_out o USING (month_start);

CREATE OR REPLACE VIEW metrics.pq12_overdue_clients AS
WITH cutoff AS (
    SELECT MAX(CAST(period_end_date AS DATE)) AS cutoff_date
    FROM warehouse.fact_payroll
)
SELECT
    c.client_id,
    c.client_name,
    COUNT(*) AS overdue_invoices,
    ROUND(SUM(i.balance_due), 2) AS overdue_balance,
    MAX(DATE_DIFF('day', i.due_date, cutoff.cutoff_date)) AS max_days_past_due
FROM warehouse.fact_invoice i
JOIN warehouse.dim_client c USING (client_id)
CROSS JOIN cutoff
WHERE i.status IN ('SENT', 'OVERDUE', 'PARTIALLY_PAID')
  AND i.balance_due > 0
  AND i.due_date < cutoff.cutoff_date
GROUP BY c.client_id, c.client_name;


