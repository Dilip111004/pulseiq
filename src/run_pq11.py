import shutil
import tempfile
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DB = ROOT / "outputs" / "pulseiq.duckdb"
SQL_FILE = ROOT / "sql" / "05_pl_expense_analytics.sql"
OUTPUT_DIR = ROOT / "outputs"

VIEWS = {
    "pq11_monthly_pl": "pq11_monthly_pl.csv",
    "pq11_expense_by_category": "pq11_expense_by_category.csv",
    "pq11_top_vendors": "pq11_top_vendors.csv",
    "pq11_expense_ledger_reconciliation": "pq11_expense_ledger_reconciliation.csv",
}

def main():
    if not SOURCE_DB.exists():
        raise FileNotFoundError(SOURCE_DB)
    if not SQL_FILE.exists():
        raise FileNotFoundError(SQL_FILE)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    temp_db = Path(tempfile.gettempdir()) / "pulseiq_pq11_export.duckdb"

    try:
        shutil.copy2(SOURCE_DB, temp_db)
        connection = duckdb.connect(str(temp_db))
        connection.execute(SQL_FILE.read_text(encoding="utf-8-sig"))

        for view, filename in VIEWS.items():
            dataframe = connection.execute(
                f"SELECT * FROM metrics.{view}"
            ).fetchdf()
            output_path = OUTPUT_DIR / filename
            dataframe.to_csv(output_path, index=False)
            print(f"{filename}: {len(dataframe)} rows")

        connection.close()
        print("PQ-11 exports completed.")
    finally:
        temp_db.unlink(missing_ok=True)

if __name__ == "__main__":
    main()
