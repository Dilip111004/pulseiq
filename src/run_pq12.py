from pathlib import Path
import shutil
import tempfile
import duckdb

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DB = ROOT / "outputs" / "pulseiq.duckdb"
SQL_FILE = ROOT / "sql" / "06_invoices_receivables_cashflow.sql"
OUTPUT_DIR = ROOT / "outputs"

if not SOURCE_DB.exists():
    raise FileNotFoundError(f"Warehouse not found: {SOURCE_DB}")

with tempfile.TemporaryDirectory(prefix="pulseiq_pq12_") as temp_dir:
    temp_db = Path(temp_dir) / "pq12_validation.duckdb"
    shutil.copy2(SOURCE_DB, temp_db)
    con = duckdb.connect(str(temp_db))
    con.execute(SQL_FILE.read_text(encoding="utf-8"))

    exports = {
        "pq12_receivables_ageing.csv": "SELECT * FROM metrics.pq12_receivables_ageing ORDER BY CASE ageing_bucket WHEN 'Current' THEN 1 WHEN '1-30 days' THEN 2 WHEN '31-60 days' THEN 3 WHEN '61-90 days' THEN 4 ELSE 5 END",
        "pq12_client_payment_behaviour.csv": "SELECT * FROM metrics.pq12_client_payment_behaviour ORDER BY avg_days_to_pay DESC",
        "pq12_monthly_cash_flow.csv": "SELECT * FROM metrics.pq12_monthly_cash_flow ORDER BY month_start",
        "pq12_overdue_clients.csv": "SELECT * FROM metrics.pq12_overdue_clients ORDER BY overdue_balance DESC"
    }

    for filename, query in exports.items():
        output = OUTPUT_DIR / filename
        con.execute(query).fetchdf().to_csv(output, index=False)
        print(f"Exported {filename}: {con.execute(f'SELECT COUNT(*) FROM ({query})').fetchone()[0]} rows")

    ageing = con.execute("""
        SELECT SUM(receivables) FROM metrics.pq12_receivables_ageing
    """).fetchone()[0]
    open_total = con.execute("""
        SELECT ROUND(SUM(balance_due), 2)
        FROM warehouse.fact_invoice
        WHERE status IN ('SENT', 'OVERDUE', 'PARTIALLY_PAID')
          AND balance_due > 0
    """).fetchone()[0]
    print(f"Ageing total: {ageing:,.2f}")
    print(f"Open receivables: {open_total:,.2f}")
    if round(ageing, 2) != round(open_total, 2):
        raise AssertionError("Ageing buckets do not reconcile to open receivables")

    print("\nTop 5 slow-paying clients:")
    print(con.execute("""
        SELECT client_name, paid_invoices, avg_days_to_pay, payment_terms_days
        FROM metrics.pq12_client_payment_behaviour
        ORDER BY avg_days_to_pay DESC LIMIT 5
    """).fetchdf().to_string(index=False))

    print("\nTop overdue clients:")
    print(con.execute("""
        SELECT client_name, overdue_invoices, overdue_balance, max_days_past_due
        FROM metrics.pq12_overdue_clients
        ORDER BY overdue_balance DESC LIMIT 5
    """).fetchdf().to_string(index=False))
    con.close()

