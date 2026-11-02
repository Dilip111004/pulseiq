from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
STARTER = ROOT / "starter"

st.set_page_config(page_title="Custom KPI Builder | PulseIQ", layout="wide")
st.title("Custom KPI Builder & Drill-Down")
st.caption("PQ-18 | Governed metric selection, role-aware views and small-group suppression")

@st.cache_data
def load_csv(name):
    path = CLEAN / name
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)

@st.cache_data
def load_users():
    return pd.read_csv(STARTER / "demo_users.csv")

metrics = load_csv("metric_dictionary.csv")
users = load_users()

if metrics.empty or users.empty:
    st.error("Required metric dictionary or demo user file is missing.")
    st.stop()

st.warning(
    "DEMO MODE: The role selector simulates role views. It is not production "
    "authentication. HR department and manager team assignments are not present "
    "in demo_users.csv, so salary detail and manager-specific records remain restricted."
)

username = st.selectbox("Demo user", users["username"].tolist())
user = users.loc[users["username"] == username].iloc[0]
role = str(user["role"]).upper()

st.write(f"**Current demo role:** {role}")

if role == "MANAGER":
    st.error(
        "Manager view is restricted: demo_users.csv does not map this user "
        "to a team. Add a verified username-to-team assignment before enabling access."
    )
    st.stop()

if role not in {"ADMIN", "HR", "EXECUTIVE"}:
    st.error("Unrecognized role. Access denied.")
    st.stop()

# Executive users can only select company-level KPIs.
supported_ids = [
    "M01", "M02", "M03", "M04",
    "M07", "M08", "M09", "M10", "M11", "M12",
    "M13", "M14", "M15",
    "M22", "M23", "M24", "M25"
]
available = metrics[metrics["metric_id"].isin(supported_ids)].copy()

if role == "EXECUTIVE":
    available = available[
        available["grain"].str.contains("month|Month", case=False, na=False)
        & available["metric_id"].isin(["M01", "M02", "M03", "M04", "M07", "M09", "M10", "M11", "M12", "M13", "M14", "M15"])
    ]

metric_id = st.selectbox(
    "Select KPI",
    available["metric_id"].tolist(),
    format_func=lambda x: (
        x + " — " + available.loc[available["metric_id"] == x, "metric_name"].iloc[0]
    )
)
metric = available.loc[available["metric_id"] == metric_id].iloc[0]

with st.expander("Metric definition and governance", expanded=True):
    st.write("**Business definition:**", metric["business_definition"])
    st.write("**Formula:**", metric["formula"])
    st.write("**Source:**", metric["source_table"])
    st.write("**Grain:**", metric["grain"])
    st.write("**Owner:**", metric["owner_team"])
    st.write("**Caveat:**", metric["caveat"])

try:
    minimum_group_size = int(metric["minimum_group_size"])
except (TypeError, ValueError):
    minimum_group_size = 0

st.caption(
    f"Minimum group size for this metric: {minimum_group_size if minimum_group_size else 'Not specified'}"
)

def month_filter(df, date_col, selected_month):
    if df.empty or date_col not in df.columns:
        return df
    dates = pd.to_datetime(df[date_col], errors="coerce")
    return df.loc[dates.dt.to_period("M") == selected_month].copy()

def suppress_small_groups(df, count_col):
    if minimum_group_size <= 0 or df.empty or count_col not in df.columns:
        return df
    return df.loc[df[count_col] >= minimum_group_size].copy()

def aggregate_monthly(metric_id, grain, selected_month):
    if metric_id in {"M01", "M02", "M03", "M04"}:
        df = load_csv("fact_headcount_monthly.csv")
        df = month_filter(df, "month_start_date", selected_month)
        if df.empty:
            return pd.DataFrame(), "No headcount data for this month."
        group_cols = ["department_id"] if grain == "Department" else []
        agg = df.groupby(group_cols, dropna=False) if group_cols else [( "Company", df )]
        rows = []
        for key, part in agg:
            if metric_id == "M01":
                value = part["headcount_end"].sum()
                population = value
            elif metric_id == "M02":
                value = part["hires"].sum()
                population = part["headcount_end"].sum()
            elif metric_id == "M03":
                value = part["exits"].sum()
                population = part["headcount_end"].sum()
            else:
                numerator = part["exits"].sum()
                denominator = part["headcount_start"].sum()
                value = numerator / denominator * 100 if denominator else None
                population = part["headcount_end"].sum()
            rows.append({
                "Department": key if isinstance(key, str) else key[0],
                "Value": value,
                "Group size": population
            })
        return pd.DataFrame(rows), None

    if metric_id in {"M07", "M08", "M09", "M10", "M11", "M12", "M15"}:
        df = load_csv("fact_payroll.csv")
        df = month_filter(df, "period_end_date", selected_month)
        if df.empty:
            return pd.DataFrame(), "No payroll data for this month."
        group_cols = ["department_id"] if grain == "Department" else []
        groups = df.groupby(group_cols, dropna=False) if group_cols else [("Company", df)]
        rows = []
        for key, part in groups:
            employees = part["employee_id"].nunique()
            gross = part["gross_pay"].sum()
            employer = part["employer_cost"].sum()
            overtime = part["overtime_pay"].sum()
            variable = part["variable_pay"].sum()
            if metric_id == "M07":
                value = gross
            elif metric_id == "M08":
                value = part["net_pay"].sum()
            elif metric_id == "M09":
                value = employer
            elif metric_id == "M10":
                value = employer / employees if employees else None
            elif metric_id == "M11":
                value = overtime / employer * 100 if employer else None
            elif metric_id == "M12":
                value = variable / gross * 100 if gross else None
            else:
                value = part["lop_days"].sum()
            rows.append({
                "Department": key if isinstance(key, str) else key[0],
                "Value": value,
                "Group size": employees
            })
        return pd.DataFrame(rows), None

    if metric_id in {"M13", "M14"}:
        df = load_csv("fact_attendance_monthly.csv")
        df = month_filter(df, "period_end_date", selected_month)
        if df.empty:
            return pd.DataFrame(), "No attendance data for this month."
        group_cols = ["department_id"] if grain == "Department" else []
        groups = df.groupby(group_cols, dropna=False) if group_cols else [("Company", df)]
        rows = []
        for key, part in groups:
            present = part["present_days"].sum()
            scheduled = part["scheduled_days"].sum()
            if metric_id == "M13":
                numerator = present + 0.5 * part["half_days_unpaid"].sum()
                value = numerator / scheduled if scheduled else None
            else:
                value = part["late_arrivals"].sum() / present if present else None
            rows.append({
                "Department": key if isinstance(key, str) else key[0],
                "Value": value,
                "Group size": part["employee_id"].nunique()
            })
        return pd.DataFrame(rows), None

    return pd.DataFrame(), "This KPI is not implemented in the monthly aggregation view."

is_task_metric = metric_id in {"M22", "M23", "M24", "M25"}

if is_task_metric:
    st.info("Task KPIs are sprint/team grain, not monthly. Select a sprint below.")
    tasks = load_csv("fact_task.csv")
    teams = load_csv("dim_team.csv")
    if tasks.empty or teams.empty:
        st.error("Task or team source table is unavailable.")
        st.stop()

    sprint_ids = sorted(tasks["sprint_id"].dropna().unique().tolist())
    sprint_id = st.selectbox("Sprint", sprint_ids)
    data = tasks.loc[tasks["sprint_id"] == sprint_id].copy()
    data = data.merge(teams[["team_id", "team_name", "department_id"]], on="team_id", how="left")
    groups = data.groupby(["team_id", "team_name"], dropna=False)
    rows = []
    for (team_id, team_name), part in groups:
        planned = part.loc[part["status"].astype(str).str.lower() != "cancelled"]
        done = part.loc[part["status"].astype(str).str.lower() == "done"]
        if metric_id == "M22":
            value = len(done) / len(planned) * 100 if len(planned) else None
        elif metric_id == "M23":
            on_time = done["completed_on_time"].astype(str).str.upper().isin(["Y", "YES", "TRUE", "1"]).sum()
            value = on_time / len(done) * 100 if len(done) else None
        elif metric_id == "M24":
            value = done["story_points"].sum()
        else:
            value = done["cycle_time_days"].mean()
        rows.append({
            "Team": team_name,
            "Value": value,
            "Group size": len(planned)
        })
    result = pd.DataFrame(rows)
    result = suppress_small_groups(result, "Group size")
    if result.empty:
        st.warning("All teams are hidden because they are below the metric's minimum group size.")
    else:
        st.dataframe(result, use_container_width=True, hide_index=True)
else:
    months_source = {
        "M01": ("fact_headcount_monthly.csv", "month_start_date"),
        "M02": ("fact_headcount_monthly.csv", "month_start_date"),
        "M03": ("fact_headcount_monthly.csv", "month_start_date"),
        "M04": ("fact_headcount_monthly.csv", "month_start_date"),
        "M07": ("fact_payroll.csv", "period_end_date"),
        "M08": ("fact_payroll.csv", "period_end_date"),
        "M09": ("fact_payroll.csv", "period_end_date"),
        "M10": ("fact_payroll.csv", "period_end_date"),
        "M11": ("fact_payroll.csv", "period_end_date"),
        "M12": ("fact_payroll.csv", "period_end_date"),
        "M13": ("fact_attendance_monthly.csv", "period_end_date"),
        "M14": ("fact_attendance_monthly.csv", "period_end_date"),
        "M15": ("fact_payroll.csv", "period_end_date")
    }
    source_name, date_col = months_source[metric_id]
    source = load_csv(source_name)
    date_values = pd.to_datetime(source[date_col], errors="coerce").dropna()
    month_options = sorted(date_values.dt.to_period("M").unique().tolist())
    if not month_options:
        st.error("No valid month values are available for this KPI.")
        st.stop()

    selected_month = st.selectbox("Reporting month", month_options, index=len(month_options)-1)
    grain_options = ["Company"] if role == "EXECUTIVE" else ["Company", "Department"]
    grain = st.selectbox("Drill-down level", grain_options)

    result, error = aggregate_monthly(metric_id, grain, selected_month)
    if error:
        st.warning(error)
    elif result.empty:
        st.warning("No records are available for the selected period.")
    else:
        if grain == "Department":
            result = suppress_small_groups(result, "Group size")
            if result.empty:
                st.warning("All departments are hidden by the minimum group-size rule.")
            else:
                st.dataframe(result, use_container_width=True, hide_index=True)
        else:
            value = result.iloc[0]["Value"]
            if pd.isna(value):
                st.warning("The metric cannot be calculated because its denominator is zero or missing.")
            else:
                st.metric(metric["metric_name"], f"{value:,.2f}")
                st.caption("Company-level aggregate. Ratios are calculated from summed numerators and denominators, not averages of department percentages.")

# Individual salary-level information is only available in the ADMIN demo.
if role == "ADMIN":
    with st.expander("Admin-only salary-level detail (demo)"):
        payroll = load_csv("fact_payroll.csv")
        if not payroll.empty:
            months = pd.to_datetime(payroll["period_end_date"], errors="coerce").dropna().dt.to_period("M")
            selected = st.selectbox("Salary detail month", sorted(months.unique().tolist()), key="admin_salary_month")
            detail = month_filter(payroll, "period_end_date", selected)
            cols = ["employee_id", "department_id", "gross_pay", "net_pay", "employer_cost"]
            st.dataframe(detail[cols], use_container_width=True, hide_index=True)
        else:
            st.info("Payroll data is unavailable.")
elif role == "HR":
    st.info("HR salary-level detail is disabled until a verified HR-to-department mapping is configured.")

st.caption("Source: data/clean metric dictionary and governed clean fact tables. Demo role selection is not an authentication boundary.")
