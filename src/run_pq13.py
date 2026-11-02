from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "clean"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

def read(name):
    return pd.read_csv(DATA / name)

hc = read("fact_headcount_monthly.csv")
hc["month"] = pd.to_datetime(hc["month_start_date"]).dt.to_period("M").dt.to_timestamp()
hc = hc.groupby(["department_id", "month"], as_index=False).agg(
    headcount_start=("headcount_start", "max"),
    headcount_end=("headcount_end", "max"),
    hires=("hires", "sum"), exits=("exits", "sum"),
    voluntary_exits=("voluntary_exits", "sum"),
    attrition_rate_monthly_pct=("attrition_rate_monthly_pct", "mean")
)

pay = read("fact_payroll.csv")
pay["month"] = pd.to_datetime(pay["period_end_date"]).dt.to_period("M").dt.to_timestamp()
pay = pay.groupby(["department_id", "month"], as_index=False).agg(
    gross_pay=("gross_pay", "sum"),
    employer_cost=("employer_cost", "sum"),
    employees_paid=("employee_id", "nunique"),
    overtime_hours_paid=("overtime_hours_paid", "sum"),
    overtime_cost=("overtime_pay", "sum")
)

att = read("fact_attendance_monthly.csv")
att["month"] = pd.to_datetime(att["period_end_date"]).dt.to_period("M").dt.to_timestamp()
att["weighted_attendance"] = att["attendance_rate"] * att["scheduled_days"]
att = att.groupby(["department_id", "month"], as_index=False).agg(
    scheduled_days=("scheduled_days", "sum"),
    present_days=("present_days", "sum"),
    attendance_overtime_hours=("overtime_hours", "sum"),
    weighted_attendance=("weighted_attendance", "sum")
)
att["attendance_rate"] = (
    att["weighted_attendance"] / att["scheduled_days"].replace(0, pd.NA)
)
att = att.drop(columns=["weighted_attendance"])

leave = read("fact_leave.csv")
leave = leave[leave["status"].str.lower().eq("approved")].copy()
leave["month"] = pd.to_datetime(leave["start_date"]).dt.to_period("M").dt.to_timestamp()
emp = read("dim_employee.csv")[["employee_id", "department_id", "valid_from", "valid_to"]].copy()
emp["valid_from"] = pd.to_datetime(emp["valid_from"], errors="coerce")
emp["valid_to"] = pd.to_datetime(emp["valid_to"], errors="coerce")
leave["start_date"] = pd.to_datetime(leave["start_date"])
leave = leave.merge(emp, on="employee_id", how="left")
leave = leave[
    leave["valid_from"].isna() |
    ((leave["start_date"] >= leave["valid_from"]) &
     (leave["valid_to"].isna() | (leave["start_date"] <= leave["valid_to"])))
]
leave = leave.groupby(["department_id", "month"], as_index=False).agg(
    approved_leave_days=("days", "sum"),
    approved_leave_requests=("leave_request_id", "nunique")
)

result = hc.merge(pay, on=["department_id", "month"], how="inner")
result = result.merge(att, on=["department_id", "month"], how="left")
result = result.merge(leave, on=["department_id", "month"], how="left")
result[["approved_leave_days", "approved_leave_requests"]] = result[
    ["approved_leave_days", "approved_leave_requests"]
].fillna(0)
result["leave_days_per_head"] = result["approved_leave_days"] / result["headcount_end"].replace(0, pd.NA)
result["overtime_cost_pct_employer_cost"] = (
    result["overtime_cost"] / result["employer_cost"].replace(0, pd.NA) * 100
)
result["cost_per_head"] = result["employer_cost"] / result["employees_paid"].replace(0, pd.NA)
result["attrition_rate_pct"] = result["attrition_rate_monthly_pct"]
result = result.sort_values(["month", "department_id"])
result.to_csv(OUT / "pq13_department_month_impact.csv", index=False)

dept = result.groupby("department_id", as_index=False).agg(
    avg_headcount=("headcount_end", "mean"),
    total_employer_cost=("employer_cost", "sum"),
    total_overtime_cost=("overtime_cost", "sum"),
    total_leave_days=("approved_leave_days", "sum"),
    total_exits=("exits", "sum"),
    avg_monthly_attrition_pct=("attrition_rate_pct", "mean"),
    avg_leave_days_per_head=("leave_days_per_head", "mean")
)
dept = dept.merge(read("dim_department.csv")[["department_id", "department_name"]], on="department_id", how="left")
dept.to_csv(OUT / "pq13_department_comparison.csv", index=False)

print("PQ-13 analysis generated")
print(f"Department-month rows: {len(result)}")
print(f"Period: {result.month.min():%Y-%m} to {result.month.max():%Y-%m}")
print(f"Employer cost: {result.employer_cost.sum():,.2f}")
print(f"Overtime cost: {result.overtime_cost.sum():,.2f}")
print(f"Approved leave days: {result.approved_leave_days.sum():,.2f}")
print(dept.sort_values("total_employer_cost", ascending=False).to_string(index=False))


