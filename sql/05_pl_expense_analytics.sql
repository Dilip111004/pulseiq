-- PulseIQ Phase 2 | PQ-11 | P&L and Expense Analytics

CREATE OR REPLACE VIEW metrics.pq11_monthly_pl AS
WITH monthly AS (
    SELECT
        CAST(l.posting_period || '-01' AS DATE) AS month,
        ROUND(SUM(CASE
            WHEN l.account_code BETWEEN 4001 AND 4004
            THEN -l.signed_amount_debit_positive ELSE 0
        END), 2) AS operating_revenue,
        ROUND(SUM(CASE
            WHEN l.account_code = 4900
            THEN -l.signed_amount_debit_positive ELSE 0
        END), 2) AS other_income,
        ROUND(SUM(CASE
            WHEN l.account_code BETWEEN 5000 AND 5999
            THEN l.signed_amount_debit_positive ELSE 0
        END), 2) AS expenses
    FROM warehouse.fact_ledger l
    JOIN warehouse.dim_account a USING (account_code)
    WHERE a.statement = 'Profit & Loss'
      AND a.is_group = 'N'
    GROUP BY 1
)
SELECT
    m.month,
    m.operating_revenue,
    m.other_income,
    ROUND(m.operating_revenue + m.other_income, 2) AS total_income,
    m.expenses,
    ROUND(m.operating_revenue + m.other_income - m.expenses, 2) AS net_profit,
    ROUND(p.net_profit, 2) AS m17_net_profit,
    ROUND(
        m.operating_revenue + m.other_income - m.expenses - p.net_profit,
        2
    ) AS m17_difference
FROM monthly m
LEFT JOIN metrics.m17_net_profit p
    ON m.month = p.month_start_date;

CREATE OR REPLACE VIEW metrics.pq11_expense_by_category AS
SELECT
    f.category_account AS account_code,
    a.account_name AS category,
    COUNT(*) AS expense_count,
    ROUND(SUM(f.amount_excl_gst), 2) AS amount_excl_gst,
    ROUND(SUM(f.gst_amount), 2) AS gst_amount,
    ROUND(SUM(f.total_amount), 2) AS total_amount_incl_gst
FROM warehouse.fact_expense f
JOIN warehouse.dim_account a
    ON f.category_account = a.account_code
WHERE a.statement = 'Profit & Loss'
  AND a.is_group = 'N'
GROUP BY 1, 2;

CREATE OR REPLACE VIEW metrics.pq11_top_vendors AS
SELECT
    f.vendor_id,
    COALESCE(v.vendor_name, 'Unknown vendor') AS vendor_name,
    COUNT(*) AS expense_count,
    ROUND(SUM(f.amount_excl_gst), 2) AS amount_excl_gst,
    ROUND(SUM(f.gst_amount), 2) AS gst_amount,
    ROUND(SUM(f.total_amount), 2) AS total_amount_incl_gst
FROM warehouse.fact_expense f
LEFT JOIN warehouse.dim_vendor v
    ON f.vendor_id = v.vendor_id
GROUP BY 1, 2;

CREATE OR REPLACE VIEW metrics.pq11_expense_ledger_reconciliation AS
WITH expense_totals AS (
    SELECT
        category_account AS account_code,
        COUNT(*) AS clean_expense_count,
        ROUND(SUM(amount_excl_gst), 2) AS clean_expense_excl_gst
    FROM warehouse.fact_expense
    GROUP BY 1
),
ledger_totals AS (
    SELECT
        l.account_code,
        ROUND(SUM(l.debit - l.credit), 2) AS ledger_net_expense
    FROM warehouse.fact_ledger l
    JOIN warehouse.dim_account a USING (account_code)
    WHERE a.statement = 'Profit & Loss'
      AND a.is_group = 'N'
      AND l.account_code BETWEEN 5000 AND 5999
    GROUP BY 1
)
SELECT
    a.account_code,
    a.account_name AS category,
    COALESCE(e.clean_expense_count, 0) AS clean_expense_count,
    COALESCE(e.clean_expense_excl_gst, 0) AS clean_expense_excl_gst,
    COALESCE(l.ledger_net_expense, 0) AS ledger_net_expense,
    ROUND(
        COALESCE(e.clean_expense_excl_gst, 0)
        - COALESCE(l.ledger_net_expense, 0), 2
    ) AS difference
FROM expense_totals e
JOIN warehouse.dim_account a ON a.account_code = e.account_code
LEFT JOIN ledger_totals l ON a.account_code = l.account_code
WHERE a.statement = 'Profit & Loss'
  AND a.is_group = 'N'
  AND a.account_code BETWEEN 5000 AND 5999;
