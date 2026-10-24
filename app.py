from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# --------------------------------------------------
# PulseIQ | Phase 1: Workforce & Headcount Dashboard
# --------------------------------------------------

st.set_page_config(
    page_title="PulseIQ | Workforce Dashboard",
    page_icon="📊",
    layout="wide",
)

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "clean"
OUTPUTS = ROOT / "outputs"

MIN_HEADCOUNT = 5
MIN_ATTRITION = 10

st.markdown("""
<style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }

    div[data-testid="stMetric"] {
        background: #F4F7FB;
        border: 1px solid #DFE7F1;
        padding: 15px;
        border-radius: 10px;
    }

    div[data-testid="stMetric"] label,
    div[data-testid="stMetricLabel"],
    div[data-testid="stMetricValue"],
    div[data-testid="stMetricDelta"] {
        color: #172033 !important;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_csv(folder, filename):
    path = folder / filename
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)


@st.cache_data
def load_data():
    headcount = load_csv(OUTPUTS, "m01_headcount.csv")
    hires = load_csv(OUTPUTS, "m02_hires.csv")
    exits = load_csv(OUTPUTS, "m03_exits.csv")
    attrition = load_csv(OUTPUTS, "m04_attrition_rate_monthly.csv")

    departments = load_csv(DATA, "dim_department.csv")
    employees = load_csv(DATA, "dim_employee.csv")
    locations = load_csv(DATA, "dim_location.csv")

    for df in [headcount, hires, exits, attrition]:
        if not df.empty and "month_start_date" in df.columns:
            df["month_start_date"] = pd.to_datetime(
                df["month_start_date"], errors="coerce"
            )

    if not employees.empty:
        if "valid_from" in employees.columns:
            employees["valid_from"] = pd.to_datetime(
                employees["valid_from"], errors="coerce"
            )
        if "is_current" in employees.columns:
            current = employees[
                employees["is_current"].astype(str).str.upper().eq("Y")
            ].copy()
        else:
            current = employees.copy()

        # Keep one latest row per employee to avoid historical duplicates.
        if "employee_id" in current.columns:
            sort_cols = ["employee_id"]
            if "valid_from" in current.columns:
                sort_cols.append("valid_from")
            current = current.sort_values(sort_cols)
            current = current.drop_duplicates("employee_id", keep="last")
        employees = current

    if not departments.empty and {
        "department_id", "department_name"
    }.issubset(departments.columns):
        departments = departments[["department_id", "department_name"]]

    return headcount, hires, exits, attrition, departments, employees, locations


try:
    headcount, hires, exits, attrition, departments, employees, locations = load_data()
except Exception as exc:
    st.error(f"Unable to load dashboard data: {exc}")
    st.stop()


def add_department_names(df):
    if df.empty:
        return df
    if (
        not departments.empty
        and "department_id" in df.columns
        and "department_id" in departments.columns
    ):
        return df.merge(departments, on="department_id", how="left")
    return df


def suppress_small_groups(df, metric_name):
    """Suppress rows below the metric's minimum group size."""
    if df.empty:
        return df.copy()

    minimum = MIN_ATTRITION if metric_name == "attrition" else MIN_HEADCOUNT

    if "group_size" in df.columns:
        group_size = pd.to_numeric(df["group_size"], errors="coerce")
        return df[group_size >= minimum].copy()

    # If group size evidence is missing, do not display grouped results.
    return df.iloc[0:0].copy()


def format_count(value):
    return f"{int(value):,}" if pd.notna(value) else "N/A"


def insight_for_change(label, current, previous):
    if pd.isna(current):
        return f"Insight: No usable value is available for {label.lower()}."
    if pd.isna(previous):
        return f"Insight: The available data shows {label.lower()} of {current:,.0f}."
    difference = current - previous
    direction = "increased" if difference > 0 else (
        "decreased" if difference < 0 else "did not change"
    )
    return (
        f"Insight: {label} {direction} by {abs(difference):,.0f} "
        f"compared with the previous displayed month."
    )


st.title("PulseIQ")
st.subheader("Workforce & Headcount Dashboard")
st.caption(
    "Phase 1 | Source: governed metric exports and cleaned dimension data. "
    "Small groups are suppressed according to the metric dictionary where group-size "
    "information is available."
)

if headcount.empty:
    st.error("The file outputs/m01_headcount.csv is missing or empty.")
    st.stop()

required = {"month_start_date", "department_id", "headcount"}
if not required.issubset(headcount.columns):
    st.error(
        "The headcount metric file is missing required columns: "
        + ", ".join(sorted(required - set(headcount.columns)))
    )
    st.stop()

headcount = add_department_names(headcount)
headcount = suppress_small_groups(headcount, "headcount")
headcount = headcount.dropna(subset=["month_start_date"])
headcount["headcount"] = pd.to_numeric(headcount["headcount"], errors="coerce")
headcount = headcount.dropna(subset=["headcount"])

if headcount.empty:
    st.warning("No headcount groups meet the minimum display threshold.")
    st.stop()

# --------------------------------------------------
# Filters
# --------------------------------------------------

st.sidebar.header("Dashboard Filters")

department_names = sorted(
    headcount["department_name"].dropna().unique().tolist()
) if "department_name" in headcount.columns else []

selected_departments = st.sidebar.multiselect(
    "Department",
    options=department_names,
    default=department_names,
)

min_date = headcount["month_start_date"].min().date()
max_date = headcount["month_start_date"].max().date()

date_range = st.sidebar.date_input(
    "Month range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date, max_date

filtered = headcount[
    (headcount["month_start_date"].dt.date >= start_date)
    & (headcount["month_start_date"].dt.date <= end_date)
].copy()

if selected_departments and "department_name" in filtered.columns:
    filtered = filtered[
        filtered["department_name"].isin(selected_departments)
    ]
elif "department_name" in filtered.columns and not selected_departments:
    filtered = filtered.iloc[0:0]

if filtered.empty:
    st.warning("No data matches these filters. Choose a wider date range or more departments.")
    st.stop()

# --------------------------------------------------
# KPI cards
# --------------------------------------------------

latest_month = filtered["month_start_date"].max()
latest_rows = filtered[filtered["month_start_date"] == latest_month]
previous_months = sorted(filtered["month_start_date"].dropna().unique())
previous_month = previous_months[-2] if len(previous_months) > 1 else None

latest_total = latest_rows["headcount"].sum()
previous_total = (
    filtered.loc[
        filtered["month_start_date"] == previous_month, "headcount"
    ].sum()
    if previous_month is not None else float("nan")
)

hire_total = None
exit_total = None
attrition_value = None

if not hires.empty and "hires" in hires.columns:
    h = add_department_names(hires)
    h = suppress_small_groups(h, "headcount")
    h = h[
        h["month_start_date"].between(
            pd.Timestamp(start_date), pd.Timestamp(end_date)
        )
    ]
    if "department_name" in h.columns:
        h = h[h["department_name"].isin(selected_departments)]
    else:
        h = h.iloc[0:0]
    hire_total = pd.to_numeric(h["hires"], errors="coerce").sum()

if not exits.empty and "exits" in exits.columns:
    e = add_department_names(exits)
    e = suppress_small_groups(e, "headcount")
    e = e[
        e["month_start_date"].between(
            pd.Timestamp(start_date), pd.Timestamp(end_date)
        )
    ]
    if selected_departments and "department_name" in e.columns:
        e = e[e["department_name"].isin(selected_departments)]
    exit_total = pd.to_numeric(e["exits"], errors="coerce").sum()

if not attrition.empty and "attrition_rate_monthly_pct" in attrition.columns:
    a = add_department_names(attrition)
    a = suppress_small_groups(a, "attrition")
    a = a[
        a["month_start_date"].between(
            pd.Timestamp(start_date), pd.Timestamp(end_date)
        )
    ]
    if selected_departments and "department_name" in a.columns:
        a = a[a["department_name"].isin(selected_departments)]
    if not a.empty:
        attrition_value = pd.to_numeric(
            a.loc[a["month_start_date"] == a["month_start_date"].max(),
                  "attrition_rate_monthly_pct"],
            errors="coerce",
        ).mean()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Headcount — latest month", format_count(latest_total))
k2.metric("Hires — selected period", format_count(hire_total) if hire_total is not None else "N/A")
k3.metric("Exits — selected period", format_count(exit_total) if exit_total is not None else "N/A")
k4.metric(
    "Monthly attrition — latest available",
    f"{attrition_value:.2f}%" if pd.notna(attrition_value) else "N/A",
)

st.caption(
    f"Latest month shown: {latest_month:%B %Y}. "
    "Headcount totals sum only displayed department groups meeting the metric's "
    "minimum group-size threshold."
)

# --------------------------------------------------
# Chart 1: Headcount trend
# --------------------------------------------------

st.markdown("### 1. Headcount trend")

trend = (
    filtered.groupby("month_start_date", as_index=False)["headcount"]
    .sum()
    .sort_values("month_start_date")
)

fig = px.line(
    trend,
    x="month_start_date",
    y="headcount",
    markers=True,
    title="Monthly headcount across selected departments",
    labels={"month_start_date": "Month", "headcount": "Headcount"},
)
fig.update_layout(hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)

if len(trend) >= 2:
    st.info(
        insight_for_change(
            "Headcount",
            trend.iloc[-1]["headcount"],
            trend.iloc[-2]["headcount"],
        )
    )
else:
    st.info("Insight: Select a date range with at least two months to compare headcount.")

# --------------------------------------------------
# Chart 2: Department mix
# --------------------------------------------------

st.markdown("### 2. Department mix")

latest_department = latest_rows.copy()
if "department_name" in latest_department.columns:
    dept_mix = (
        latest_department.groupby("department_name", as_index=False)["headcount"]
        .sum()
        .sort_values("headcount", ascending=False)
    )
    if not dept_mix.empty:
        fig = px.bar(
            dept_mix,
            x="department_name",
            y="headcount",
            title="Headcount by department — latest month",
            labels={"department_name": "Department", "headcount": "Headcount"},
        )
        st.plotly_chart(fig, use_container_width=True)
        top = dept_mix.iloc[0]
        st.info(
            f"Insight: {top['department_name']} has the highest displayed "
            f"headcount ({top['headcount']:,.0f}) in the latest month."
        )
    else:
        st.info("Insight: No department groups meet the privacy threshold.")
else:
    st.info("Department names are unavailable, so the department chart cannot be shown.")

# --------------------------------------------------
# Chart 3: Location tier
# --------------------------------------------------

st.markdown("### 3. Workforce by location tier")

if not employees.empty and "work_location" in employees.columns and not locations.empty:
    location_data = employees.merge(locations, on="work_location", how="left")

    if selected_departments and "department_name" in headcount.columns:
        # Map department names to IDs using the dimension table.
        allowed_ids = departments[
            departments["department_name"].isin(selected_departments)
        ]["department_id"].tolist() if not departments.empty else []
        if "department_id" in location_data.columns and allowed_ids:
            location_data = location_data[
                location_data["department_id"].isin(allowed_ids)
            ]

    if "employee_id" in location_data.columns and "city_tier" in location_data.columns:
        tier_counts = (
            location_data.groupby("city_tier")["employee_id"]
            .nunique()
            .reset_index(name="employees")
        )
        tier_counts = tier_counts[tier_counts["employees"] >= MIN_HEADCOUNT]

        if not tier_counts.empty:
            fig = px.bar(
                tier_counts,
                x="city_tier",
                y="employees",
                title="Current employee records by location tier",
                labels={"city_tier": "Location tier", "employees": "Employees"},
            )
            st.plotly_chart(fig, use_container_width=True)
            top = tier_counts.sort_values("employees", ascending=False).iloc[0]
            st.info(
                f"Insight: {top['city_tier']} has the highest displayed employee "
                f"count ({top['employees']:,}) among location tiers."
            )
        else:
            st.info("Insight: No location-tier group meets the minimum group size of 5.")
    else:
        st.info("Location tier or employee identifier columns are unavailable.")
else:
    st.info("Employee or location dimension data is unavailable for the location chart.")

# --------------------------------------------------
# Chart 4: Work mode
# --------------------------------------------------

st.markdown("### 4. Workforce by work mode")

if not employees.empty and {"employee_id", "work_mode"}.issubset(employees.columns):
    work_data = employees.copy()

    if selected_departments and not departments.empty and "department_id" in work_data.columns:
        allowed_ids = departments[
            departments["department_name"].isin(selected_departments)
        ]["department_id"].tolist()
        if allowed_ids:
            work_data = work_data[work_data["department_id"].isin(allowed_ids)]

    work_counts = (
        work_data.groupby("work_mode")["employee_id"]
        .nunique()
        .reset_index(name="employees")
    )
    work_counts = work_counts[work_counts["employees"] >= MIN_HEADCOUNT]

    if not work_counts.empty:
        fig = px.bar(
            work_counts,
            x="work_mode",
            y="employees",
            title="Current employee records by work mode",
            labels={"work_mode": "Work mode", "employees": "Employees"},
        )
        st.plotly_chart(fig, use_container_width=True)
        top = work_counts.sort_values("employees", ascending=False).iloc[0]
        st.info(
            f"Insight: {top['work_mode']} is the largest displayed work-mode group "
            f"({top['employees']:,} employees)."
        )
    else:
        st.info("Insight: No work-mode group meets the minimum group size of 5.")
else:
    st.info("Work-mode or employee identifier columns are unavailable.")

# --------------------------------------------------
# Chart 5: Monthly hires vs exits
# --------------------------------------------------

st.markdown("### 5. Hires and exits over time")

if (
    not hires.empty and not exits.empty
    and {"month_start_date", "hires"}.issubset(hires.columns)
    and {"month_start_date", "exits"}.issubset(exits.columns)
):
    h = add_department_names(hires)
    e = add_department_names(exits)
    h = suppress_small_groups(h, "headcount")
    e = suppress_small_groups(e, "headcount")

    if selected_departments:
        if "department_name" in h.columns:
            h = h[h["department_name"].isin(selected_departments)]
        if "department_name" in e.columns:
            e = e[e["department_name"].isin(selected_departments)]

    h = h[h["month_start_date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))]
    e = e[e["month_start_date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))]

    h_month = h.groupby("month_start_date", as_index=False)["hires"].sum()
    e_month = e.groupby("month_start_date", as_index=False)["exits"].sum()
    flows = h_month.merge(e_month, on="month_start_date", how="outer").fillna(0)
    flows = flows.sort_values("month_start_date")

    if not flows.empty:
        long_flows = flows.melt(
            id_vars="month_start_date",
            value_vars=["hires", "exits"],
            var_name="measure",
            value_name="employees",
        )
        fig = px.line(
            long_flows,
            x="month_start_date",
            y="employees",
            color="measure",
            markers=True,
            title="Monthly hires and exits",
            labels={
                "month_start_date": "Month",
                "employees": "Employees",
                "measure": "Measure",
            },
        )
        st.plotly_chart(fig, use_container_width=True)
        latest_flow = flows.iloc[-1]
        st.info(
            f"Insight: In {latest_flow['month_start_date']:%B %Y}, "
            f"the displayed groups recorded {latest_flow['hires']:,.0f} hires "
            f"and {latest_flow['exits']:,.0f} exits."
        )
    else:
        st.info("Insight: No hires/exits data is available for the selected filters.")
else:
    st.info("Hires/exits metric files are unavailable for this comparison.")

st.divider()
st.caption(
    "PulseIQ Phase 1 | Use governed metric exports for workforce metrics. "
    "Historical employee records are reduced to one latest current row per employee "
    "for snapshot charts. Small groups are suppressed where group-size evidence is available."
)