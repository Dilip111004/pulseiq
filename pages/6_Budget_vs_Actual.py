from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# --------------------------------------------------
# PulseIQ | Phase 2 | PQ-10 Budget vs Actual
# --------------------------------------------------

st.set_page_config(
    page_title="PulseIQ | Budget vs Actual",
    page_icon="📊",
    layout="wide",
)

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "outputs"
DATA = ROOT / "data" / "clean"
MIN_GROUP_SIZE = 5


@st.cache_data
def load_csv(filename):
    path = OUTPUTS / filename
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)


@st.cache_data
def load_departments():
    path = DATA / "dim_department.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if {"department_id", "department_name"}.issubset(df.columns):
        return df[["department_id", "department_name"]].drop_duplicates()
    return pd.DataFrame()


budget = load_csv("pq10_budget_vs_actual.csv")
kpis = load_csv("pq10_kpi_target_comparison.csv")
tasks = load_csv("pq10_task_sprint_target_comparison.csv")
departments = load_departments()

st.title("PulseIQ")
st.subheader("Budget vs Actual and KPI Targets")
st.caption(
    "Phase 2 | PQ-10 | Payroll budget variance, KPI target performance "
    "and departmental overspending."
)

if budget.empty:
    st.error("Budget data is missing. Check outputs/pq10_budget_vs_actual.csv.")
    st.stop()

required = {
    "month", "department_id", "budget_payroll_cost",
    "actual_employer_cost", "variance", "variance_pct",
    "budget_status", "group_size"
}
if not required.issubset(budget.columns):
    st.error("Budget CSV is missing required columns.")
    st.stop()

budget["month"] = pd.to_datetime(budget["month"], errors="coerce")
for col in [
    "budget_payroll_cost", "actual_employer_cost",
    "variance", "variance_pct", "group_size"
]:
    budget[col] = pd.to_numeric(budget[col], errors="coerce")

if not departments.empty:
    budget = budget.merge(departments, on="department_id", how="left")
else:
    budget["department_name"] = budget["department_id"]

budget["department_label"] = (
    budget["department_name"].fillna(budget["department_id"])
)

# --------------------------------------------------
# Filters
# --------------------------------------------------

st.sidebar.header("Dashboard Filters")

department_options = sorted(budget["department_label"].dropna().unique())
selected_departments = st.sidebar.multiselect(
    "Department",
    department_options,
    default=department_options,
)

valid_months = budget["month"].dropna()
min_month = valid_months.min().date()
max_month = valid_months.max().date()

date_range = st.sidebar.date_input(
    "Month range",
    value=(min_month, max_month),
    min_value=min_month,
    max_value=max_month,
)

if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_month, max_month

filtered = budget[
    budget["month"].dt.date.between(start_date, end_date)
    & budget["department_label"].isin(selected_departments)
].copy()

if filtered.empty:
    st.warning("No budget records match the selected filters.")
    st.stop()

# --------------------------------------------------
# KPI cards
# --------------------------------------------------

available = filtered.dropna(subset=["variance", "actual_employer_cost"])
total_budget = available["budget_payroll_cost"].sum()
total_actual = available["actual_employer_cost"].sum()
net_variance = available["variance"].sum()
gross_overspend = available["variance"].clip(lower=0).sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Approved budget", f"₹{total_budget / 100000:.2f} L")
c2.metric("Actual employer cost", f"₹{total_actual / 100000:.2f} L")
c3.metric("Gross overspend", f"₹{gross_overspend / 100000:.2f} L")
c4.metric("Net variance", f"₹{net_variance / 100000:.2f} L")

st.caption(
    f"Showing {len(available)} department-months with actual payroll data. "
    "Missing actuals are excluded, not treated as zero."
)

# --------------------------------------------------
# Sign convention
# --------------------------------------------------

st.markdown("### 1. Variance calculation and sign convention")
st.code(
    "Variance = Actual employer cost - Approved budget\n"
    "Variance % = (Variance / Approved budget) × 100"
)
st.markdown(
    "- **Positive variance:** overspending; unfavourable.\n"
    "- **Negative variance:** underspending; favourable.\n"
    "- **Zero variance:** exactly on budget.\n"
    "- **Unavailable:** actual payroll is missing; no variance is calculated."
)

# --------------------------------------------------
# Budget variance trend
# --------------------------------------------------

st.markdown("### 2. Monthly budget vs actual")

monthly = (
    available.groupby("month", as_index=False)[
        ["budget_payroll_cost", "actual_employer_cost"]
    ].sum().sort_values("month")
)

if not monthly.empty:
    trend = monthly.melt(
        id_vars="month",
        value_vars=["budget_payroll_cost", "actual_employer_cost"],
        var_name="measure",
        value_name="amount",
    )
    trend["measure"] = trend["measure"].map({
        "budget_payroll_cost": "Approved budget",
        "actual_employer_cost": "Actual employer cost",
    })
    fig = px.line(
        trend,
        x="month",
        y="amount",
        color="measure",
        markers=True,
        title="Monthly approved budget vs actual employer cost",
        labels={"month": "Month", "amount": "Amount (₹)", "measure": "Measure"},
    )
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------
# Department ranking
# --------------------------------------------------

st.markdown("### 3. Department ranking by gross overspend")

ranking = (
    available.assign(
        positive_variance=available["variance"].clip(lower=0)
    )
    .groupby("department_label", as_index=False)
    .agg(
        gross_overspend=("positive_variance", "sum"),
        net_variance=("variance", "sum"),
        overspend_months=("variance", lambda x: int((x > 0).sum())),
        months_with_actuals=("variance", "count"),
    )
    .sort_values("gross_overspend", ascending=False)
)

fig = px.bar(
    ranking,
    x="department_label",
    y="gross_overspend",
    title="Gross overspend by department",
    labels={
        "department_label": "Department",
        "gross_overspend": "Gross overspend (₹)",
    },
)
st.plotly_chart(fig, use_container_width=True)

st.dataframe(
    ranking.rename(columns={
        "department_label": "Department",
        "gross_overspend": "Gross overspend (₹)",
        "net_variance": "Net variance (₹)",
        "overspend_months": "Overspend months",
        "months_with_actuals": "Months with actuals",
    }).style.format({
        "Gross overspend (₹)": "₹{:,.2f}",
        "Net variance (₹)": "₹{:,.2f}",
    }),
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "Ranking uses the sum of positive monthly variances. "
    "Underspending months do not offset gross overspending."
)

# --------------------------------------------------
# Monthly variance detail
# --------------------------------------------------

st.markdown("### 4. Monthly variance details")

detail = filtered[[
    "month", "department_id", "department_label",
    "budget_payroll_cost", "actual_employer_cost",
    "variance", "variance_pct", "budget_status",
]].sort_values(["month", "department_id"])

display_detail = detail.rename(columns={
    "month": "Month",
    "department_id": "Department ID",
    "department_label": "Department",
    "budget_payroll_cost": "Budget (INR)",
    "actual_employer_cost": "Actual (INR)",
    "variance": "Variance (INR)",
    "variance_pct": "Variance %",
    "budget_status": "Status",
})

for col in ["Budget (INR)", "Actual (INR)", "Variance (INR)"]:
    display_detail[col] = display_detail[col].apply(
        lambda v: "N/A" if pd.isna(v) else f"INR {v:,.2f}"
    )

display_detail["Variance %"] = display_detail["Variance %"].apply(
    lambda v: "N/A" if pd.isna(v) else f"{v:.2f}%"
)

display_detail["Month"] = pd.to_datetime(
    display_detail["Month"]
).dt.strftime("%Y-%m")

st.dataframe(
    display_detail,
    use_container_width=True,
    hide_index=True,
)

# KPI target performance
# --------------------------------------------------

st.markdown("### 5. KPI performance against targets")

if not kpis.empty:
    kpis["month"] = pd.to_datetime(kpis["month"], errors="coerce")
    kpis["group_size"] = pd.to_numeric(kpis["group_size"], errors="coerce")
    kpis = kpis[kpis["group_size"] >= MIN_GROUP_SIZE].copy()

    if not departments.empty:
        kpis = kpis.merge(departments, on="department_id", how="left")
        kpis["department_label"] = kpis["department_name"].fillna(
            kpis["department_id"]
        )
    else:
        kpis["department_label"] = kpis["department_id"]

    kpis = kpis[
        kpis["month"].dt.date.between(start_date, end_date)
        & kpis["department_label"].isin(selected_departments)
    ]

    if not kpis.empty:
        counts = (
            kpis.groupby(["metric_name", "traffic_light"])
            .size()
            .unstack(fill_value=0)
            .reindex(columns=["Green", "Red", "Unavailable"], fill_value=0)
        )
        def traffic_light_style(value):
            colors = {
                "Green": "background-color: #d1fae5; color: #065f46; font-weight: bold;",
                "Red": "background-color: #fee2e2; color: #991b1b; font-weight: bold;",
                "Unavailable": "background-color: #e5e7eb; color: #374151; font-weight: bold;",
            }
            return colors.get(value, "")

        st.markdown("**Traffic-light summary**")
        counts_styled = counts.style.map(
            traffic_light_style,
            subset=["Green", "Red", "Unavailable"],
        )
        st.dataframe(counts_styled, use_container_width=True)

        st.caption(
            "Green = target met; Red = target missed; "
            "Unavailable = actual or target missing. "
            "No amber threshold is defined in the target table."
        )

        kpi_detail = kpis[[
            "month", "department_id", "metric_name",
            "actual_value", "target_value",
            "direction", "traffic_light", "group_size"
        ]].sort_values(["month", "department_id", "metric_name"])

        detail_styled = kpi_detail.style.map(
            traffic_light_style,
            subset=["traffic_light"],
        )
        st.dataframe(
            detail_styled,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No KPI records match the selected filters.")
else:
    st.warning("KPI comparison CSV is unavailable.")

# --------------------------------------------------
# Task completion reference comparison
# --------------------------------------------------

st.markdown("### 6. Task completion — reference comparison")

st.warning(
    "Task completion actuals are measured at team-sprint level, "
    "while targets are measured at department-month level. "
    "The sprint end month is used to align the target. "
    "This is a reference comparison, not a like-for-like monthly KPI."
)

if not tasks.empty:
    tasks["target_month"] = pd.to_datetime(
        tasks["target_month"], errors="coerce"
    )
    tasks["group_size"] = pd.to_numeric(tasks["group_size"], errors="coerce")
    tasks = tasks[tasks["group_size"] >= MIN_GROUP_SIZE].copy()

    if not departments.empty:
        tasks = tasks.merge(departments, on="department_id", how="left")
        tasks["department_label"] = tasks["department_name"].fillna(
            tasks["department_id"]
        )
    else:
        tasks["department_label"] = tasks["department_id"]

    tasks = tasks[
        tasks["target_month"].dt.date.between(start_date, end_date)
        & tasks["department_label"].isin(selected_departments)
    ]

    if not tasks.empty:
        st.dataframe(
            tasks[[
                "sprint_id", "sprint_start_date", "sprint_end_date",
                "department_id", "team_id", "actual_completion_pct",
                "target_completion_pct", "traffic_light", "group_size"
            ]].sort_values(["sprint_end_date", "department_id", "team_id"]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No task-completion records match the selected filters.")
else:
    st.warning("Task-completion comparison CSV is unavailable.")

# --------------------------------------------------
# Recommendations
# --------------------------------------------------

st.markdown("### 7. Management recommendations")

st.markdown("""
**Priority 1 — D01**

- Highest gross overspend: ₹48.30 lakh across 8 overspending months.
- Net variance is an underspend of approximately ₹20.55 lakh.
- March 2026 and April 2026 recorded the largest monthly overspends:
  approximately ₹12.58 lakh and ₹12.88 lakh.
- Recommendation: investigate the payroll drivers in these two months,
  including headcount changes, new hires, salary changes and overtime.
  Review the underspending months separately before making staffing or
  cost-reduction decisions.

**Priority 2 — D04**

- Second-highest gross overspend: ₹26.10 lakh across 9 overspending months.
- Net variance is an overspend of approximately ₹0.58 lakh.
- May 2025, April 2025 and June 2025 recorded notable overspends.
- Recommendation: review recurring payroll deviations in these months.
  Compare actual staffing, overtime and pay changes with the approved
  departmental plan, then agree corrective actions with the department owner.

**Watchlist — D03**

- Gross overspend is approximately ₹26.08 lakh.
- Net overspend is approximately ₹9.93 lakh across the selected 18 months.
- Recommendation: investigate the repeated overspend pattern and monitor
  it alongside D01 and D04.
""")

# --------------------------------------------------
# Budget fairness caveat
# --------------------------------------------------

st.markdown("### 8. Budget fairness and hiring-freeze context")

st.info(
    "If a hiring freeze was introduced but the approved budget was not updated, "
    "retain the original approved budget as the baseline and label it as potentially "
    "stale. Show the variance transparently, add the freeze date and approved context, "
    "and avoid treating the variance alone as evidence of poor departmental "
    "performance. Rebase the budget only after formal approval."
)

st.caption(
    "PulseIQ | Phase 2 | PQ-10 | Source: governed metric views and clean CSV exports. "
    "Small groups below the minimum group size of 5 are excluded where group-size "
    "information is available."
)
