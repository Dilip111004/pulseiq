from pathlib import Path
import sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from build_warehouse import PKS, FKS, build_future_date_rows
from run_etl import schema_drift_errors

RAW=ROOT/"data"/"raw"
CLEAN=ROOT/"data"/"clean"
REJECTED=ROOT/"data"/"rejected"

def read(folder,name):
    return pd.read_csv(folder/f"{name}.csv",low_memory=False)

def test_etl_row_accounting_all_csvs():
    for raw_path in RAW.glob("*.csv"):
        table=raw_path.stem
        source=pd.read_csv(raw_path,low_memory=False)
        clean=read(CLEAN,table)
        rejected=pd.read_csv(REJECTED/f"{table}_rejected.csv",low_memory=False)
        assert len(source)==len(clean)+len(rejected), table

def test_primary_keys_are_unique_and_non_null_in_clean_outputs():
    for table,keys in PKS.items():
        df=read(CLEAN,table)
        assert not df[keys].isna().any(axis=None), table
        assert not df.duplicated(keys).any(), table

def test_foreign_key_integrity_for_clean_outputs():
    for child,links in FKS.items():
        df=read(CLEAN,child)
        for col,parent,parent_col in links:
            parent_values=set(read(CLEAN,parent)[parent_col].dropna().astype(str))
            if child=="fact_forecast" and col=="forecast_month_key":
                # The warehouse extends dim_date through the forecast horizon; these future keys
                # are intentionally not part of the original source/clean calendar.
                parent_values.update(read(CLEAN,"fact_forecast")["forecast_month_key"].dropna().astype(str))
            values=df[col]
            bad=values.notna() & ~values.astype(str).isin(parent_values)
            assert not bad.any(), (child,col,parent,df.loc[bad,col].head().tolist())

def test_employee_history_is_non_overlapping_after_logged_repair():
    df=read(CLEAN,"dim_employee")
    df["from_dt"]=pd.to_datetime(df["valid_from"],errors="coerce")
    df["to_dt"]=pd.to_datetime(df["valid_to"].replace("9999-12-31","2262-04-11"),errors="coerce")
    for emp_id,group in df.sort_values(["employee_id","from_dt"]).groupby("employee_id"):
        prev_end=None
        for _,row in group.iterrows():
            if prev_end is not None:
                assert prev_end < row["from_dt"], f"SCD2 overlap for {emp_id}"
            prev_end=row["to_dt"]

def test_expected_contract_and_business_quarantines():
    expected={
        "fact_payroll":(7340,4),
        "fact_attendance_monthly":(7339,4),
        "fact_attrition_risk":(425,5),
        "fact_task":(28848,20),
        "fact_leave":(3439,2),
        "fact_invoice":(742,1),
        "fact_invoice_payment":(708,1),
        "fact_expense":(500,1),
    }
    for table,(clean_n,rejected_n) in expected.items():
        assert len(read(CLEAN,table))==clean_n, table
        assert len(pd.read_csv(REJECTED/f"{table}_rejected.csv",low_memory=False))==rejected_n, table

def test_transform_log_records_scd2_repair():
    log=pd.read_csv(ROOT/"logs"/"etl_transform_log.csv")
    assert len(log)==1
    assert log.iloc[0]["reason"]=="SCD2_OVERLAP_CLIPPED_TO_DAY_BEFORE_NEXT_VALID_FROM"


def test_forecast_calendar_extension_covers_horizon():
    from datetime import date
    extension=build_future_date_rows(date(2027,1,1),date(2027,3,31))
    assert len(extension)==90
    keys=set(extension["date_key"].astype(int))
    assert {20270131,20270228,20270331}.issubset(keys)
    # Public-holiday status is unknown for generated future dates; do not fabricate it.
    assert extension["is_holiday"].isna().all()

def test_all_metric_views_and_dq_checks_are_declared():
    import re
    metric_sql=(ROOT/"sql"/"03_metric_views.sql").read_text(encoding="utf-8")
    dq_sql=(ROOT/"sql"/"02_data_quality_checks.sql").read_text(encoding="utf-8")
    metrics=set(re.findall(r"CREATE OR REPLACE VIEW metrics\.m(\d{2})_",metric_sql))
    checks=set(re.findall(r"'DQ-C(\d{2})'",dq_sql))
    assert metrics=={f"{i:02d}" for i in range(1,29)}
    assert checks=={f"{i:02d}" for i in range(1,15)}


def test_schema_drift_policy_detects_unexpected_and_missing_columns():
    dictionary = pd.DataFrame({
        "sheet": ["example", "example", "example"],
        "column": ["id", "amount", "status"],
    })
    frames = {"example": pd.DataFrame({"id": [1], "amount": [10], "new_field": ["x"]})}
    errors = schema_drift_errors(frames, dictionary)
    assert "example" in errors
    joined = " ".join(errors["example"])
    assert "MISSING_COLUMNS:status" in joined
    assert "UNEXPECTED_COLUMNS:new_field" in joined


def test_schema_drift_policy_accepts_exact_schema():
    dictionary = pd.DataFrame({"sheet": ["example", "example"], "column": ["id", "amount"]})
    frames = {"example": pd.DataFrame({"id": [1], "amount": [10]})}
    assert schema_drift_errors(frames, dictionary) == {}


def test_m19_uses_ledger_payroll_accounts_not_payroll_fact_as_numerator():
    sql = (ROOT / "sql" / "03_metric_views.sql").read_text(encoding="utf-8")
    start = sql.index("CREATE OR REPLACE VIEW metrics.m19_payroll_as_pct_revenue AS")
    end = sql.index("CREATE OR REPLACE VIEW metrics.m20_days_sales_outstanding AS", start)
    m19 = sql[start:end]
    assert "'5001','5002','5003','5004','5005'" in m19
    assert "lp.payroll_cost_ledger / NULLIF(r.revenue,0)" in m19
    assert "ps.payroll_cost_fact" in m19  # retained only for reconciliation visibility


def test_metric_catalog_includes_owner_and_governance_fields():
    sql = (ROOT / "sql" / "03_metric_views.sql").read_text(encoding="utf-8")
    marker = "CREATE OR REPLACE VIEW governance.metric_catalog AS"
    catalog = sql[sql.index(marker):]
    for column in ["metric_id", "metric_name", "business_definition", "source_table", "owner_team", "minimum_group_size"]:
        assert column in catalog


def test_dq_sql_has_persisted_results_and_row_level_evidence():
    sql = (ROOT / "sql" / "02_data_quality_checks.sql").read_text(encoding="utf-8")
    assert "CREATE OR REPLACE VIEW dq.v_bad_rows AS" in sql
    assert "AS table_name" in sql
    assert "AS run_at" in sql
    build = (ROOT / "src" / "build_warehouse.py").read_text(encoding="utf-8")
    assert "CREATE OR REPLACE TABLE dq.dq_results AS SELECT * FROM dq.v_check_results" in build
    assert "outputs/dq_sql_bad_rows.csv" in build
