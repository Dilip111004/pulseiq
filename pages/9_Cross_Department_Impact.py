import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
st.set_page_config(page_title="Cross-Department Impact", layout="wide")
st.title("Cross-Department Impact View")
st.caption("Department-month analysis - April 2025 to September 2026 - Fictional workforce data")
file = ROOT / "outputs" / "pq13_department_month_impact.csv"
if not file.exists():
    st.error("Run: python src/run_pq13.py")
    st.stop()
df = pd.read_csv(file, parse_dates=["month"])
dept = pd.read_csv(ROOT / "outputs" / "pq13_department_comparison.csv")
months = sorted(df.month.dropna().unique())
selected = st.selectbox("Month", months, format_func=lambda x: pd.Timestamp(x).strftime("%B %Y"))
view = df[df.month.eq(selected)]
c1,c2,c3,c4 = st.columns(4)
c1.metric("Employer cost", f"\u20b9{view.employer_cost.sum():,.0f}")
c2.metric("Overtime cost", f"\u20b9{view.overtime_cost.sum():,.0f}")
c3.metric("Approved leave days", f"{view.approved_leave_days.sum():,.0f}")
c4.metric("Exits", f"{view.exits.sum():,.0f}")
st.subheader("Department-month detail")
st.dataframe(view, use_container_width=True, hide_index=True)
st.subheader("Department comparison: cost and attrition")
fig = px.scatter(dept, x="total_employer_cost", y="avg_monthly_attrition_pct",
                 size="total_overtime_cost", color="department_name",
                 hover_name="department_name",
                 labels={"total_employer_cost":"Total employer cost (\u20b9)",
                         "avg_monthly_attrition_pct":"Average monthly attrition (%)",
                         "total_overtime_cost":"Overtime cost (\u20b9)"})
st.plotly_chart(fig, use_container_width=True)
st.subheader("Department summary")
st.dataframe(dept, use_container_width=True, hide_index=True)
st.caption("Leave requests are assigned to the employee's department effective on the leave start date and grouped by start month. Leave days are summed from approved requests.")

