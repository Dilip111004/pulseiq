#!/usr/bin/env python3
"""PulseIQ PQ-01 ETL: reproducible CSV ingestion, contract validation and quarantine.

Uses pandas only. Raw files are never modified. Contract-specific validation is applied
where official data_contracts exist; other tables receive data-dictionary type checks,
primary-key checks, and duplicate-row checks. Cross-table business checks belong to PQ-03.
"""
from __future__ import annotations
import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PKS = {
    "dim_date": ["date_key"], "dim_employee": ["employee_key"],
    "dim_department": ["department_id"], "dim_role": ["role_id"],
    "dim_location": ["work_location"], "dim_leave_type": ["leave_type_code"],
    "dim_account": ["account_code"], "dim_client": ["client_id"],
    "dim_vendor": ["vendor_id"], "dim_team": ["team_id"], "dim_sprint": ["sprint_id"],
    "fact_payroll": ["payroll_item_id"], "fact_attendance_monthly": ["attendance_fact_id"],
    "fact_leave": ["leave_request_id"], "fact_headcount_monthly": ["date_key", "department_id"],
    "fact_ledger": ["line_id"], "fact_invoice": ["invoice_id"],
    "fact_invoice_payment": ["payment_id"], "fact_expense": ["expense_id"],
    "fact_task": ["task_id"], "fact_anomaly": ["result_id"],
    "fact_attrition_risk": ["prediction_id"], "fact_forecast": ["forecast_id"],
    "budget_payroll_dept_month": ["department_id", "month"],
    "kpi_targets": ["month", "department_id"],
}
FEED_TABLE = {
    "AI anomaly results (fact_anomaly)": "fact_anomaly",
    "AI attrition risk (fact_attrition_risk)": "fact_attrition_risk",
    "AI forecast (fact_forecast)": "fact_forecast",
    "Task board (fact_task)": "fact_task",
}
ID_PATTERNS = {
    "fact_anomaly.result_id": r"^AN-\d{4}$",
    "fact_attrition_risk.prediction_id": r"^AR-\d{4}$",
    "fact_forecast.forecast_id": r"^FC-\d{4}$",
    "fact_task.task_id": r"^TASK-\d{5}$",
}

def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False, keep_default_na=True)

def blank(v) -> bool:
    return pd.isna(v) or (isinstance(v, str) and not v.strip())

def numeric(v):
    try:
        x = pd.to_numeric(pd.Series([v]), errors="coerce").iloc[0]
        return None if pd.isna(x) else float(x)
    except Exception:
        return None

def parse_date(v):
    if blank(v):
        return None
    try:
        x = pd.to_datetime(v, errors="coerce")
        return None if pd.isna(x) else x
    except Exception:
        return None

def load_all(raw_dir: Path):
    frames = {}
    for path in sorted(raw_dir.glob("*.csv")):
        frames[path.stem] = read_csv(path)
    return frames

def contract_errors(frames, contracts):
    """Return row-level contract violations, preserving all reasons per source row."""
    from collections import defaultdict
    issues = {}
    employees = set(frames.get("dim_employee", pd.DataFrame()).get("employee_id", pd.Series(dtype=str)).dropna().astype(str))
    dim_emp = frames.get("dim_employee", pd.DataFrame())
    if not dim_emp.empty and {"is_current", "employment_status", "employee_id"}.issubset(dim_emp.columns):
        active = set(dim_emp.loc[(dim_emp["is_current"].astype(str) == "Y") &
                                 (dim_emp["employment_status"].astype(str) == "Active"), "employee_id"].dropna().astype(str))
    else:
        active = employees
    departments = set(frames.get("dim_department", pd.DataFrame()).get("department_id", pd.Series(dtype=str)).dropna().astype(str))
    teams = set(frames.get("dim_team", pd.DataFrame()).get("team_id", pd.Series(dtype=str)).dropna().astype(str))
    sprints = frames.get("dim_sprint", pd.DataFrame())
    sprint_ids = set(sprints.get("sprint_id", pd.Series(dtype=str)).dropna().astype(str))
    sprint_end = dict(zip(sprints.get("sprint_id", pd.Series(dtype=str)).astype(str),
                          sprints.get("end_date", pd.Series(dtype=str)).astype(str)))
    attendance_ids = set(frames.get("fact_attendance_monthly", pd.DataFrame()).get("attendance_fact_id", pd.Series(dtype=str)).dropna().astype(str))
    payroll_ids = set(frames.get("fact_payroll", pd.DataFrame()).get("payroll_item_id", pd.Series(dtype=str)).dropna().astype(str))
    attendance_suffixes = {x.split("-")[-1] for x in attendance_ids}

    for feed, group in contracts.groupby("feed", sort=False):
        table = FEED_TABLE.get(feed)
        if not table or table not in frames:
            continue
        df = frames[table]
        reasons = defaultdict(list)
        def add(mask, reason):
            if not isinstance(mask, pd.Series):
                mask = pd.Series(mask, index=df.index)
            mask = mask.fillna(False).astype(bool)
            for idx in df.index[mask]:
                reasons[int(idx)].append(reason)
        for _, c in group.iterrows():
            base_col = str(c["column_name"])
            cols = [f"top_reason_{i}" for i in (1,2,3)] if base_col == "top_reason_1..3" else [base_col]
            missing = [col for col in cols if col not in df.columns]
            if missing:
                for i in df.index:
                    reasons[int(i)].append("SCHEMA_MISSING_COLUMN:" + ",".join(missing))
                continue
            for col in cols:
                s = df[col]
                blank_mask = s.isna() | s.astype(str).str.strip().eq("")
                nullable = str(c["nullable"]).strip().lower() in {"yes","y","true"}
                if not nullable: add(blank_mask, f"REQUIRED:{col}")
                typ = str(c["data_type"]).lower()
                nonblank = ~blank_mask
                if typ in {"date","timestamp"}:
                    parsed = pd.to_datetime(s, errors="coerce", utc=(typ=="timestamp"))
                    add(nonblank & parsed.isna(), f"INVALID_{typ.upper()}:{col}")
                elif typ.startswith("decimal") or typ in {"int","integer"}:
                    nums = pd.to_numeric(s, errors="coerce")
                    add(nonblank & nums.isna(), f"INVALID_NUMBER:{col}")
                    if typ in {"int","integer"}: add(nonblank & nums.notna() & ((nums % 1) != 0), f"NOT_INTEGER:{col}")
                rule = str(c["rule_or_allowed_values"]).strip()
                if "unique" in rule.lower():
                    add(s.astype(str).duplicated(keep="first"), f"DUPLICATE:{col}")
                pattern = ID_PATTERNS.get(f"{table}.{col}")
                if pattern: add(nonblank & ~s.astype(str).str.fullmatch(pattern), f"INVALID_ID_FORMAT:{col}")
                if col == "source_dataset":
                    add(nonblank & ~s.astype(str).isin({"attendance_monthly_features","payroll_monthly_features"}), "INVALID_SOURCE_DATASET")
                elif col == "flagged":
                    add(nonblank & ~s.astype(str).isin({"Y","N"}), "INVALID_FLAGGED_VALUE")
                elif col == "risk_band":
                    add(nonblank & ~s.astype(str).isin({"Low","Medium","High"}), "INVALID_RISK_BAND")
                elif col == "metric":
                    add(nonblank & ~s.astype(str).isin({"headcount_end","attrition_rate_monthly_pct"}), "INVALID_FORECAST_METRIC")
                elif col == "task_type":
                    add(nonblank & ~s.astype(str).isin({"Feature","Bug","Chore","Spike"}), "INVALID_TASK_TYPE")
                elif col == "priority":
                    add(nonblank & ~s.astype(str).isin({"P1","P2","P3","P4"}), "INVALID_PRIORITY")
                elif col == "status":
                    add(nonblank & ~s.astype(str).isin({"Done","In Progress","Blocked","To Do","Cancelled"}), "INVALID_TASK_STATUS")
                elif col == "story_points":
                    nums = pd.to_numeric(s, errors="coerce")
                    add(nonblank & ~nums.isin([1,2,3,5,8,13]), "INVALID_STORY_POINTS")
                elif col in {"anomaly_score","risk_score_12m"}:
                    nums = pd.to_numeric(s, errors="coerce")
                    add(nonblank & nums.notna() & ~nums.between(0,1), f"OUT_OF_RANGE:{col}")
                elif col in {"forecast_value","lower_80","upper_80"}:
                    nums = pd.to_numeric(s, errors="coerce")
                    add(nonblank & nums.notna() & (nums < 0), f"NEGATIVE:{col}")
                elif col == "reopened_count":
                    nums = pd.to_numeric(s, errors="coerce")
                    add(nonblank & nums.notna() & ((nums < 0) | ((nums % 1) != 0)), "INVALID_REOPENED_COUNT")
                elif col == "trained_through":
                    add(nonblank & ~s.astype(str).str.fullmatch(r"\d{4}-\d{2}"), "INVALID_TRAINED_THROUGH")

        if table == "fact_anomaly":
            s = df["employee_id"].astype(str)
            add(~s.isin(employees), "UNKNOWN_EMPLOYEE_ID")
            src = df["source_dataset"].astype(str)
            rid = df["record_id"].astype(str)
            suffix = rid.str.extract(r"-(\d+)$", expand=False)
            is_payroll = src.eq("payroll_monthly_features")
            is_attendance = src.eq("attendance_monthly_features")
            add(is_payroll & ~rid.isin(payroll_ids), "UNKNOWN_SOURCE_RECORD_ID")
            # Upstream attendance IDs use AF-xxxxx; supplied attendance facts use FA-xxxxx.
            add(is_attendance & (~rid.str.startswith("AF-") | ~suffix.isin(attendance_suffixes)), "UNKNOWN_SOURCE_RECORD_ID")
            add(is_attendance & df["money_at_risk"].notna(), "MONEY_AT_RISK_ON_ATTENDANCE_ROW")
        elif table == "fact_attrition_risk":
            add(~df["employee_id"].astype(str).isin(active), "EMPLOYEE_NOT_CURRENT_ACTIVE")
            add(~df["department_id"].astype(str).isin(departments), "UNKNOWN_DEPARTMENT_ID")
            dates = pd.to_datetime(df["as_of_date"], errors="coerce").dt.strftime("%Y-%m-%d")
            if dates.notna().any():
                batch_date = dates.mode(dropna=True).iloc[0]
                add(dates.notna() & dates.ne(batch_date), "INCONSISTENT_BATCH_AS_OF_DATE")
        elif table == "fact_forecast":
            dep = df["department_id"].astype(str)
            add(~dep.eq("ALL") & ~dep.isin(departments), "UNKNOWN_DEPARTMENT_ID")
            fm = pd.to_datetime(df["forecast_month"], errors="coerce")
            add(fm.notna() & fm.dt.day.ne(1), "FORECAST_MONTH_NOT_FIRST_DAY")
            lo = pd.to_numeric(df["lower_80"], errors="coerce")
            val = pd.to_numeric(df["forecast_value"], errors="coerce")
            hi = pd.to_numeric(df["upper_80"], errors="coerce")
            add(lo.notna() & val.notna() & lo.gt(val), "LOWER_BOUND_ABOVE_FORECAST")
            add(hi.notna() & val.notna() & hi.lt(val), "UPPER_BOUND_BELOW_FORECAST")
        elif table == "fact_task":
            add(~df["team_id"].astype(str).isin(teams), "UNKNOWN_TEAM_ID")
            add(~df["sprint_id"].astype(str).isin(sprint_ids), "UNKNOWN_SPRINT_ID")
            add(~df["assignee_employee_id"].astype(str).isin(employees), "UNKNOWN_ASSIGNEE_EMPLOYEE_ID")
            status = df["status"].astype(str)
            created = pd.to_datetime(df["created_date"], errors="coerce")
            started = pd.to_datetime(df["started_date"], errors="coerce")
            completed = pd.to_datetime(df["completed_date"], errors="coerce")
            add(started.isna() & status.ne("To Do"), "STARTED_DATE_NULL_ONLY_ALLOWED_FOR_TODO")
            add(created.notna() & started.notna() & created.gt(started), "CREATED_AFTER_STARTED")
            add(status.eq("Done") & completed.isna(), "DONE_WITHOUT_COMPLETION_DATE")
            add(completed.notna() & started.notna() & completed.lt(started), "COMPLETED_BEFORE_STARTED")
            due = pd.to_datetime(df["due_date"], errors="coerce")
            ends = df["sprint_id"].astype(str).map(sprint_end)
            ends = pd.to_datetime(ends, errors="coerce")
            add(due.notna() & ends.notna() & due.dt.normalize().ne(ends.dt.normalize()), "DUE_DATE_NOT_SPRINT_END")
        issues[table] = {i: sorted(set(rs)) for i,rs in reasons.items() if rs}
    return {k:v for k,v in issues.items() if v}

def baseline_errors(frames, dictionary):
    """Data-dictionary parseability and primary-key checks for tables without contracts."""
    errors = {}
    type_map = {}
    for sheet_name, group in dictionary.groupby("sheet", sort=False):
        type_map[sheet_name] = dict(zip(group["column"], group["data_type"]))
    for table, df in frames.items():
        if table in {"data_dictionary", "data_contracts", "metric_dictionary", "dq_checks_catalog"}:
            continue
        per_row = [[] for _ in range(len(df))]
        types = type_map.get(table, {})
        for col, dtype in types.items():
            if col not in df.columns: continue
            series = df[col]
            nonblank = ~series.isna()
            if dtype == "integer":
                vals = pd.to_numeric(series, errors="coerce")
                bad = nonblank & (vals.isna() | ((vals % 1) != 0))
            elif dtype == "decimal":
                vals = pd.to_numeric(series, errors="coerce")
                bad = nonblank & vals.isna()
            elif dtype == "date":
                vals = pd.to_datetime(series, errors="coerce")
                # SCD2 current versions use 9999-12-31 as an open-ended valid_to sentinel.
                sentinel_ok = series.astype(str).eq("9999-12-31")
                bad = nonblank & vals.isna() & ~sentinel_ok
            elif dtype == "timestamp":
                vals = pd.to_datetime(series, errors="coerce", utc=True)
                bad = nonblank & vals.isna()
            else:
                bad = pd.Series(False, index=series.index)
            for i in bad[bad].index:
                per_row[i].append(f"TYPE_PARSE_ERROR:{col}:{dtype}")
        keys = PKS.get(table)
        if keys and all(k in df.columns for k in keys):
            bad_key = df[keys].isna().any(axis=1)
            dup = df.duplicated(keys, keep="first")
            for i in df.index[bad_key]: per_row[i].append("NULL_PRIMARY_KEY")
            for i in df.index[dup]: per_row[i].append("DUPLICATE_PRIMARY_KEY")
        dup_full = df.duplicated(keep="first")
        for i in df.index[dup_full]: per_row[i].append("DUPLICATE_FULL_ROW")
        found = {i: sorted(set(r)) for i,r in enumerate(per_row) if r}
        if found: errors[table] = found
    return errors

def schema_drift_errors(frames, dictionary):
    """Detect unexpected/missing columns using the supplied data dictionary as the full schema.

    Policy: fail the ETL run before overwriting clean outputs. This is safer than silently
    ignoring a new field or guessing its meaning. Raw source files remain untouched.
    """
    expected_by_table = {}
    if not dictionary.empty and {"sheet", "column"}.issubset(dictionary.columns):
        for table, group in dictionary.groupby("sheet", sort=False):
            expected_by_table[str(table)] = set(group["column"].dropna().astype(str))
    # The data dictionary cannot describe its own schema; define that metadata table explicitly.
    expected_by_table.setdefault("data_dictionary", {
        "sheet", "column", "data_type", "description", "null_count",
        "null_percent", "distinct_values", "example"
    })
    errors = {}
    for table, df in frames.items():
        expected = expected_by_table.get(table)
        if expected is None:
            errors[table] = ["NO_DATA_DICTIONARY_SCHEMA"]
            continue
        actual = set(map(str, df.columns))
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        if missing or unexpected:
            reasons = []
            if missing:
                reasons.append("MISSING_COLUMNS:" + ",".join(missing))
            if unexpected:
                reasons.append("UNEXPECTED_COLUMNS:" + ",".join(unexpected))
            errors[table] = reasons
    return errors


def business_errors(frames):
    """Supplement incomplete official contracts with explicit critical data rules."""
    from collections import defaultdict
    out={}
    emp=frames.get("dim_employee",pd.DataFrame())
    emp_ids=set(emp.get("employee_id",pd.Series(dtype=str)).dropna().astype(str))
    emp_keys=set(emp.get("employee_key",pd.Series(dtype=str)).dropna().astype(str))
    key_to_id=dict(zip(emp.get("employee_key",pd.Series(dtype=str)).astype(str),
                       emp.get("employee_id",pd.Series(dtype=str)).astype(str)))
    # Payroll: keep the first row per employee/run, quarantine extra occurrences and orphan/mismatched keys.
    p=frames.get("fact_payroll")
    if p is not None:
        r=defaultdict(list)
        def addp(mask, reason):
            mask=pd.Series(mask,index=p.index).fillna(False).astype(bool)
            for i in p.index[mask]: r[int(i)].append(reason)
        addp(p.duplicated(["employee_id","run_id"],keep="first"),"DUPLICATE_EMPLOYEE_RUN")
        addp(~p["employee_id"].astype(str).isin(emp_ids),"UNKNOWN_EMPLOYEE_ID")
        addp(~p["employee_key"].astype(str).isin(emp_keys),"UNKNOWN_EMPLOYEE_KEY")
        addp(p["employee_key"].astype(str).map(key_to_id).fillna("__MISSING__").ne(p["employee_id"].astype(str)),
             "EMPLOYEE_ID_KEY_MISMATCH")
        if r: out["fact_payroll"]={i:sorted(set(rs)) for i,rs in r.items()}
    # Attendance: rows after the latest employee exit month are not valid workforce attendance.
    a=frames.get("fact_attendance_monthly")
    if a is not None and not emp.empty:
        current=emp[emp["is_current"].astype(str).eq("Y")][["employee_id","exit_date"]].drop_duplicates("employee_id")
        x=a.copy(); x["_period"]=pd.to_datetime(x["period_end_date"],errors="coerce")
        current["_exit"]=pd.to_datetime(current["exit_date"],errors="coerce")
        x=x.merge(current[["employee_id","_exit"]],on="employee_id",how="left")
        mask=x["_exit"].notna()&x["_period"].notna()&(x["_period"].dt.to_period("M")>x["_exit"].dt.to_period("M"))
        if mask.any(): out["fact_attendance_monthly"]={int(i):["ATTENDANCE_AFTER_EXIT_MONTH"] for i in x.index[mask]}
    # Leave requests with reversed date ranges.
    l=frames.get("fact_leave")
    if l is not None:
        mask=pd.to_datetime(l["end_date"],errors="coerce")<pd.to_datetime(l["start_date"],errors="coerce")
        if mask.any(): out["fact_leave"]={int(i):["LEAVE_END_BEFORE_START"] for i in l.index[mask]}
    # Invoice arithmetic: quarantine impossible balances.
    inv=frames.get("fact_invoice")
    if inv is not None:
        mask=(pd.to_numeric(inv["amount_paid"],errors="coerce")>pd.to_numeric(inv["total_amount"],errors="coerce")+.01)|(pd.to_numeric(inv["balance_due"],errors="coerce")<-.01)
        if mask.any(): out["fact_invoice"]={int(i):["INVOICE_BALANCE_INVALID"] for i in inv.index[mask]}
    # Expense arithmetic.
    ex=frames.get("fact_expense")
    if ex is not None:
        mask=(pd.to_numeric(ex["total_amount"],errors="coerce")-(pd.to_numeric(ex["amount_excl_gst"],errors="coerce")+pd.to_numeric(ex["gst_amount"],errors="coerce"))).abs()>.01
        if mask.any(): out["fact_expense"]={int(i):["EXPENSE_TOTAL_GST_MISMATCH"] for i in ex.index[mask]}
    # Payments referencing an invoice quarantined for impossible arithmetic must also be quarantined,
    # otherwise the warehouse would contain an orphan invoice key.
    inv=frames.get("fact_invoice"); payments=frames.get("fact_invoice_payment")
    if inv is not None and payments is not None:
        invalid_inv=set(inv.loc[(pd.to_numeric(inv["amount_paid"],errors="coerce")>pd.to_numeric(inv["total_amount"],errors="coerce")+.01) |
                                (pd.to_numeric(inv["balance_due"],errors="coerce")<-.01),"invoice_id"].astype(str))
        mask=payments["invoice_id"].astype(str).isin(invalid_inv)
        if mask.any(): out["fact_invoice_payment"]={int(i):["PAYMENT_REFERENCES_REJECTED_INVOICE"] for i in payments.index[mask]}
    return out

def repair_employee_history(df):
    """Clip an overlapping SCD2 validity end to the day before the next version starts.

    This deterministic repair is logged with old/new values; the raw source remains untouched.
    """
    from datetime import date, timedelta
    out=df.copy()
    events=[]
    if not {"employee_id","valid_from","valid_to","employee_key"}.issubset(out.columns):
        return out,events
    for emp_id, group in out.groupby("employee_id",sort=False):
        ordered=group.assign(_from=pd.to_datetime(group["valid_from"],errors="coerce")).sort_values(["_from","employee_key"])
        idxs=list(ordered.index)
        for pos in range(len(idxs)-1):
            idx,next_idx=idxs[pos],idxs[pos+1]
            old_end=str(out.at[idx,"valid_to"])
            try:
                end_date=date.fromisoformat(old_end[:10])
                next_start=date.fromisoformat(str(out.at[next_idx,"valid_from"])[:10])
            except Exception:
                continue
            if end_date>=next_start:
                new_end=(next_start-timedelta(days=1)).isoformat()
                events.append({"table_name":"dim_employee","source_row_number":int(idx)+2,
                               "employee_key":out.at[idx,"employee_key"],"employee_id":emp_id,
                               "column_name":"valid_to","old_value":old_end,"new_value":new_end,
                               "reason":"SCD2_OVERLAP_CLIPPED_TO_DAY_BEFORE_NEXT_VALID_FROM"})
                out.at[idx,"valid_to"]=new_end
    return out,events

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default="data/raw")
    ap.add_argument("--clean-dir", default="data/clean")
    ap.add_argument("--rejected-dir", default="data/rejected")
    ap.add_argument("--log-dir", default="logs")
    args = ap.parse_args()
    raw_dir, clean_dir, reject_dir, log_dir = map(Path, [args.raw_dir,args.clean_dir,args.rejected_dir,args.log_dir])
    for d in (clean_dir,reject_dir,log_dir): d.mkdir(parents=True,exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    logging.basicConfig(level=logging.INFO, format="%(asctime)sZ %(levelname)s %(message)s")
    started = datetime.now(timezone.utc)
    frames = load_all(raw_dir)
    contracts = frames.get("data_contracts", pd.DataFrame())
    dictionary = frames.get("data_dictionary", pd.DataFrame())
    drift = schema_drift_errors(frames, dictionary)
    if drift:
        drift_rows = []
        for table, reasons in sorted(drift.items()):
            drift_rows.append({"table_name": table, "schema_drift_reasons": ";".join(reasons)})
        pd.DataFrame(drift_rows).to_csv(log_dir / "etl_schema_drift.csv", index=False)
        finished = datetime.now(timezone.utc)
        run_summary = {
            "run_id": run_id, "started_at": started.isoformat(), "finished_at": finished.isoformat(),
            "status": "FAILED_SCHEMA_DRIFT", "tables": len(frames),
            "input_rows": sum(len(df) for df in frames.values()), "clean_rows": None,
            "rejected_rows": None, "row_accounting_pass": False,
            "tables_with_rejects": None,
            "failure_reason": "Schema drift detected; clean outputs were not overwritten. See etl_schema_drift.csv."
        }
        pd.DataFrame([run_summary]).to_csv(log_dir / "etl_run_log.csv", index=False)
        (log_dir / "etl_run_summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8")
        print(json.dumps(run_summary, indent=2), file=sys.stderr)
        return 2
    # Remove a stale schema-drift artifact from a previous failed run once this run passes.
    stale_drift_log = log_dir / "etl_schema_drift.csv"
    if stale_drift_log.exists():
        stale_drift_log.unlink()
    c_errors = contract_errors(frames, contracts)
    b_errors = baseline_errors(frames, dictionary)
    x_errors = business_errors(frames)
    all_errors = {}
    for t in set(c_errors) | set(b_errors) | set(x_errors):
        combined = dict(b_errors.get(t, {}))
        for source in (c_errors, x_errors):
            for i, reasons in source.get(t, {}).items():
                combined[i] = sorted(set(combined.get(i, []) + reasons))
        all_errors[t] = combined
    logs = []
    transform_events = []
    for table, df in sorted(frames.items()):
        row_errors = all_errors.get(table, {})
        bad_idx = set(row_errors)
        rejected = df.loc[[i for i in range(len(df)) if i in bad_idx]].copy()
        if not rejected.empty:
            rejected.insert(0, "source_table", table)
            rejected.insert(1, "source_row_number", [i + 2 for i in rejected.index])
            rejected["reject_reasons"] = [ ";".join(row_errors[i]) for i in rejected.index]
        clean = df.loc[[i for i in range(len(df)) if i not in bad_idx]].copy()
        if table == "dim_employee":
            clean, events = repair_employee_history(clean)
            transform_events.extend(events)
        clean.to_csv(clean_dir / f"{table}.csv", index=False)
        rejected.to_csv(reject_dir / f"{table}_rejected.csv", index=False)
        logs.append({
            "run_id":run_id, "table_name":table, "input_rows":len(df),
            "clean_rows":len(clean), "rejected_rows":len(rejected),
            "accounting_pass":len(df)==len(clean)+len(rejected),
            "reject_reasons":json.dumps(pd.Series([r for rs in row_errors.values() for r in rs]).value_counts().to_dict(), sort_keys=True),
        })
        logging.info("%s input=%d clean=%d rejected=%d", table,len(df),len(clean),len(rejected))
    finished = datetime.now(timezone.utc)
    run_summary = {
        "run_id":run_id,"started_at":started.isoformat(),"finished_at":finished.isoformat(),
        "status":"SUCCESS" if all(x["accounting_pass"] for x in logs) else "FAILED",
        "tables":len(frames),"input_rows":sum(x["input_rows"] for x in logs),
        "clean_rows":sum(x["clean_rows"] for x in logs),
        "rejected_rows":sum(x["rejected_rows"] for x in logs),
        "row_accounting_pass":all(x["accounting_pass"] for x in logs),
        "tables_with_rejects":sum(x["rejected_rows"]>0 for x in logs),
    }
    pd.DataFrame(logs).to_csv(log_dir / "etl_table_log.csv", index=False)
    pd.DataFrame(transform_events, columns=["table_name","source_row_number","employee_key","employee_id","column_name","old_value","new_value","reason"]).to_csv(log_dir / "etl_transform_log.csv", index=False)
    pd.DataFrame([run_summary]).to_csv(log_dir / "etl_run_log.csv", index=False)
    (log_dir / "etl_run_summary.json").write_text(json.dumps(run_summary,indent=2),encoding="utf-8")
    print(json.dumps(run_summary,indent=2))
    return 0 if run_summary["row_accounting_pass"] else 2

if __name__ == "__main__":
    sys.exit(main())
