
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# --------------------------------------------------
# PulseIQ | Phase 2: Attrition Analytics (PQ-07)
# --------------------------------------------------

st.set_page_config(
    page_title="PulseIQ | Attrition Analytics",
    page_icon="📊",
    layout="wide",
)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "clean"
OUTPUTS = ROOT / "outputs"

# Official minimum group-size rules
MIN_ATTRITION_GROUP = 10
MIN_RISK_GROUP = 10

st.title("PulseIQ | Attrition Analytics")
st.caption(
    "PQ-07 | Actual employee exits and separately labelled "
    "predicted attrition risk"
)


@st.cache_data
def load_csv(folder, filename):
    """Load a CSV file safely."""
    path = folder / filename

    if not path.exists():
        return pd.DataFrame()

    return pd.read_csv(path, low_memory=False)


@st.cache_data
def load_data():
    """Load official metric outputs and supporting dimensions."""
    return {
        "monthly": load_csv(
            OUTPUTS, "m04_attrition_rate_monthly.csv"
        ),
        "rolling": load_csv(
            OUTPUTS, "m05_attrition_rate_rolling_12m.csv"
        ),
        "voluntary": load_csv(
            OUTPUTS, "m06_voluntary_attrition_rate.csv"
        ),
        "risk": load_csv(
            OUTPUTS, "m27_high_risk_share.csv"
        ),
        "headcount": load_csv(
            DATA, "fact_headcount_monthly.csv"
        ),
        "employees": load_csv(
            DATA, "dim_employee.csv"
        ),
        "departments": load_csv(
            DATA, "dim_department.csv"
        ),
        "risk_detail": load_csv(
            DATA, "fact_attrition_risk.csv"
        ),
    }


data = load_data()


# --------------------------------------------------
# Prepare data and dashboard filters
# --------------------------------------------------

monthly = data["monthly"].copy()
rolling = data["rolling"].copy()
voluntary = data["voluntary"].copy()
risk = data["risk"].copy()

departments = data["departments"].copy()

if departments.empty:
    st.error("Department data is missing.")
    st.stop()

department_map = dict(
    zip(
        departments["department_id"],
        departments["department_name"],
    )
)

# Convert metric dates to datetime
for frame in [monthly, rolling, voluntary]:
    if not frame.empty:
        frame["month_start_date"] = pd.to_datetime(
            frame["month_start_date"],
            errors="coerce",
        )

if not risk.empty:
    risk["as_of_date"] = pd.to_datetime(
        risk["as_of_date"],
        errors="coerce",
    )

# Show readable department names
for frame in [monthly, rolling, voluntary, risk]:
    if not frame.empty:
        frame["department_name"] = frame["department_id"].map(
            department_map
        )

# Determine the date range from the official monthly metric
if monthly.empty:
    st.error("The monthly attrition metric file is empty or missing.")
    st.stop()

monthly = monthly.dropna(subset=["month_start_date"])

if monthly.empty:
    st.error("No valid dates were found in the monthly attrition data.")
    st.stop()

min_date = monthly["month_start_date"].min().date()
max_date = monthly["month_start_date"].max().date()

st.sidebar.header("Dashboard filters")

selected_dates = st.sidebar.date_input(
    "Month range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

if isinstance(selected_dates, (tuple, list)) and len(selected_dates) == 2:
    start_date, end_date = selected_dates
else:
    start_date, end_date = min_date, max_date

start_date = pd.Timestamp(start_date)
end_date = pd.Timestamp(end_date)

available_departments = sorted(
    monthly["department_name"].dropna().unique().tolist()
)

selected_departments = st.sidebar.multiselect(
    "Departments",
    options=available_departments,
    default=available_departments,
)

# Filter actual monthly metrics
monthly_filtered = monthly[
    monthly["month_start_date"].between(start_date, end_date)
    & monthly["department_name"].isin(selected_departments)
    & (monthly["group_size"] >= MIN_ATTRITION_GROUP)
].copy()

# Filter rolling and voluntary metrics
rolling_filtered = rolling[
    rolling["month_start_date"].between(start_date, end_date)
    & rolling["department_name"].isin(selected_departments)
    & (rolling["group_size"] >= MIN_ATTRITION_GROUP)
].copy()

voluntary_filtered = voluntary[
    voluntary["month_start_date"].between(start_date, end_date)
    & voluntary["department_name"].isin(selected_departments)
    & (voluntary["group_size"] >= MIN_ATTRITION_GROUP)
].copy()

# Risk is a point-in-time prediction, so filter by snapshot date.
risk_filtered = risk[
    risk["department_name"].isin(selected_departments)
    & (risk["group_size"] >= MIN_RISK_GROUP)
].copy()

if not risk_filtered.empty:
    latest_risk_date = risk_filtered["as_of_date"].max()
    risk_filtered = risk_filtered[
        risk_filtered["as_of_date"] == latest_risk_date
    ]


# --------------------------------------------------
# Headline KPI cards
# --------------------------------------------------

st.divider()
st.subheader("Workforce attrition overview")

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

# Latest available rolling 12-month metric in the selected range
if not rolling_filtered.empty:
    latest_rolling_date = rolling_filtered["month_start_date"].max()
    latest_rolling = rolling_filtered[
        rolling_filtered["month_start_date"] == latest_rolling_date
    ]

    rolling_rate = (
        latest_rolling["attrition_rate_rolling_12m_pct"].mean()
    )
    rolling_label = latest_rolling_date.strftime("%b %Y")
    kpi1.metric(
        "Rolling 12-month attrition",
        f"{rolling_rate:.2f}%",
        help=f"Latest available month: {rolling_label}",
    )
else:
    kpi1.metric("Rolling 12-month attrition", "N/A")

# Sum of actual exits in the selected period and visible departments
if not monthly_filtered.empty:
    total_exits = int(monthly_filtered["exits"].sum())
    kpi2.metric(
    "Actual exits (eligible groups)",
    f"{total_exits:,}",
    help=(
        "Sum of recorded exits from department-month groups that "
        "meet the official minimum group-size threshold of 10."
    ),
)
else:
    kpi2.metric("Actual exits (eligible groups)", "N/A")

# Latest voluntary attrition metric
if not voluntary_filtered.empty:
    latest_voluntary_date = voluntary_filtered["month_start_date"].max()
    latest_voluntary = voluntary_filtered[
        voluntary_filtered["month_start_date"] == latest_voluntary_date
    ]

    voluntary_rate = (
        latest_voluntary["voluntary_attrition_rate_pct"].mean()
    )
    kpi3.metric(
        "Voluntary attrition (12m)",
        f"{voluntary_rate:.2f}%",
        help=(
            "Official rolling 12-month voluntary attrition metric. "
            f"Latest available month: {latest_voluntary_date:%b %Y}"
        ),
    )
else:
    kpi3.metric("Voluntary attrition (12m)", "N/A")

# Latest predicted high-risk share, aggregated across eligible groups
if not risk_filtered.empty:
    weighted_high_risk = (
        risk_filtered["high_risk_share"]
        * risk_filtered["group_size"]
    ).sum() / risk_filtered["group_size"].sum()

    risk_date_label = risk_filtered["as_of_date"].max().strftime("%d %b %Y")

    kpi4.metric(
        "Predicted high-risk share",
        f"{weighted_high_risk:.2%}",
        help=(
            "Prediction, not actual attrition. "
            f"Snapshot: {risk_date_label}. "
            "Aggregated across eligible department groups."
        ),
    )
else:
    kpi4.metric("Predicted high-risk share", "N/A")

st.caption(
    "Actual exits describe recorded departures. Predicted risk is a "
    "model-generated signal and must not be interpreted as a confirmed exit."
)

st.info(
    "Data limitation: The available source data does not contain a "
    "dedicated exit-reason field. Exit reasons are therefore not "
    "analysed in this dashboard."
)


# --------------------------------------------------
# Monthly attrition trends
# --------------------------------------------------

st.divider()
st.subheader("1. Monthly attrition trends")

st.caption(
    "Official M04 metric: monthly exits divided by starting headcount. "
    "Department-month groups below 10 are excluded."
)

if monthly_filtered.empty:
    st.info(
        "No eligible monthly attrition data is available for the "
        "selected dates and departments."
    )
else:
    monthly_chart = px.line(
        monthly_filtered.sort_values("month_start_date"),
        x="month_start_date",
        y="attrition_rate_monthly_pct",
        color="department_name",
        markers=True,
        title="Monthly attrition rate by department",
        labels={
            "month_start_date": "Month",
            "attrition_rate_monthly_pct": "Attrition rate (%)",
            "department_name": "Department",
        },
    )

    monthly_chart.update_layout(
        hovermode="x unified",
        legend_title_text="Department",
    )

    st.plotly_chart(monthly_chart, width="stretch")

    highest_month = monthly_filtered.loc[
        monthly_filtered["attrition_rate_monthly_pct"].idxmax()
    ]

    st.markdown(
        f"**Finding:** The highest eligible monthly attrition rate in "
        f"the current selection was **"
        f"{highest_month['attrition_rate_monthly_pct']:.2f}%** in "
        f"**{highest_month['department_name']}** during "
        f"{highest_month['month_start_date']:%b %Y}."
    )


# --------------------------------------------------
# Rolling and voluntary attrition trends
# --------------------------------------------------

st.divider()
st.subheader("2. Rolling 12-month attrition")

st.caption(
    "Official M05 metric: exits over the trailing 12 months divided "
    "by average ending headcount over the same period."
)

if rolling_filtered.empty:
    st.info("No eligible rolling 12-month attrition data is available.")
else:
    rolling_chart = px.line(
        rolling_filtered.sort_values("month_start_date"),
        x="month_start_date",
        y="attrition_rate_rolling_12m_pct",
        color="department_name",
        markers=True,
        title="Rolling 12-month attrition rate by department",
        labels={
            "month_start_date": "Month",
            "attrition_rate_rolling_12m_pct": "Attrition rate (%)",
            "department_name": "Department",
        },
    )

    rolling_chart.update_layout(
        hovermode="x unified",
        legend_title_text="Department",
    )

    st.plotly_chart(rolling_chart, width="stretch")


st.subheader("3. Voluntary attrition")

st.caption(
    "Official M06 metric: trailing 12-month voluntary exits divided "
    "by average ending headcount over the same period."
)

if voluntary_filtered.empty:
    st.info("No eligible voluntary attrition data is available.")
else:
    voluntary_chart = px.line(
        voluntary_filtered.sort_values("month_start_date"),
        x="month_start_date",
        y="voluntary_attrition_rate_pct",
        color="department_name",
        markers=True,
        title="Voluntary attrition rate over 12 months by department",
        labels={
            "month_start_date": "Month",
            "voluntary_attrition_rate_pct": "Voluntary attrition rate (%)",
            "department_name": "Department",
        },
    )

    voluntary_chart.update_layout(
        hovermode="x unified",
        legend_title_text="Department",
    )

    st.plotly_chart(voluntary_chart, width="stretch")


# --------------------------------------------------
# Predicted attrition risk (AI output)
# --------------------------------------------------

st.divider()
st.subheader("4. Predicted Attrition Risk — AI Model Output")

st.warning(
    "These are model predictions, not confirmed employee departures. "
    "Use them as aggregated HR support signals, never as individual "
    "employment decisions."
)

if risk_filtered.empty:
    st.info(
        "No eligible predicted-risk groups are available for the "
        "selected departments."
    )
else:
    risk_display = risk_filtered.copy()

    risk_display["high_risk_share_pct"] = (
        risk_display["high_risk_share"] * 100
    )

    risk_chart = px.bar(
        risk_display.sort_values("high_risk_share_pct", ascending=False),
        x="department_name",
        y="high_risk_share_pct",
        title="Predicted high-risk share by department",
        labels={
            "department_name": "Department",
            "high_risk_share_pct": "Predicted high-risk share (%)",
        },
        hover_data={
            "group_size": True,
            "as_of_date": True,
        },
    )

    risk_chart.update_layout(
        xaxis_title="Department",
        yaxis_title="Predicted high-risk share (%)",
    )

    st.plotly_chart(risk_chart, width="stretch")

    st.caption(
        f"Snapshot date: {risk_display['as_of_date'].max():%d %b %Y}. "
        "Only department groups meeting the minimum size of 10 are shown."
    )

    risk_table = risk_display[
        [
            "department_name",
            "high_risk_share_pct",
            "group_size",
            "as_of_date",
        ]
    ].rename(
        columns={
            "department_name": "Department",
            "high_risk_share_pct": "Predicted high-risk share (%)",
            "group_size": "Employees assessed",
            "as_of_date": "Prediction snapshot date",
        }
    )

    risk_table["Predicted high-risk share (%)"] = (
        risk_table["Predicted high-risk share (%)"].round(2)
    )

    st.dataframe(
        risk_table.sort_values(
            "Predicted high-risk share (%)",
            ascending=False,
        ),
        hide_index=True,
        width="stretch",
    )


# --------------------------------------------------
# Tenure at exit
# --------------------------------------------------

st.divider()
st.subheader("5. Employee Tenure at Exit")

st.caption(
    "Tenure is calculated as the time between hire date and exit date. "
    "Each employee is counted once, using their latest historical record."
)

employees = data["employees"].copy()

if employees.empty:
    st.info("Employee dimension data is unavailable.")
else:
    required_columns = {
        "employee_id",
        "hire_date",
        "exit_date",
        "department_id",
        "valid_from",
    }

    if not required_columns.issubset(employees.columns):
        st.warning(
            "The employee dimension is missing one or more fields "
            "needed for tenure-at-exit analysis."
        )
    else:
        employees["hire_date"] = pd.to_datetime(
            employees["hire_date"], errors="coerce"
        )
        employees["exit_date"] = pd.to_datetime(
            employees["exit_date"], errors="coerce"
        )
        employees["valid_from"] = pd.to_datetime(
            employees["valid_from"], errors="coerce"
        )

        # Keep one record per employee: the most recent valid_from row.
        employees = employees.sort_values("valid_from")
        employee_exit_records = employees.drop_duplicates(
            subset=["employee_id"],
            keep="last",
        ).copy()

        employee_exit_records = employee_exit_records.dropna(
            subset=["hire_date", "exit_date"]
        )

        employee_exit_records = employee_exit_records[
            employee_exit_records["exit_date"]
            >= employee_exit_records["hire_date"]
        ].copy()

        employee_exit_records["tenure_years"] = (
            (
                employee_exit_records["exit_date"]
                - employee_exit_records["hire_date"]
            ).dt.days
            / 365.25
        )

        employee_exit_records["department_name"] = (
            employee_exit_records["department_id"].map(
                department_map
            )
        )

        # Keep exits in the selected reporting period and departments.
        employee_exit_records = employee_exit_records[
            employee_exit_records["exit_date"].between(
                start_date,
                end_date + pd.Timedelta(days=1) - pd.Timedelta(seconds=1),
            )
            & employee_exit_records["department_name"].isin(
                selected_departments
            )
        ].copy()

        if employee_exit_records.empty:
            st.info(
                "No employee exit records were found for the selected "
                "period and departments."
            )
        else:
            # Show only departments with at least 10 exited employees.
            tenure_by_department = (
                employee_exit_records.groupby("department_name")
                .agg(
                    exited_employees=("employee_id", "nunique"),
                    average_tenure_years=("tenure_years", "mean"),
                    median_tenure_years=("tenure_years", "median"),
                )
                .reset_index()
            )

            tenure_by_department = tenure_by_department[
                tenure_by_department["exited_employees"]
                >= MIN_ATTRITION_GROUP
            ]

            if tenure_by_department.empty:
                st.info(
                    "No department has at least 10 exited employees "
                    "in the selected period. Tenure groups are hidden "
                    "to protect privacy."
                )
            else:
                tenure_chart = px.bar(
                    tenure_by_department.sort_values(
                        "median_tenure_years",
                        ascending=False,
                    ),
                    x="department_name",
                    y="median_tenure_years",
                    title="Median tenure at exit by department",
                    labels={
                        "department_name": "Department",
                        "median_tenure_years": "Median tenure (years)",
                    },
                    hover_data={
                        "exited_employees": True,
                        "average_tenure_years": ":.2f",
                    },
                )

                st.plotly_chart(
                    tenure_chart,
                    width="stretch",
                )

                tenure_display = tenure_by_department.rename(
                    columns={
                        "department_name": "Department",
                        "exited_employees": "Exited employees",
                        "average_tenure_years": "Average tenure (years)",
                        "median_tenure_years": "Median tenure (years)",
                    }
                ).copy()

                tenure_display["Average tenure (years)"] = (
                    tenure_display["Average tenure (years)"].round(2)
                )
                tenure_display["Median tenure (years)"] = (
                    tenure_display["Median tenure (years)"].round(2)
                )

                st.dataframe(
                    tenure_display,
                    hide_index=True,
                    width="stretch",
                )

# --------------------------------------------------
# Three key findings
# --------------------------------------------------

st.divider()
st.subheader("6. Key Findings")

finding_count = 0

# Finding 1: Highest eligible monthly attrition
if not monthly_filtered.empty:
    highest_month = monthly_filtered.loc[
        monthly_filtered["attrition_rate_monthly_pct"].idxmax()
    ]

    st.markdown(
        f"**Finding 1 — Monthly attrition:** The highest eligible "
        f"department-month attrition rate was "
        f"**{highest_month['attrition_rate_monthly_pct']:.2f}%** "
        f"in **{highest_month['department_name']}** during "
        f"**{highest_month['month_start_date']:%b %Y}**."
    )
    finding_count += 1

# Finding 2: Highest eligible rolling 12-month attrition
if not rolling_filtered.empty:
    highest_rolling = rolling_filtered.loc[
        rolling_filtered["attrition_rate_rolling_12m_pct"].idxmax()
    ]

    st.markdown(
        f"**Finding 2 — Longer-term attrition:** The highest eligible "
        f"rolling 12-month attrition rate was "
        f"**{highest_rolling['attrition_rate_rolling_12m_pct']:.2f}%** "
        f"in **{highest_rolling['department_name']}** during "
        f"**{highest_rolling['month_start_date']:%b %Y}**."
    )
    finding_count += 1

# Finding 3: Highest predicted high-risk share
if not risk_filtered.empty:
    highest_risk = risk_filtered.loc[
        risk_filtered["high_risk_share"].idxmax()
    ]

    st.markdown(
        f"**Finding 3 — Predicted risk:** The highest eligible "
        f"department-level predicted high-risk share was "
        f"**{highest_risk['high_risk_share']:.2%}** in "
        f"**{highest_risk['department_name']}**, based on the "
        f"**{highest_risk['as_of_date']:%d %b %Y}** snapshot. "
        f"This is a model prediction, not a confirmed departure."
    )
    finding_count += 1

if finding_count < 3:
    st.info(
        f"Only {finding_count} findings could be calculated from the "
        "current filters. Select a broader date range or more "
        "departments to find three eligible results."
    )

st.caption(
    "Findings update with the selected filters. Small groups are "
    "excluded according to the official metric privacy thresholds."
)

