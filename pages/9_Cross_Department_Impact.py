import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

st.set_page_config(page_title="Cross-Department Impact", layout="wide")
st.title("PQ-13 | Cross-Department Impact View")
st.caption("Department-month analysis | April 2025 to September 2026 | Fictional workforce data")

file = ROOT / "outputs" / "pq13_department_month_impact.csv"
dept_file = ROOT / "outputs" / "pq13_department_comparison.csv"
ref_file = ROOT / "reference" / "unlock_PQ-13_reference_summary_dept_month.csv"

if not file.exists() or not dept_file.exists():
    st.error("Run: python src/run_pq13.py")
    st.stop()

df = pd.read_csv(file, parse_dates=["month"])
dept = pd.read_csv(dept_file)

# --------------------------------------------------
# MONTH FILTER AND KPI SUMMARY
# --------------------------------------------------
months = sorted(df.month.dropna().unique())
selected = st.selectbox(
    "Month",
    months,
    format_func=lambda x: pd.Timestamp(x).strftime("%B %Y")
)
view = df[df.month.eq(selected)]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Employer cost", f"₹{view.employer_cost.sum():,.0f}")
c2.metric("Overtime cost", f"₹{view.overtime_cost.sum():,.0f}")
c3.metric("Approved leave days", f"{view.approved_leave_days.sum():,.0f}")
c4.metric("Exits", f"{view.exits.sum():,.0f}")

# --------------------------------------------------
# DEPARTMENT-MONTH DETAIL
# --------------------------------------------------
st.subheader("Department-month detail")
st.dataframe(view, use_container_width=True, hide_index=True)

# --------------------------------------------------
# DEPARTMENT COMPARISON
# --------------------------------------------------
st.subheader("Department comparison: cost, overtime and attrition")

fig = px.scatter(
    dept,
    x="total_employer_cost",
    y="avg_monthly_attrition_pct",
    size="total_overtime_cost",
    color="department_name",
    hover_name="department_name",
    hover_data={
        "total_employer_cost": ":,.2f",
        "total_overtime_cost": ":,.2f",
        "avg_monthly_attrition_pct": ":.2f",
        "total_exits": True
    },
    labels={
        "total_employer_cost": "Total employer cost (₹)",
        "avg_monthly_attrition_pct": "Average monthly attrition (%)",
        "total_overtime_cost": "Total overtime cost (₹)"
    },
    size_max=55
)
fig.update_layout(
    height=600,
    legend_title_text="Department"
)
st.plotly_chart(fig, use_container_width=True)

st.caption(
    "Bubble size represents overtime cost. This chart shows association, "
    "not proof that overtime causes employee attrition."
)

st.subheader("Department summary")
st.dataframe(dept, use_container_width=True, hide_index=True)

# --------------------------------------------------
# OFFICIAL REFERENCE RECONCILIATION
# --------------------------------------------------
st.divider()
st.subheader("Reference reconciliation")

if not ref_file.exists():
    st.warning(
        "Official reference file not found. Expected: "
        "reference/unlock_PQ-13_reference_summary_dept_month.csv"
    )
else:
    ref = pd.read_csv(ref_file)

    df["month"] = pd.to_datetime(df["month"])
    ref["month"] = pd.to_datetime(ref["month"])

    merged = df.merge(
        ref,
        on=["department_id", "month"],
        how="outer",
        suffixes=("_actual", "_reference"),
        indicator=True
    )

    matched = int((merged["_merge"] == "both").sum())
    unmatched = int((merged["_merge"] != "both").sum())

    checks = [
        ("Employer cost", "employer_cost_actual", "employer_cost_reference", 0.01),
        ("Gross pay", "gross_pay_actual", "gross_pay_reference", 0.01),
        ("Overtime cost", "overtime_cost", "overtime_pay", 0.01),
        ("Overtime hours", "overtime_hours_paid", "overtime_hours", 0.01),
        ("Employees paid", "employees_paid_actual", "employees_paid_reference", 0),
        ("Attendance rate", "attendance_rate_actual", "attendance_rate_reference", 0.0001),
        ("Ending headcount", "headcount_end_actual", "headcount_end_reference", 0),
        ("Hires", "hires_actual", "hires_reference", 0),
        ("Exits", "exits_actual", "exits_reference", 0),
        ("Attrition rate", "attrition_rate_monthly_pct_actual",
         "attrition_rate_monthly_pct_reference", 0.01),
        ("Cost per head", "cost_per_head_actual", "cost_per_head_reference", 0.01),
    ]

    results = []

    for label, actual_col, ref_col, tolerance in checks:
        valid = (
            (merged["_merge"] == "both")
            & merged[actual_col].notna()
            & merged[ref_col].notna()
        )
        differences = (
            merged.loc[valid, actual_col] -
            merged.loc[valid, ref_col]
        ).abs()

        mismatch_count = int((differences > tolerance).sum())

        results.append({
            "Metric": label,
            "Compared rows": int(valid.sum()),
            "Mismatches": mismatch_count,
            "Maximum difference": (
                float(differences.max()) if len(differences) else None
            ),
            "Tolerance": tolerance,
            "Status": "PASS" if mismatch_count == 0 and valid.sum() == matched else "CHECK"
        })

    results_df = pd.DataFrame(results)

    passed = int((results_df["Status"] == "PASS").sum())
    total_checks = len(results_df)

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Current records", len(df))
    r2.metric("Reference records", len(ref))
    r3.metric("Matched keys", f"{matched}/{len(ref)}")
    r4.metric("Metrics passed", f"{passed}/{total_checks}")

    if unmatched == 0 and passed == total_checks:
        st.success("All department-month keys and all 11 metric checks passed.")
    else:
        st.warning("Some reference reconciliation checks need attention.")

    st.dataframe(
        results_df,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Tolerance is applied to the absolute difference between current "
        "and reference values. Attendance tolerance is 0.0001."
    )

    attendance_diff = (
        merged["attendance_rate_actual"] -
        merged["attendance_rate_reference"]
    ).abs()

    st.markdown("**Attendance precision differences**")
    st.write(
        f"Maximum absolute difference: {attendance_diff.max():.8f}. "
        f"Records within 0.0001 tolerance: "
        f"{int((attendance_diff <= 0.0001).sum())}/{len(df)}."
    )

# --------------------------------------------------
# METHODOLOGY AND DIFFERENCE NOTES
# --------------------------------------------------
st.divider()
st.subheader("Methodology and reconciliation notes")

with st.expander("Aggregation and join methodology", expanded=True):
    st.markdown("""
    1. Headcount is aggregated to department-month grain.
    2. Payroll is aggregated to department-month grain before joining.
    3. Attendance is aggregated to department-month grain using
       scheduled-days-weighted attendance.
    4. Approved leave requests are assigned using the employee's
       effective department on the leave start date and grouped by
       leave start month.
    5. Each source is aggregated before joining to prevent
       row multiplication.
    6. Department ID and month are the common join keys.
    7. Headcount and payroll are inner-joined; attendance and leave
       are left-joined. Missing leave totals are filled with zero.
    """)

with st.expander("Metric definitions and difference explanations"):
    st.markdown("""
    - **Leave days per head:** Approved leave days divided by ending headcount.
    - **Cost per head:** Employer cost divided by employees paid.
    - **Attendance rate:** Scheduled-days-weighted attendance rate.
    - **Overtime cost:** Payroll overtime pay.
    - **Overtime share:** Overtime cost divided by employer cost, multiplied by 100.

    **Reference precision:** Attendance differences are retained rather
    than artificially adjusted. The reference stores attendance to four
    decimal places. All 198 records are within the accepted 0.0001
    absolute-difference tolerance. Cost per head is compared with a
    0.01 tolerance.

    **Join differences:** The reconciliation checks department-month keys
    and identifies unmatched keys. The current comparison has 198 matched
    keys and zero unmatched keys.
    """)

with st.expander("Does overtime cause attrition?"):
    st.markdown("""
    The comparison chart shows department-level overtime cost alongside
    average monthly attrition. It does not establish causation.

    Other possible explanations include:

    - Staffing shortages and workload pressure.
    - Seasonal demand and operational peaks.
    - Compensation and employee benefits.
    - Management practices and scheduling.
    - Department size, job mix and employee tenure.

    A causal conclusion would require employee-level or time-lagged
    analysis with relevant controls, or a suitable experimental design.
    """)

st.caption(
    "PQ-13 | Department-month grain | Reference: "
    "unlock_PQ-13_reference_summary_dept_month.csv"
)
