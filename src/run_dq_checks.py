#!/usr/bin/env python3
"""PQ-03 independent data-quality checks over untouched raw exports.

Writes a summary and row-level evidence. Checks are intentionally run against raw
source data so ETL quarantine does not hide the original defects. PQ-04 adds a
separate runtime check for privacy suppression once SQL metric views are built.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse, json
import pandas as pd

def load(raw_dir):
    return {p.stem: pd.read_csv(p, low_memory=False) for p in Path(raw_dir).glob("*.csv")}

def parse(s):
    return pd.to_datetime(s, errors="coerce")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--raw-dir",default="data/raw")
    ap.add_argument("--log-dir",default="logs")
    ap.add_argument("--clean-dir",default="data/clean")
    ap.add_argument("--out-dir",default="outputs/dq")
    ap.add_argument("--load-time",default=None,help="ISO timestamp for reproducible freshness checks")
    args=ap.parse_args()
    raw=load(args.raw_dir); out=Path(args.out_dir); out.mkdir(parents=True,exist_ok=True)
    now=pd.to_datetime(args.load_time,utc=True) if args.load_time else pd.Timestamp.now(tz="UTC")
    checks=[]; bad_rows=[]
    def record(cid,name,severity,df,mask,detail):
        mask=pd.Series(mask,index=df.index).fillna(False).astype(bool)
        bad=df.loc[mask].copy()
        checks.append({"check_id":cid,"check_name":name,"severity":severity,"status":"PASS" if bad.empty else "FAIL",
                       "bad_row_count":len(bad),"detail":detail})
        if not bad.empty:
            bad.insert(0,"check_id",cid); bad.insert(1,"check_name",name)
            bad.insert(2,"source_row_number",bad.index+2)
            bad_rows.append(bad)
        return bad

    pay=raw["fact_payroll"].copy(); led=raw["fact_ledger"].copy()
    pay["month"]=parse(pay["period_end_date"]).dt.strftime("%Y-%m")
    led["month"]=led["posting_period"].astype(str)
    pay_month=pay.groupby("month",dropna=False)["employer_cost"].sum()
    led_salary=led[led["account_code"].astype(str).isin(["5001","5002","5003","5004","5005"])].groupby("month")["signed_amount_debit_positive"].sum()
    comp=pd.concat([pay_month.rename("payroll_cost"),led_salary.rename("ledger_salary_expense")],axis=1).fillna(0)
    comp["difference"]=comp["payroll_cost"]-comp["ledger_salary_expense"]
    diff=comp[comp["difference"].abs()>.01].reset_index()
    # Independently reconcile after ETL quarantine to show which differences remain.
    clean_pay_path=Path(args.clean_dir)/"fact_payroll.csv"
    if clean_pay_path.exists():
        clean_pay=pd.read_csv(clean_pay_path,low_memory=False)
        clean_pay["month"]=parse(clean_pay["period_end_date"]).dt.strftime("%Y-%m")
        clean_pay_month=clean_pay.groupby("month")["employer_cost"].sum()
        post=pd.concat([clean_pay_month.rename("payroll_cost_clean"),led_salary.rename("ledger_salary_expense")],axis=1).fillna(0)
        post["difference"]=post["payroll_cost_clean"]-post["ledger_salary_expense"]
        post["status"]=post["difference"].abs().le(.01).map({True:"PASS",False:"FAIL"})
        post.reset_index().rename(columns={"index":"month"}).to_csv(out/"payroll_ledger_reconciliation_after_etl.csv",index=False)
    checks.append({"check_id":"DQ-C01","check_name":"Payroll equals ledger","severity":"Critical",
                   "status":"PASS" if diff.empty else "FAIL","bad_row_count":len(diff),
                   "detail":"Monthly payroll employer_cost versus ledger accounts 5001–5005; tolerance INR 0.01"})
    if not diff.empty:
        diff.insert(0,"check_id","DQ-C01"); diff.insert(1,"check_name","Payroll equals ledger"); bad_rows.append(diff)

    entry_bal=led.groupby("entry_id",as_index=False).agg(debit=("debit","sum"),credit=("credit","sum"))
    record("DQ-C02","Ledger balanced","Critical",entry_bal,(entry_bal.debit-entry_bal.credit).abs()>.005,
           "Per journal entry, absolute debit-credit difference must be <= INR 0.005")

    dups=pay.duplicated(["employee_id","run_id"],keep=False)
    record("DQ-C03","Unique payroll rows","Critical",pay,dups,
           "One payroll row per employee_id and run_id")

    dimemp=raw["dim_employee"]
    emp_ids=set(dimemp.employee_id.dropna().astype(str))
    for table,col in [
        ("fact_payroll","employee_id"),("fact_attendance_monthly","employee_id"),("fact_leave","employee_id"),
        ("fact_anomaly","employee_id"),("fact_attrition_risk","employee_id"),("fact_task","assignee_employee_id")
    ]:
        df=raw[table]
        mask=~df[col].astype(str).isin(emp_ids)
        record("DQ-C04",f"No orphan employees — {table}","Critical",df,mask,
               f"{col} must exist in dim_employee.employee_id")

    current=dimemp[dimemp["is_current"].astype(str).eq("Y")][["employee_id","exit_date"]].drop_duplicates("employee_id")
    att=raw["fact_attendance_monthly"].copy()
    att["period_dt"]=parse(att["period_end_date"])
    current["exit_dt"]=parse(current["exit_date"])
    att=att.merge(current[["employee_id","exit_dt"]],on="employee_id",how="left")
    mask=att["exit_dt"].notna() & att["period_dt"].notna() & (att["period_dt"].dt.to_period("M")>att["exit_dt"].dt.to_period("M"))
    record("DQ-C05","No attendance after exit","Warning",att,mask,
           "Attendance period month must not be after the employee exit month")

    a=raw["fact_attendance_monthly"].copy()
    p=raw["fact_payroll"].copy()
    a["month"]=parse(a["period_end_date"]).dt.strftime("%Y-%m")
    p["month"]=parse(p["period_end_date"]).dt.strftime("%Y-%m")
    ag=a.groupby(["employee_id","month"],as_index=False)["unpaid_absence_days"].sum()
    pg=p.groupby(["employee_id","month"],as_index=False)["lop_days"].sum()
    unpaid=ag.merge(pg,on=["employee_id","month"],how="left").fillna({"lop_days":0})
    record("DQ-C06","Unpaid leave deducted","Warning",unpaid,
           unpaid["unpaid_absence_days"]>unpaid["lop_days"]+0.5,
           "Unpaid absence days must be reflected in payroll LOP days within 0.5-day tolerance")

    inv=raw["fact_invoice"]
    record("DQ-C07","Invoice arithmetic","Warning",inv,
           (inv["amount_paid"]>inv["total_amount"]+.01)|(inv["balance_due"]<-.01),
           "Amount paid cannot exceed total; balance due cannot be negative")

    exp=raw["fact_expense"]
    record("DQ-C08","Expense arithmetic","Warning",exp,
           (exp["total_amount"]-(exp["amount_excl_gst"]+exp["gst_amount"])).abs()>.01,
           "total_amount must equal amount_excl_gst + gst_amount within INR 0.01")

    task=raw["fact_task"]
    started=parse(task["started_date"]); completed=parse(task["completed_date"])
    record("DQ-C09","Task dates sensible","Warning",task,
           (completed.notna()&started.notna()&(completed<started)) |
           (task["status"].astype(str).eq("Done")&completed.isna()),
           "Completed date cannot precede started date; Done tasks require a completion date")

    leave=raw["fact_leave"]
    record("DQ-C10","Leave dates sensible","Warning",leave,
           parse(leave["end_date"])<parse(leave["start_date"]),
           "Leave end date must be on or after start date")

    risk=raw["fact_attrition_risk"].copy()
    risk["as_of_dt"]=parse(risk["as_of_date"])
    max_date=risk["as_of_dt"].max()
    stale_risk=risk["as_of_dt"] < (max_date-pd.Timedelta(days=7))
    record("DQ-C11","AI feeds are fresh — prediction batch","Warning",risk,stale_risk,
           "Prediction as_of_date must be within 7 days of latest batch date")
    anomaly=raw["fact_anomaly"].copy()
    anomaly["scored_at_dt"]=pd.to_datetime(anomaly["scored_at"],errors="coerce",utc=True)
    stale_scores=anomaly["scored_at_dt"].isna() | (anomaly["scored_at_dt"] < now-pd.Timedelta(hours=24))
    record("DQ-C11","AI feeds are fresh — anomaly scoring","Warning",anomaly,stale_scores,
           "scored_at must be within 24 hours of ETL load time; static training data may be stale")

    emp=dimemp.copy()
    emp["from_dt"]=parse(emp["valid_from"])
    emp["to_dt"]=parse(emp["valid_to"])
    # pandas cannot represent year 9999; use an open-ended sentinel far beyond the dataset range.
    emp.loc[emp["valid_to"].astype(str).eq("9999-12-31"),"to_dt"]=pd.Timestamp("2262-04-11")
    emp=emp.sort_values(["employee_id","from_dt","employee_key"])
    overlap_ids=set()
    overlap_rows=[]
    for eid,g in emp.groupby("employee_id",sort=False):
        prev_end=None
        for _,row in g.iterrows():
            if prev_end is not None and pd.notna(row["from_dt"]) and prev_end>=row["from_dt"]:
                overlap_ids.add(row["employee_key"])
                overlap_rows.append({"employee_id":eid,"employee_key":row["employee_key"],"valid_from":row["valid_from"],
                                     "previous_valid_to":prev_end.strftime("%Y-%m-%d"),"current_valid_to":row["valid_to"]})
            if pd.notna(row["to_dt"]): prev_end=row["to_dt"] if prev_end is None else max(prev_end,row["to_dt"])
    overlap_df=pd.DataFrame(overlap_rows)
    checks.append({"check_id":"DQ-C12","check_name":"Dimension history does not overlap","severity":"Critical",
                   "status":"PASS" if overlap_df.empty else "FAIL","bad_row_count":len(overlap_df),
                   "detail":"Employee SCD2 validity intervals must not overlap"})
    if not overlap_df.empty:
        overlap_df.insert(0,"check_id","DQ-C12"); overlap_df.insert(1,"check_name","Dimension history does not overlap"); bad_rows.append(overlap_df)

    run_log_path=Path(args.log_dir)/"etl_run_log.csv"
    if run_log_path.exists():
        log=pd.read_csv(run_log_path)
        latest=pd.to_datetime(log["finished_at"],utc=True,errors="coerce").max()
        fresh=pd.notna(latest) and latest>=now-pd.Timedelta(hours=24)
    else:
        latest=pd.NaT; fresh=False
    checks.append({"check_id":"DQ-C13","check_name":"Pipeline freshness","severity":"Critical",
                   "status":"PASS" if fresh else "FAIL","bad_row_count":0 if fresh else 1,
                   "detail":f"Latest successful ETL finish={latest}; must be within 24 hours of check time"})

    # PQ-04 runtime check is completed by SQL after metric views are created. This explicit
    # placeholder prevents the report from falsely claiming the privacy check was executed.
    checks.append({"check_id":"DQ-C14","check_name":"Minimum group size","severity":"Critical",
                   "status":"PENDING_SQL_RUNTIME","bad_row_count":0,
                   "detail":"Run sql/02_data_quality_checks.sql after sql/03_metric_views.sql; verify every restricted metric view suppresses groups below its dictionary threshold."})

    subchecks=pd.DataFrame(checks)
    # The catalog defines 14 checks. Some checks (C04 and C11) have multiple
    # subchecks; aggregate them so the final summary still reports exactly 14 IDs.
    catalog=raw["dq_checks_catalog"][["check_id","check_name","severity"]].drop_duplicates("check_id")
    aggregate=[]
    for _, spec in catalog.iterrows():
        group=subchecks[subchecks["check_id"].eq(spec["check_id"])]
        if group.empty:
            status="NOT_RUN"; count=0; detail="No execution result generated"
        else:
            statuses=set(group["status"])
            status="FAIL" if "FAIL" in statuses else ("PENDING_SQL_RUNTIME" if any(str(x).startswith("PENDING") for x in statuses) else ("PASS" if statuses=={"PASS"} else "NOT_RUN"))
            count=int(group["bad_row_count"].sum())
            detail=" | ".join(dict.fromkeys(group["detail"].astype(str)))
        aggregate.append({"check_id":spec["check_id"],"check_name":spec["check_name"],"severity":spec["severity"],
                          "status":status,"bad_row_count":count,"detail":detail})
    summary=pd.DataFrame(aggregate)
    summary.to_csv(out/"dq_results.csv",index=False)
    if bad_rows:
        # Preserve a heterogeneous row-level evidence file by normalizing columns.
        allcols=sorted(set().union(*(set(x.columns) for x in bad_rows)))
        row_records=[]
        for frame in bad_rows:
            row_records.extend(frame.to_dict(orient="records"))
        pd.DataFrame(row_records,columns=allcols).to_csv(out/"dq_bad_rows.csv",index=False)
    else:
        pd.DataFrame(columns=["check_id","check_name"]).to_csv(out/"dq_bad_rows.csv",index=False)
    (out/"dq_summary.json").write_text(json.dumps({
        "run_at":now.isoformat(),"checks_total":len(summary),
        "pass":int((summary.status=="PASS").sum()),
        "fail":int((summary.status=="FAIL").sum()),
        "pending":int(summary.status.str.startswith("PENDING").sum()),
        "overall":"PASS" if (summary.status.isin(["PASS","PENDING_SQL_RUNTIME"]).all()) else "FAIL"
    },indent=2),encoding="utf-8")
    print(summary[["check_id","check_name","status","bad_row_count"]].to_string(index=False))
    print(f"\nWrote {out/'dq_results.csv'} and {out/'dq_bad_rows.csv'}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
