from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="PulseIQ | Payroll Cost",
    page_icon="??",
    layout="wide",
)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "clean"
OUTPUTS = ROOT / "outputs"
MIN_GROUP_SIZE = 5

st.title("Payroll Cost Dashboard")
st.caption("PQ-09 | Payroll cost, reconciliation and department analysis")

st.warning(
    "DEMO ACCESS CONTROL: Role selection simulates permissions only. "
    "It is not secure authentication. Only aggregated payroll data is displayed."
)


@st.cache_data
def load_data():
    payroll = pd.read_csv(DATA / "fact_payroll.csv")
    departments = pd.read_csv(DATA / "dim_department.csv")
    roles = pd.read_csv(DATA / "dim_role.csv")

    payroll["period_end_date"] = pd.to_datetime(payroll["period_end_date"])

    payroll = payroll.merge(
        departments[["department_id", "department_name"]],
        on="department_id",
        how="left",
    )

    payroll = payroll.merge(
        roles[["role_id", "role_title", "level"]],
        on="role_id",
        how="left",
    )

    return payroll


payroll = load_data()

st.sidebar.header("Demo Access")
demo_role = st.sidebar.selectbox(
    "Choose demo role",
    ["ADMIN", "HR", "MANAGER", "EXECUTIVE"],
)

st.sidebar.caption(
    "This selector is for demonstrating role-based views, not verifying identity."
)

st.sidebar.header("Filters")

months = sorted(payroll["period_end_date"].dropna().unique())
selected_months = st.sidebar.multiselect(
    "Payroll months",
    months,
    default=months[-3:] if len(months) >= 3 else months,
    format_func=lambda value: pd.Timestamp(value).strftime("%b %Y"),
)

departments_list = sorted(payroll["department_name"].dropna().unique())

if demo_role in ["HR", "MANAGER"]:
    selected_department = st.sidebar.selectbox(
        "Demo department assignment",
        departments_list,
    )
else:
    selected_department = None

st.info(
    f"Current demo view: {demo_role}. "
    "All displayed payroll figures are aggregated."
)


# --------------------------------------------------
# Payroll filtering and KPI calculations
# --------------------------------------------------

filtered_payroll = payroll[
    payroll["period_end_date"].isin(selected_months)
].copy()

if demo_role in ["HR", "MANAGER"]:
    filtered_payroll = filtered_payroll[
        filtered_payroll["department_name"] == selected_department
    ]

if filtered_payroll.empty:
    st.warning("No payroll records found for the selected filters.")
    st.stop()

gross_total = filtered_payroll["gross_pay"].sum()
net_total = filtered_payroll["net_pay"].sum()
employer_total = filtered_payroll["employer_cost"].sum()
employee_total = filtered_payroll["headcount_flag"].sum()

st.subheader("Payroll Summary")

col1, col2, col3, col4 = st.columns(4)

col1.metric("Gross Pay", f"Rs. {gross_total:,.0f}")
col2.metric("Net Pay", f"Rs. {net_total:,.0f}")
col3.metric("Employer Cost", f"Rs. {employer_total:,.0f}")
col4.metric("Employee-Months", f"{employee_total:,.0f}")

# Executive users can see company-level KPIs only.
if demo_role != "EXECUTIVE":

    st.subheader("Department Payroll Summary")

    department_summary = (
        filtered_payroll.groupby("department_name", as_index=False)
        .agg(
            gross_pay=("gross_pay", "sum"),
            net_pay=("net_pay", "sum"),
            employer_cost=("employer_cost", "sum"),
            employee_count=("headcount_flag", "sum"),
        )
    )

    st.dataframe(department_summary, use_container_width=True)

    st.subheader("Role-wise Payroll Summary")

    role_summary = (
        filtered_payroll.groupby(
            ["role_title", "level"], as_index=False
        )
        .agg(
            gross_pay=("gross_pay", "sum"),
            net_pay=("net_pay", "sum"),
            employer_cost=("employer_cost", "sum"),
            employee_count=("employee_id", "nunique"),
        )
    )

    if demo_role in ["HR", "MANAGER"]:
        role_summary = role_summary[
            role_summary["employee_count"] >= MIN_GROUP_SIZE
        ]

    st.dataframe(role_summary, use_container_width=True)



# --------------------------------------------------
# Monthly Payroll Cost Trends
# --------------------------------------------------

if demo_role != "EXECUTIVE":

    st.subheader("Monthly Payroll Cost Trends")

    monthly_summary = (
        filtered_payroll.groupby("period_end_date", as_index=False)
        .agg(
            gross_pay=("gross_pay", "sum"),
            net_pay=("net_pay", "sum"),
            employer_cost=("employer_cost", "sum"),
        )
        .sort_values("period_end_date")
    )

    trend_data = monthly_summary.melt(
        id_vars="period_end_date",
        value_vars=["gross_pay", "net_pay", "employer_cost"],
        var_name="payroll_component",
        value_name="amount",
    )

    trend_data["payroll_component"] = trend_data[
        "payroll_component"
    ].replace({
        "gross_pay": "Gross Pay",
        "net_pay": "Net Pay",
        "employer_cost": "Employer Cost",
    })

    fig = px.line(
        trend_data,
        x="period_end_date",
        y="amount",
        color="payroll_component",
        markers=True,
        title="Gross Pay vs Net Pay vs Employer Cost",
        labels={
            "period_end_date": "Payroll Month",
            "amount": "Amount (INR)",
            "payroll_component": "Payroll Component",
        },
    )

    fig.update_layout(
        hovermode="x unified",
        yaxis_tickformat=",.0f",
    )

    st.plotly_chart(fig, use_container_width=True)



# Improve KPI number visibility
st.markdown("""
<style>
div[data-testid="stMetricValue"] {
    font-size: 1.65rem !important;
    white-space: nowrap !important;
    overflow: visible !important;
}
div[data-testid="stMetricLabel"] {
    font-size: 0.9rem !important;
}
</style>
""", unsafe_allow_html=True)



# --------------------------------------------------
# Cost per Employee Analysis
# --------------------------------------------------

if demo_role != "EXECUTIVE":

    st.subheader("Department-wise Cost per Employee")

    department_cost = (
        filtered_payroll.groupby(
            ["period_end_date", "department_name"], as_index=False
        )
        .agg(
            employer_cost=("employer_cost", "sum"),
            employee_count=("employee_id", "nunique"),
        )
    )

    department_cost["cost_per_employee"] = (
        department_cost["employer_cost"]
        / department_cost["employee_count"]
    )

    department_cost = department_cost[
        department_cost["employee_count"] >= MIN_GROUP_SIZE
    ]

    st.dataframe(
        department_cost,
        use_container_width=True,
        hide_index=True,
    )

    fig_cost = px.bar(
        department_cost,
        x="department_name",
        y="cost_per_employee",
        color="period_end_date",
        barmode="group",
        title="Monthly Employer Cost per Employee by Department",
        labels={
            "department_name": "Department",
            "cost_per_employee": "Cost per Employee (INR)",
            "period_end_date": "Payroll Month",
        },
    )

    fig_cost.update_layout(yaxis_tickformat=",.0f")
    st.plotly_chart(fig_cost, use_container_width=True)

    st.subheader("Role-wise Cost per Employee")

    role_cost = (
        filtered_payroll.groupby(
            ["role_title", "level"], as_index=False
        )
        .agg(
            employer_cost=("employer_cost", "sum"),
            employee_count=("employee_id", "nunique"),
        )
    )

    role_cost["cost_per_employee"] = (
        role_cost["employer_cost"] / role_cost["employee_count"]
    )

    if demo_role in ["HR", "MANAGER"]:
        role_cost = role_cost[
            role_cost["employee_count"] >= MIN_GROUP_SIZE
        ]

    st.dataframe(
        role_cost.sort_values("cost_per_employee", ascending=False),
        use_container_width=True,
        hide_index=True,
    )


# --------------------------------------------------
# Payroll Reconciliation
# --------------------------------------------------

st.divider()
st.subheader("Payroll Reconciliation")

if demo_role == "ADMIN":

    reconciliation_path = OUTPUTS / "dq" / "payroll_ledger_reconciliation_after_etl.csv"

    if reconciliation_path.exists():

        reconciliation = pd.read_csv(reconciliation_path)

        pass_count = (reconciliation["status"] == "PASS").sum()
        fail_count = (reconciliation["status"] == "FAIL").sum()

        rc1, rc2, rc3 = st.columns(3)
        rc1.metric("Periods Checked", len(reconciliation))
        rc2.metric("Periods Passed", int(pass_count))
        rc3.metric("Periods Failed", int(fail_count))

        st.dataframe(
            reconciliation,
            use_container_width=True,
            hide_index=True,
        )

        june_issue = reconciliation[
            reconciliation["month"] == "2026-06"
        ]

        if not june_issue.empty:
            difference = june_issue.iloc[0]["difference"]
            st.error(
                f"June 2026 unresolved ledger difference: "
                f"Rs. {abs(difference):,.2f}. "
                "Do not silently adjust this difference."
            )

        st.subheader("Excluded Payroll Records")

        excluded_rows = pd.DataFrame({
            "Payroll Item ID": [
                "PI-X0001", "PI-X0002", "PI-X0003", "PI-X0004"
            ],
            "Reason": [
                "Duplicate employee-run record",
                "Duplicate employee-run record",
                "Unknown employee ID and employee key mismatch",
                "Unknown employee ID and employee key mismatch",
            ],
            "Action": [
                "Exclude later duplicate; retain original",
                "Exclude later duplicate; retain original",
                "Quarantined as invalid payroll row",
                "Quarantined as invalid payroll row",
            ],
        })

        st.dataframe(
            excluded_rows,
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.warning("Payroll reconciliation file was not found.")

else:
    st.info(
        "Detailed payroll reconciliation is restricted "
        "to the ADMIN demo view."
    )


# --------------------------------------------------


