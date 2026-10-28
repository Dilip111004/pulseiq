from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# --------------------------------------------------
# PulseIQ | Phase 2, Task 6: Attendance & Leave Trends
# --------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "clean"

MIN_GROUP_SIZE = 5


@st.cache_data
def load_csv(filename):
    path = DATA / filename
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)


def add_department_names(df, departments):
    if df.empty or "department_id" not in df.columns:
        return df.copy()
    return df.merge(departments, on="department_id", how="left")


def safe_date(series):
    return pd.to_datetime(series, errors="coerce")


attendance = load_csv("fact_attendance_monthly.csv")
leave = load_csv("fact_leave.csv")
calendar = load_csv("dim_date.csv")
departments = load_csv("dim_department.csv")
employees = load_csv("dim_employee.csv")
leave_types = load_csv("dim_leave_type.csv")

st.title("Attendance & Leave Trends")
st.caption(
    "PulseIQ Phase 2 | Task 6 — monthly attendance, lateness, "
    "overtime, approved leave and calendar context."
)

required_attendance = {
    "employee_id", "department_id", "period_end_date",
    "scheduled_days", "present_days", "half_days_unpaid",
    "late_arrivals", "overtime_hours",
}
if attendance.empty or not required_attendance.issubset(attendance.columns):
    st.error("Attendance data is missing or does not contain the required columns.")
    st.stop()

if departments.empty or not {
    "department_id", "department_name"
}.issubset(departments.columns):
    st.error("Department dimension is missing or incomplete.")
    st.stop()

attendance["period_end_date"] = safe_date(attendance["period_end_date"])
for col in [
    "scheduled_days", "present_days", "half_days_unpaid",
    "late_arrivals", "overtime_hours",
]:
    attendance[col] = pd.to_numeric(attendance[col], errors="coerce").fillna(0)

department_map = departments[["department_id", "department_name"]].drop_duplicates()
attendance = add_department_names(attendance, department_map)
attendance = attendance.dropna(subset=["period_end_date", "department_name"])

min_date = attendance["period_end_date"].min().date()
max_date = attendance["period_end_date"].max().date()

with st.sidebar:
    st.header("Filters")
    selected_range = st.date_input(
        "Month-end date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    department_options = sorted(attendance["department_name"].dropna().unique())
    selected_departments = st.multiselect(
        "Department",
        options=department_options,
        default=department_options,
    )

if not isinstance(selected_range, (tuple, list)) or len(selected_range) != 2:
    st.info("Select both a start and end date to display the trends.")
    st.stop()

start_date, end_date = selected_range
period_start = pd.Timestamp(start_date).to_period('M').start_time
period_end = pd.Timestamp(end_date).to_period('M').end_time.normalize()
if start_date > end_date:
    st.error("The start date must be on or before the end date.")
    st.stop()

filtered = attendance[
    attendance["period_end_date"].between(
        pd.Timestamp(start_date), pd.Timestamp(end_date)
    )
    & attendance["department_name"].isin(selected_departments)
].copy()

if filtered.empty:
    st.warning("No attendance records match the selected filters.")
    st.stop()

filtered["attendance_numerator"] = (
    filtered["present_days"] + 0.5 * filtered["half_days_unpaid"]
)

monthly = filtered.groupby("period_end_date", as_index=False).agg(
    scheduled_days=("scheduled_days", "sum"),
    present_days=("present_days", "sum"),
    attendance_numerator=("attendance_numerator", "sum"),
    late_arrivals=("late_arrivals", "sum"),
    overtime_hours=("overtime_hours", "sum"),
    employees=("employee_id", "nunique"),
)
monthly["attendance_rate_pct"] = (
    monthly["attendance_numerator"]
    / monthly["scheduled_days"].replace(0, pd.NA) * 100
)
monthly["late_per_100_present_days"] = (
    monthly["late_arrivals"]
    / monthly["present_days"].replace(0, pd.NA) * 100
)
monthly = monthly.sort_values("period_end_date")

st.subheader("Monthly overview")

latest = monthly.iloc[-1]
previous = monthly.iloc[-2] if len(monthly) > 1 else None

col1, col2, col3, col4 = st.columns(4)
col1.metric(
    "Latest attendance rate",
    f"{latest['attendance_rate_pct']:.2f}%"
    if pd.notna(latest["attendance_rate_pct"]) else "N/A",
    f"{latest['attendance_rate_pct'] - previous['attendance_rate_pct']:+.2f} pp"
    if previous is not None
    and pd.notna(latest["attendance_rate_pct"])
    and pd.notna(previous["attendance_rate_pct"])
    else None,
)
col2.metric("Latest late arrivals", f"{latest['late_arrivals']:,.0f}")
col3.metric("Latest overtime hours", f"{latest['overtime_hours']:,.1f}")
col4.metric("Scheduled employee-days", f"{latest['scheduled_days']:,.0f}")

attendance_chart = px.line(
    monthly,
    x="period_end_date",
    y="attendance_rate_pct",
    markers=True,
    title="Monthly attendance rate",
    labels={
        "period_end_date": "Month",
        "attendance_rate_pct": "Attendance rate (%)",
    },
)
attendance_chart.update_yaxes(ticksuffix="%", rangemode="tozero")
st.plotly_chart(attendance_chart, width="stretch")

late_chart = px.bar(
    monthly,
    x="period_end_date",
    y="late_per_100_present_days",
    title="Late arrivals per 100 present days",
    labels={
        "period_end_date": "Month",
        "late_per_100_present_days": "Late arrivals per 100 present days",
    },
)
st.plotly_chart(late_chart, width="stretch")

overtime_chart = px.bar(
    monthly,
    x="period_end_date",
    y="overtime_hours",
    title="Monthly overtime hours",
    labels={"period_end_date": "Month", "overtime_hours": "Overtime hours"},
)
st.plotly_chart(overtime_chart, width="stretch")

st.subheader("Department comparison")

dept_month = filtered.groupby(
    ["period_end_date", "department_id", "department_name"],
    as_index=False,
).agg(
    employees=("employee_id", "nunique"),
    scheduled_days=("scheduled_days", "sum"),
    present_days=("present_days", "sum"),
    attendance_numerator=("attendance_numerator", "sum"),
    late_arrivals=("late_arrivals", "sum"),
    overtime_hours=("overtime_hours", "sum"),
)
dept_month = dept_month[dept_month["employees"] >= MIN_GROUP_SIZE].copy()
dept_month["attendance_rate_pct"] = (
    dept_month["attendance_numerator"]
    / dept_month["scheduled_days"].replace(0, pd.NA) * 100
)
dept_month["late_per_100_present_days"] = (
    dept_month["late_arrivals"]
    / dept_month["present_days"].replace(0, pd.NA) * 100
)
dept_month["overtime_per_100_scheduled_days"] = (
    dept_month["overtime_hours"]
    / dept_month["scheduled_days"].replace(0, pd.NA) * 100
)

if not dept_month.empty:
    dept_chart = px.line(
        dept_month,
        x="period_end_date",
        y="attendance_rate_pct",
        color="department_name",
        markers=True,
        title="Attendance rate by department",
        labels={
            "period_end_date": "Month",
            "attendance_rate_pct": "Attendance rate (%)",
            "department_name": "Department",
        },
    )
    st.plotly_chart(dept_chart, width="stretch")

    overtime_dept_chart = px.line(
        dept_month,
        x="period_end_date",
        y="overtime_per_100_scheduled_days",
        color="department_name",
        markers=True,
        title="Overtime hours per 100 scheduled employee-days",
        labels={
            "period_end_date": "Month",
            "overtime_per_100_scheduled_days": "Overtime hours per 100 scheduled days",
            "department_name": "Department",
        },
    )
    st.plotly_chart(overtime_dept_chart, width="stretch")

    st.caption(
        "Department-month groups with fewer than five distinct employees "
        "are excluded from these comparisons."
    )
else:
    st.info("No department-month groups meet the minimum group-size requirement.")

st.subheader("Approved leave trends")

if leave.empty or not {
    "leave_request_id", "employee_id", "start_date", "end_date",
    "days", "status", "leave_type_code",
}.issubset(leave.columns):
    st.warning("Leave data is missing or does not contain the required columns.")
else:
    leave["start_date"] = safe_date(leave["start_date"])
    leave["end_date"] = safe_date(leave["end_date"])
    leave["days"] = pd.to_numeric(leave["days"], errors="coerce").fillna(0)

    if not {
        "employee_id", "department_id", "valid_from", "valid_to"
    }.issubset(employees.columns):
        st.warning("Employee history is unavailable; leave cannot be filtered by department.")
        leave_with_dept = pd.DataFrame()
    else:
        employees["valid_from"] = safe_date(employees["valid_from"])
        employees["valid_to"] = safe_date(employees["valid_to"])

        leave_with_dept = leave.merge(
            employees[
                ["employee_id", "department_id", "valid_from", "valid_to"]
            ],
            on="employee_id",
            how="left",
        )
        valid = (
            leave_with_dept["start_date"].ge(leave_with_dept["valid_from"])
            & (
                leave_with_dept["valid_to"].isna()
                | leave_with_dept["start_date"].le(leave_with_dept["valid_to"])
            )
        )
        leave_with_dept = leave_with_dept[valid].copy()
        leave_with_dept = add_department_names(leave_with_dept, department_map)

    if not leave_with_dept.empty:
        approved = leave_with_dept[
            leave_with_dept["status"].astype(str).str.strip().str.lower().eq("approved")
            & leave_with_dept["start_date"].between(
                period_start, period_end
            )
            & leave_with_dept["department_name"].isin(selected_departments)
        ].copy()

        if not approved.empty:
            approved["request_month"] = (
                approved["start_date"].dt.to_period("M").dt.to_timestamp()
            )
            leave_monthly = approved.groupby("request_month", as_index=False).agg(
                requests=("leave_request_id", "nunique"),
                approved_leave_days=("days", "sum"),
            )

            leave_chart = px.bar(
                leave_monthly,
                x="request_month",
                y="approved_leave_days",
                title="Approved leave days by request start month",
                labels={
                    "request_month": "Request start month",
                    "approved_leave_days": "Approved leave days",
                },
            )
            st.plotly_chart(leave_chart, width="stretch")

            leave_summary = approved.merge(
                leave_types[["leave_type_code", "leave_type_name"]].drop_duplicates()
                if not leave_types.empty and {
                    "leave_type_code", "leave_type_name"
                }.issubset(leave_types.columns)
                else pd.DataFrame(columns=["leave_type_code", "leave_type_name"]),
                on="leave_type_code",
                how="left",
            )
            leave_summary["leave_type_name"] = (
                leave_summary["leave_type_name"].fillna(leave_summary["leave_type_code"])
            )
            leave_by_type = leave_summary.groupby(
                "leave_type_name", as_index=False
            ).agg(
                requests=("leave_request_id", "nunique"),
                approved_leave_days=("days", "sum"),
                employees=("employee_id", "nunique"),
            )
            leave_by_type = leave_by_type[
                leave_by_type["employees"] >= MIN_GROUP_SIZE
            ]
            if not leave_by_type.empty:
                type_chart = px.bar(
                    leave_by_type.sort_values("approved_leave_days", ascending=False),
                    x="leave_type_name",
                    y="approved_leave_days",
                    title="Approved leave days by leave type",
                    labels={
                        "leave_type_name": "Leave type",
                        "approved_leave_days": "Approved leave days",
                    },
                )
                st.plotly_chart(type_chart, width="stretch")
            else:
                st.info(
                    "Leave-type groups are suppressed because fewer than five "
                    "distinct employees appear in each group."
                )

            crossing = approved[
                approved["start_date"].dt.to_period("M")
                != approved["end_date"].dt.to_period("M")
            ]
            st.caption(
                f"{len(crossing)} of {len(approved):,} approved requests in the "
                "selected filters cross month boundaries. Monthly leave totals are "
                "assigned to the request start month because daily leave allocation "
                "is not available in the source data."
            )
        else:
            st.info("No approved leave requests match the selected filters.")
    else:
        st.warning("Could not match leave requests to historical department records.")

st.subheader("Holiday and long-weekend context")

if not calendar.empty and {"date", "is_holiday", "is_weekend"}.issubset(calendar.columns):
    calendar["date"] = safe_date(calendar["date"])
    period_calendar = calendar[
        calendar["date"].between(period_start, period_end)
    ].copy()
    period_calendar["is_holiday"] = (
        period_calendar["is_holiday"].astype(str).str.upper().eq("Y")
    )
    period_calendar["is_weekend"] = (
        period_calendar["is_weekend"].astype(str).str.upper().eq("Y")
    )
    holiday_dates = period_calendar[period_calendar["is_holiday"]].copy()
    holiday_dates["day_name"] = holiday_dates["date"].dt.day_name()

    # Flag holidays within a run of at least 3 consecutive weekend/holiday dates.
    non_working = (
        period_calendar["is_weekend"] | period_calendar["is_holiday"]
    )
    non_working_by_date = pd.Series(
        non_working.to_numpy(),
        index=period_calendar["date"],
    ).sort_index()

    date_gaps = non_working_by_date.index.to_series().diff().dt.days.ne(1)
    run_ids = date_gaps.cumsum()
    run_lengths = non_working_by_date.groupby(run_ids).transform("size")
    qualifying_dates = set(
        non_working_by_date.index[
            non_working_by_date.to_numpy() & run_lengths.ge(3).to_numpy()
        ]
    )
    holiday_dates["long_weekend_context"] = holiday_dates["date"].isin(
        qualifying_dates
    )
    holiday_dates["date"] = holiday_dates["date"].dt.strftime("%Y-%m-%d")
    holiday_dates = holiday_dates.rename(
        columns={"date": "Holiday date", "day_name": "Weekday"}
    )

    st.write(
        f"Calendar contains {len(holiday_dates)} holiday dates in the selected period."
    )
    if not holiday_dates.empty:
        st.dataframe(
            holiday_dates[
                ["Holiday date", "Weekday", "is_weekend", "long_weekend_context"]
            ].rename(
                columns={
                    "is_weekend": "Falls on weekend",
                    "long_weekend_context": "Part of 3+ consecutive weekend/holiday dates",
                }
            ),
            width="stretch",
            hide_index=True,
        )
    st.caption(
        "Holidays in runs of at least three consecutive weekend/holiday dates are flagged. "
        "A holiday on a weekend is counted once. Attendance rates use scheduled "
        "employee-days as the denominator; calendar flags provide context only."
    )
else:
    st.info("Calendar holiday flags are unavailable.")

st.subheader("Numeric findings")

lowest_attendance = monthly.dropna(subset=["attendance_rate_pct"]).nsmallest(
    1, "attendance_rate_pct"
)
highest_late = monthly.dropna(subset=["late_per_100_present_days"]).nlargest(
    1, "late_per_100_present_days"
)
highest_overtime = monthly.nlargest(1, "overtime_hours")

insight_cols = st.columns(3)
if not lowest_attendance.empty:
    r = lowest_attendance.iloc[0]
    insight_cols[0].write(
        f"**Lowest attendance:** {r['period_end_date']:%B %Y}, "
        f"{r['attendance_rate_pct']:.2f}%."
    )
if not highest_late.empty:
    r = highest_late.iloc[0]
    insight_cols[1].write(
        f"**Highest lateness rate:** {r['period_end_date']:%B %Y}, "
        f"{r['late_per_100_present_days']:.2f} late arrivals per 100 present days."
    )
if not highest_overtime.empty:
    r = highest_overtime.iloc[0]
    insight_cols[2].write(
        f"**Highest overtime:** {r['period_end_date']:%B %Y}, "
        f"{r['overtime_hours']:.1f} hours."
    )

st.caption(
    "Interpretation note: these are descriptive patterns, not proof of cause. "
    "The official attendance formula is (present days + 0.5 × unpaid half-days) "
    "÷ scheduled days. The official late-arrival rate is late arrivals ÷ present days."
)
