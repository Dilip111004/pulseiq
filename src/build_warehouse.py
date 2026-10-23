#!/usr/bin/env python3
"""Build the DuckDB warehouse from ETL-cleaned CSVs.

Run after `python src/run_etl.py`. The raw schema preserves source exports, clean
contains validated outputs, governance stores dictionaries/contracts, and warehouse
contains PK-constrained dimensions/facts.
"""
from pathlib import Path
import argparse, re, sys
import pandas as pd

PKS = {
    "dim_date":["date_key"], "dim_employee":["employee_key"], "dim_department":["department_id"],
    "dim_role":["role_id"], "dim_location":["work_location"], "dim_leave_type":["leave_type_code"],
    "dim_account":["account_code"], "dim_client":["client_id"], "dim_vendor":["vendor_id"],
    "dim_team":["team_id"], "dim_sprint":["sprint_id"], "fact_payroll":["payroll_item_id"],
    "fact_attendance_monthly":["attendance_fact_id"], "fact_leave":["leave_request_id"],
    "fact_headcount_monthly":["date_key","department_id"], "fact_ledger":["line_id"],
    "fact_invoice":["invoice_id"], "fact_invoice_payment":["payment_id"], "fact_expense":["expense_id"],
    "fact_task":["task_id"], "fact_anomaly":["result_id"], "fact_attrition_risk":["prediction_id"],
    "fact_forecast":["forecast_id"], "budget_payroll_dept_month":["department_id","month"],
    "kpi_targets":["month","department_id"],
}
GOVERNANCE={"data_dictionary","data_contracts","metric_dictionary","dq_checks_catalog"}
DIM_ORDER=["dim_date","dim_department","dim_role","dim_location","dim_leave_type","dim_account",
           "dim_client","dim_vendor","dim_sprint","dim_team","dim_employee"]
FACT_ORDER=["fact_headcount_monthly","fact_payroll","fact_attendance_monthly","fact_leave","fact_ledger",
            "fact_invoice","fact_invoice_payment","fact_expense","fact_task","fact_anomaly",
            "fact_attrition_risk","fact_forecast","budget_payroll_dept_month","kpi_targets"]
FKS={
    "dim_role":[("department_id","dim_department","department_id")],
    "dim_team":[("department_id","dim_department","department_id")],
    "dim_employee":[("department_id","dim_department","department_id"),("role_id","dim_role","role_id"),("work_location","dim_location","work_location")],
    "fact_headcount_monthly":[("date_key","dim_date","date_key"),("department_id","dim_department","department_id")],
    "fact_payroll":[("employee_key","dim_employee","employee_key"),("date_key","dim_date","date_key"),("department_id","dim_department","department_id"),("role_id","dim_role","role_id")],
    "fact_attendance_monthly":[("employee_key","dim_employee","employee_key"),("date_key","dim_date","date_key"),("department_id","dim_department","department_id")],
    "fact_leave":[("employee_key","dim_employee","employee_key"),("leave_type_code","dim_leave_type","leave_type_code"),("start_date_key","dim_date","date_key"),("end_date_key","dim_date","date_key")],
    "fact_ledger":[("date_key","dim_date","date_key"),("account_code","dim_account","account_code"),("cost_center_department_id","dim_department","department_id")],
    "fact_invoice":[("client_id","dim_client","client_id"),("invoice_date_key","dim_date","date_key"),("service_line_account","dim_account","account_code")],
    "fact_invoice_payment":[("invoice_id","fact_invoice","invoice_id"),("payment_date_key","dim_date","date_key")],
    "fact_expense":[("expense_date_key","dim_date","date_key"),("category_account","dim_account","account_code"),("vendor_id","dim_vendor","vendor_id"),("department_id","dim_department","department_id")],
    "fact_task":[("team_id","dim_team","team_id"),("sprint_id","dim_sprint","sprint_id")],
    "fact_anomaly":[("period_key","dim_date","date_key")],
    "fact_attrition_risk":[("employee_key","dim_employee","employee_key"),("department_id","dim_department","department_id"),("as_of_date_key","dim_date","date_key")],
    "fact_forecast":[("forecast_month_key","dim_date","date_key")],
    "budget_payroll_dept_month":[("department_id","dim_department","department_id")],
    "kpi_targets":[("department_id","dim_department","department_id")],
}

def ident(s): return '"' + str(s).replace('"','""') + '"'
def table_id(schema, table): return f"{ident(schema)}.{ident(table)}"

def build_future_date_rows(start_date, end_date):
    """Generate calendar rows needed by the forecast horizon beyond the supplied date dimension."""
    from datetime import date, timedelta
    rows=[]
    d=start_date
    while d<=end_date:
        wd=d.weekday()
        fy_start=d.year if d.month>=4 else d.year-1
        fy=f"FY{fy_start}-{str(fy_start+1)[-2:]}"
        fiscal_month=((d.month-4)%12)+1
        fiscal_quarter=f"Q{((fiscal_month-1)//3)+1}"
        next_month=date(d.year+(d.month==12),1 if d.month==12 else d.month+1,1)
        month_end=next_month-timedelta(days=1)
        rows.append({
            "date":d.isoformat(),"date_key":int(d.strftime("%Y%m%d")),"year":d.year,"quarter":(d.month-1)//3+1,
            "month_number":d.month,"month_name":d.strftime("%B"),"year_month":d.strftime("%Y-%m"),
            "week_of_year":int(d.isocalendar().week),"day_of_week":d.strftime("%A"),
            "is_weekend":"Y" if wd>=5 else "N","is_holiday":None,"is_working_day":"N" if wd>=5 else None,
            "financial_year":fy,"fiscal_quarter":fiscal_quarter,"fiscal_month_number":fiscal_month,
            "is_month_end":"Y" if d==month_end else "N","month_start_date":d.replace(day=1).isoformat(),
            "month_end_date":month_end.isoformat()
        })
        d+=timedelta(days=1)
    return pd.DataFrame(rows)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--raw-dir",default="data/raw")
    ap.add_argument("--clean-dir",default="data/clean")
    ap.add_argument("--db",default="outputs/pulseiq.duckdb")
    args=ap.parse_args()
    try:
        import duckdb
    except ImportError:
        print("ERROR: DuckDB is not installed. Run `pip install -r requirements.txt` and retry.",file=sys.stderr)
        return 2
    raw_dir,clean_dir,db=Path(args.raw_dir),Path(args.clean_dir),Path(args.db)
    db.parent.mkdir(parents=True,exist_ok=True)
    con=duckdb.connect(str(db))
    for schema in ["metrics","dq","warehouse","governance","clean","raw"]:
        con.execute(f"DROP SCHEMA IF EXISTS {ident(schema)} CASCADE")
        con.execute(f"CREATE SCHEMA {ident(schema)}")
    # Bronze raw and ETL-clean copies.
    for path in sorted(raw_dir.glob("*.csv")):
        table=path.stem
        safe=str(path.resolve()).replace("'","''")
        con.execute(f"CREATE TABLE {table_id('raw',table)} AS SELECT * FROM read_csv_auto('{safe}', header=true, sample_size=-1)")
    for path in sorted(clean_dir.glob("*.csv")):
        table=path.stem
        safe=str(path.resolve()).replace("'","''")
        schema="governance" if table in GOVERNANCE else "clean"
        con.execute(f"CREATE TABLE {table_id(schema,table)} AS SELECT * FROM read_csv_auto('{safe}', header=true, sample_size=-1)")
    # Constrained warehouse dimensions then facts. PKs are enforced by DuckDB.
    all_warehouse=[t for t in DIM_ORDER+FACT_ORDER if (clean_dir/f"{t}.csv").exists()]
    def create_warehouse_table(table):
        source=table_id("clean",table)
        desc=con.execute(f"DESCRIBE SELECT * FROM {source}").fetchall()
        cols=[(r[0],r[1]) for r in desc]
        pk=PKS.get(table,[])
        fk=FKS.get(table,[])
        definitions=[f"{ident(col)} {dtype}" for col,dtype in cols]
        if pk:
            definitions.append("PRIMARY KEY ("+", ".join(ident(c) for c in pk)+")")
        for col,parent,parent_col in fk:
            if col in [c for c,_ in cols]:
                definitions.append(f"FOREIGN KEY ({ident(col)}) REFERENCES {table_id('warehouse',parent)} ({ident(parent_col)})")
        con.execute(f"CREATE TABLE {table_id('warehouse',table)} ("+", ".join(definitions)+")")
        con.execute(f"INSERT INTO {table_id('warehouse',table)} SELECT * FROM {source}")
    for table in DIM_ORDER:
        if table in all_warehouse: create_warehouse_table(table)
    calendar_extension_rows=0
    # Extend only the warehouse calendar to cover forecast months Jan–Mar 2027.
    # The supplied raw/clean date dimension remains unchanged; future holiday flags are unknown,
    # so generated dates mark weekends accurately and do not invent public holidays.
    if "dim_date" in all_warehouse:
        existing_max=con.execute("SELECT MAX(CAST(date AS DATE)) FROM warehouse.dim_date").fetchone()[0]
        if (clean_dir/"fact_forecast.csv").exists():
            from datetime import date, timedelta
            max_forecast_key=max(int(x) for x in con.execute("SELECT DISTINCT forecast_month_key FROM clean.fact_forecast").fetchnumpy()["forecast_month_key"])
            forecast_end=date(int(str(max_forecast_key)[:4]),int(str(max_forecast_key)[4:6]),int(str(max_forecast_key)[6:8]))
            if forecast_end>existing_max:
                extension=build_future_date_rows(existing_max+timedelta(days=1),forecast_end)
                con.register("future_date_rows",extension)
                con.execute("INSERT INTO warehouse.dim_date SELECT * FROM future_date_rows")
                calendar_extension_rows=len(extension)
                con.unregister("future_date_rows")
    for table in FACT_ORDER:
        if table in all_warehouse: create_warehouse_table(table)
    # SCD2-safe temporal joins for feeds that only carry a natural employee ID.
    con.execute("""
        CREATE OR REPLACE VIEW warehouse.v_fact_task_employee_history AS
        SELECT t.*, e.employee_key, e.department_id AS employee_department_at_task,
               e.role_id AS employee_role_at_task
        FROM warehouse.fact_task t
        LEFT JOIN warehouse.dim_employee e
          ON t.assignee_employee_id = e.employee_id
         AND CAST(t.created_date AS DATE) >= CAST(e.valid_from AS DATE)
         AND CAST(t.created_date AS DATE) <= CAST(e.valid_to AS DATE)
    """)
    con.execute("""
        CREATE OR REPLACE VIEW warehouse.v_fact_anomaly_employee_history AS
        SELECT a.*, e.employee_key, e.department_id AS employee_department_at_period
        FROM warehouse.fact_anomaly a
        LEFT JOIN warehouse.dim_employee e
          ON a.employee_id = e.employee_id
         AND CAST(a.period AS DATE) >= CAST(e.valid_from AS DATE)
         AND CAST(a.period AS DATE) <= CAST(e.valid_to AS DATE)
    """)
    # Load ETL evidence so freshness is checked against the actual latest successful run.
    for log_name in ["etl_run_log.csv","etl_table_log.csv","etl_transform_log.csv"]:
        log_path=Path("logs")/log_name
        if log_path.exists():
            log_table=log_name[:-4]
            safe=str(log_path.resolve()).replace("'","''")
            con.execute(f"CREATE OR REPLACE TABLE {table_id('dq',log_table)} AS SELECT * FROM read_csv_auto('{safe}', header=true, sample_size=-1)")
    # Build governed metric views, then run the 14 catalogued checks (including privacy runtime).
    metrics_path=Path("sql/03_metric_views.sql")
    checks_path=Path("sql/02_data_quality_checks.sql")
    if metrics_path.exists(): con.execute(metrics_path.read_text(encoding="utf-8"))
    if checks_path.exists(): con.execute(checks_path.read_text(encoding="utf-8"))
    if checks_path.exists():
        # Persist the requested check/table/count/status/run-time result table and row-level evidence.
        con.execute("CREATE OR REPLACE TABLE dq.dq_results AS SELECT * FROM dq.v_check_results")
        check_results=con.execute("SELECT * FROM dq.dq_results ORDER BY check_id").df()
        check_results.to_csv("outputs/dq_sql_results.csv",index=False)
        bad_rows=con.execute("SELECT * FROM dq.v_bad_rows ORDER BY check_id, table_name, row_key").df()
        bad_rows.to_csv("outputs/dq_sql_bad_rows.csv",index=False)
        # Export each metric view for review and hand-checks.
        for view_name, in con.execute("SELECT table_name FROM information_schema.views WHERE table_schema='metrics' AND table_name LIKE 'm%' ORDER BY table_name").fetchall():
            con.execute(f"COPY (SELECT * FROM metrics.{ident(view_name)}) TO 'outputs/{view_name}.csv' (HEADER, DELIMITER ',')")
    # Reconciliation counts are based on clean rows; rejected rows remain in quarantine CSVs.
    counts=[]
    for table in all_warehouse:
        source_count=con.execute(f"SELECT COUNT(*) FROM {table_id('clean',table)}").fetchone()[0]
        warehouse_count=con.execute(f"SELECT COUNT(*) FROM {table_id('warehouse',table)}").fetchone()[0]
        extension_rows=calendar_extension_rows if table=="dim_date" else 0
        counts.append({"table_name":table,"clean_rows":source_count,"warehouse_rows":warehouse_count,
                       "warehouse_extension_rows":extension_rows,
                       "row_count_match":warehouse_count==source_count+extension_rows})
    pd.DataFrame(counts).to_csv("outputs/warehouse_row_reconciliation.csv",index=False)
    # Indexes on frequent join/filter columns.
    index_defs=[
        ("fact_payroll","employee_key"),("fact_payroll","date_key"),("fact_payroll","department_id"),
        ("fact_attendance_monthly","employee_key"),("fact_attendance_monthly","date_key"),
        ("fact_leave","employee_key"),("fact_ledger","date_key"),("fact_ledger","account_code"),
        ("fact_invoice","client_id"),("fact_invoice_payment","invoice_id"),("fact_expense","vendor_id"),
        ("fact_task","team_id"),("fact_task","sprint_id"),("fact_headcount_monthly","department_id"),
    ]
    for table,col in index_defs:
        name=re.sub(r"[^A-Za-z0-9_]","_",f"idx_{table}_{col}")
        con.execute(f"CREATE INDEX IF NOT EXISTS {ident(name)} ON {table_id('warehouse',table)} ({ident(col)})")
    print(f"Built {db} with {len(all_warehouse)} warehouse tables.")
    print(f"Row reconciliation: {sum(x['row_count_match'] for x in counts)}/{len(counts)} tables matched.")
    con.close()
    return 0

if __name__=="__main__":
    raise SystemExit(main())
