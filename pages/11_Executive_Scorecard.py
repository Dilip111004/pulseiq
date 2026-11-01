from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
CLEAN = ROOT / "data" / "clean"

st.set_page_config(
    page_title="PulseIQ | Executive Scorecard",
    page_icon="📊",
    layout="wide",
)

st.markdown("""
<style>
    .block-container {
        padding-top: 1.1rem;
        padding-bottom: 1rem;
    }
    div[data-testid="stMetric"] {
        background: #F4F7FB;
        border: 1px solid #DFE7F1;
        padding: 12px;
        border-radius: 9px;
        color: #1F2937 !important;
    }
    div[data-testid="stMetric"] label,
    div[data-testid="stMetric"] [data-testid="stMetricLabel"],
    div[data-testid="stMetric"] [data-testid="stMetricLabel"] p,
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #1F2937 !important;
    }
    @media print {
        header, [data-testid="stSidebar"], footer,
        [data-testid="stToolbar"], [data-testid="stDecoration"] {
            display: none !important;
        }
        .block-container {
            padding: 0.2rem !important;
            max-width: 100% !important;
        }
        [data-testid="stMetric"] {
            break-inside: avoid;
        }
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def read_metric(filename):
    path = OUTPUTS / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing metric output: {filename}")
    return pd.read_csv(path, low_memory=False)


@st.cache_data
def load_all():
    revenue = read_metric("m16_revenue.csv")
    profit = read_metric("m17_net_profit.csv")
    margin = read_metric("m18_operating_margin.csv")
    payroll = read_metric("m19_payroll_as_pct_revenue.csv")
    dso = read_metric("m20_days_sales_outstanding.csv")
    overdue = read_metric("m21_overdue_receivables.csv")

    attendance = read_metric("m13_attendance_rate.csv")
    overtime = read_metric("m11_overtime_share.csv")
    attrition = read_metric("m04_attrition_rate_monthly.csv")

    targets_path = CLEAN / "kpi_targets.csv"
    departments_path = CLEAN / "dim_department.csv"

    if not targets_path.exists():
        raise FileNotFoundError("Missing data/clean/kpi_targets.csv")
    if not departments_path.exists():
        raise FileNotFoundError("Missing data/clean/dim_department.csv")

    targets = pd.read_csv(targets_path)
    departments = pd.read_csv(departments_path)

    return (
        revenue, profit, margin, payroll, dso, overdue,
        attendance, overtime, attrition, targets, departments
    )


try:
    (
        revenue, profit, margin, payroll, dso, overdue,
        attendance, overtime, attrition, targets, departments
    ) = load_all()
except Exception as exc:
    st.error(f"Unable to load Executive Scorecard data: {exc}")
    st.stop()


# Validate the source columns before calculating any headline values.
required = {
    "revenue": {"month_start_date", "department_id", "account_code", "revenue"},
    "profit": {"month_start_date", "department_id", "net_profit"},
    "margin": {"month_start_date", "department_id", "operating_margin_pct"},
    "payroll": {"month_start_date", "department_id", "payroll_pct_revenue"},
    "dso": {"month_end_date", "department_id", "dso_days"},
    "overdue": {"report_date", "overdue_receivables"},
    "attendance": {"month_end_date", "department_id", "attendance_rate", "group_size"},
    "overtime": {"month_end_date", "department_id", "overtime_share_pct", "group_size"},
    "attrition": {
        "month_start_date", "department_id",
        "attrition_rate_monthly_pct", "group_size"
    },
    "targets": {
        "month", "department_id", "attendance_rate_target",
        "overtime_share_target_pct", "attrition_monthly_target_pct"
    },
    "departments": {"department_id", "department_name"},
}

frames = {
    "revenue": revenue, "profit": profit, "margin": margin,
    "payroll": payroll, "dso": dso, "overdue": overdue,
    "attendance": attendance, "overtime": overtime,
    "attrition": attrition, "targets": targets,
    "departments": departments,
}

for name, columns in required.items():
    missing = columns - set(frames[name].columns)
    if missing:
        st.error(
            f"{name} is missing required columns: "
            + ", ".join(sorted(missing))
        )
        st.stop()


# Normalize source dates and numeric values.
for frame, column in [
    (revenue, "month_start_date"),
    (profit, "month_start_date"),
    (margin, "month_start_date"),
    (payroll, "month_start_date"),
    (attrition, "month_start_date"),
    (targets, "month"),
    (dso, "month_end_date"),
    (attendance, "month_end_date"),
    (overtime, "month_end_date"),
    (overdue, "report_date"),
]:
    frame[column] = pd.to_datetime(frame[column], errors="coerce")

for frame, columns in [
    (revenue, ["revenue"]),
    (profit, ["net_profit"]),
    (margin, ["operating_margin_pct"]),
    (payroll, ["payroll_pct_revenue"]),
    (dso, ["dso_days"]),
    (overdue, ["overdue_receivables"]),
    (attendance, ["attendance_rate", "group_size"]),
    (overtime, ["overtime_share_pct", "group_size"]),
    (attrition, ["attrition_rate_monthly_pct", "group_size"]),
    (targets, [
        "attendance_rate_target",
        "overtime_share_target_pct",
        "attrition_monthly_target_pct",
    ]),
]:
    for column in columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")


# Use only months with company-wide profit, margin and payroll records.
available = set(
    profit.loc[profit["department_id"].eq("ALL"), "month_start_date"]
    .dropna().dt.strftime("%Y-%m").tolist()
)
available &= set(
    margin.loc[margin["department_id"].eq("ALL"), "month_start_date"]
    .dropna().dt.strftime("%Y-%m").tolist()
)
available &= set(
    payroll.loc[payroll["department_id"].eq("ALL"), "month_start_date"]
    .dropna().dt.strftime("%Y-%m").tolist()
)
available &= set(
    revenue.loc[revenue["department_id"].eq("ALL"), "month_start_date"]
    .dropna().dt.strftime("%Y-%m").tolist()
)

months = sorted(available)

if not months:
    st.error("No common company-wide finance reporting months were found.")
    st.stop()


st.title("PulseIQ | Executive Scorecard")
st.caption(
    "PQ-15 | Executive view of company finance and department-level "
    "workforce indicators. Source: governed metric exports and KPI targets."
)

selected_month = st.selectbox(
    "Reporting month",
    options=months,
    index=len(months) - 1,
    format_func=lambda value: pd.Timestamp(value + "-01").strftime("%B %Y"),
)

month_start = pd.Timestamp(selected_month + "-01")
month_end = month_start + pd.offsets.MonthEnd(0)
previous_month = month_start - pd.offsets.MonthBegin(1)
previous_key = previous_month.strftime("%Y-%m")


def one_company_row(frame, date_column, date_value):
    rows = frame[
        frame["department_id"].eq("ALL")
        & frame[date_column].dt.to_period("M").eq(date_value.to_period("M"))
    ]
    return rows.iloc[0] if not rows.empty else None


def money_crore(value):
    if pd.isna(value):
        return "N/A"
    return f"INR {value / 10000000:,.2f} Cr"


def get_value(frame, date_column, date_value, value_column):
    row = one_company_row(frame, date_column, date_value)
    if row is None:
        return None
    value = row[value_column]
    return float(value) if pd.notna(value) else None


def delta_text(current, previous, suffix="", inverse=False):
    if current is None or previous is None:
        return None
    difference = current - previous
    if inverse:
        difference = -difference
    return f"{difference:+,.2f}{suffix} vs previous month"


# Finance headline values.
revenue_rows = revenue[
    revenue["department_id"].eq("ALL")
    & revenue["month_start_date"].dt.to_period("M").eq(month_start.to_period("M"))
]
revenue_value = (
    float(revenue_rows["revenue"].sum())
    if not revenue_rows.empty else None
)

profit_value = get_value(
    profit, "month_start_date", month_start, "net_profit"
)
margin_value = get_value(
    margin, "month_start_date", month_start, "operating_margin_pct"
)
payroll_value = get_value(
    payroll, "month_start_date", month_start, "payroll_pct_revenue"
)
dso_value = get_value(dso, "month_end_date", month_end, "dso_days")

overdue_rows = overdue[
    overdue["report_date"].dt.date.eq(month_end.date())
]
overdue_value = (
    float(overdue_rows["overdue_receivables"].sum())
    if not overdue_rows.empty else None
)

previous_revenue_rows = revenue[
    revenue["department_id"].eq("ALL")
    & revenue["month_start_date"].dt.to_period("M").eq(
        previous_month.to_period("M")
    )
]
previous_revenue = (
    float(previous_revenue_rows["revenue"].sum())
    if not previous_revenue_rows.empty else None
)

previous_profit = get_value(
    profit, "month_start_date", previous_month, "net_profit"
)
previous_margin = get_value(
    margin, "month_start_date", previous_month, "operating_margin_pct"
)
previous_payroll = get_value(
    payroll, "month_start_date", previous_month, "payroll_pct_revenue"
)
previous_dso = get_value(dso, "month_end_date", previous_month, "dso_days")


st.header("1. Company-wide financial health")
st.caption(
    "All values below use department_id = ALL. Revenue is summed across "
    "the four account-code rows. Financial targets are not defined in "
    "kpi_targets.csv, so these KPIs are not traffic-light rated."
)

cards = st.columns(3)

cards[0].metric(
    "Revenue",
    money_crore(revenue_value) if revenue_value is not None else "N/A",
    delta_text(revenue_value, previous_revenue, inverse=False),
)
cards[1].metric(
    "Net profit",
    money_crore(profit_value) if profit_value is not None else "N/A",
    delta_text(profit_value, previous_profit),
)
cards[2].metric(
    "Operating margin",
    f"{margin_value:.2f}%" if margin_value is not None else "N/A",
    delta_text(margin_value, previous_margin, "%"),
)

cards = st.columns(3)

cards[0].metric(
    "Payroll / revenue",
    f"{payroll_value:.2f}%" if payroll_value is not None else "N/A",
    delta_text(payroll_value, previous_payroll, "%", inverse=True),
)
cards[1].metric(
    "Days sales outstanding",
    f"{dso_value:.2f} days" if dso_value is not None else "N/A",
    delta_text(dso_value, previous_dso, " days", inverse=True),
)
cards[2].metric(
    "Overdue receivables",
    money_crore(overdue_value) if overdue_value is not None else "Not available",
    help="Sum of client-level overdue receivables for the selected report date.",
)

st.caption(
    "Overdue receivables are available only for dates present in M21. "
    "A missing value is shown as unavailable, not zero."
)


# Three-month company financial trend.
st.subheader("Three-month financial trend")

trend = []
for key in months:
    date_value = pd.Timestamp(key + "-01")

    rev_rows = revenue[
        revenue["department_id"].eq("ALL")
        & revenue["month_start_date"].dt.to_period("M").eq(
            date_value.to_period("M")
        )
    ]

    rev = float(rev_rows["revenue"].sum()) if not rev_rows.empty else None
    prof = get_value(profit, "month_start_date", date_value, "net_profit")
    marg = get_value(margin, "month_start_date", date_value, "operating_margin_pct")
    pay = get_value(payroll, "month_start_date", date_value, "payroll_pct_revenue")
    dso_month = get_value(
        dso, "month_end_date", date_value + pd.offsets.MonthEnd(0), "dso_days"
    )

    trend.append({
        "Month": date_value.strftime("%b %Y"),
        "Revenue (INR Cr)": rev / 10000000 if rev is not None else None,
        "Net profit (INR Cr)": prof / 10000000 if prof is not None else None,
        "Operating margin (%)": marg,
        "Payroll / revenue (%)": pay,
        "DSO (days)": dso_month,
    })

trend_df = pd.DataFrame(trend).tail(3).set_index("Month")
st.line_chart(trend_df, use_container_width=True)


# Department-level workforce measures.
st.header("2. Department-level workforce performance")
st.caption(
    "These are department-level measures, not company-wide averages. "
    "Targets are compared at the same department and reporting month."
)

att_month = attendance[
    attendance["month_end_date"].dt.to_period("M").eq(month_start.to_period("M"))
].copy()

ot_month = overtime[
    overtime["month_end_date"].dt.to_period("M").eq(month_start.to_period("M"))
].copy()

attr_month = attrition[
    attrition["month_start_date"].dt.to_period("M").eq(month_start.to_period("M"))
].copy()

target_month = targets[
    targets["month"].dt.to_period("M").eq(month_start.to_period("M"))
].copy()

if att_month.empty or ot_month.empty or attr_month.empty or target_month.empty:
    st.warning(
        "One or more workforce metrics or targets are unavailable "
        "for the selected month."
    )

ops = departments[["department_id", "department_name"]].copy()

ops = ops.merge(
    att_month[["department_id", "attendance_rate", "group_size"]].rename(
        columns={"group_size": "attendance_group_size"}
    ),
    on="department_id", how="left",
)

ops = ops.merge(
    ot_month[["department_id", "overtime_share_pct", "group_size"]].rename(
        columns={"group_size": "overtime_group_size"}
    ),
    on="department_id", how="left",
)

ops = ops.merge(
    attr_month[[
        "department_id", "attrition_rate_monthly_pct", "group_size"
    ]].rename(columns={"group_size": "attrition_group_size"}),
    on="department_id", how="left",
)

ops = ops.merge(
    target_month[[
        "department_id", "attendance_rate_target",
        "overtime_share_target_pct", "attrition_monthly_target_pct"
    ]],
    on="department_id", how="left",
)

ops["Attendance (%)"] = ops["attendance_rate"] * 100
ops["Attendance target (%)"] = ops["attendance_rate_target"] * 100
ops["Overtime (%)"] = ops["overtime_share_pct"]
ops["Overtime target (%)"] = ops["overtime_share_target_pct"]
ops["Monthly attrition (%)"] = ops["attrition_rate_monthly_pct"]
ops["Attrition target (%)"] = ops["attrition_monthly_target_pct"]


def status(actual, target, higher_is_better):
    if pd.isna(actual) or pd.isna(target):
        return "Not available"
    passed = actual >= target if higher_is_better else actual <= target
    return "On target" if passed else "Needs attention"


ops["Attendance status"] = ops.apply(
    lambda row: status(
        row["Attendance (%)"], row["Attendance target (%)"], True
    ), axis=1
)
ops["Overtime status"] = ops.apply(
    lambda row: status(
        row["Overtime (%)"], row["Overtime target (%)"], False
    ), axis=1
)
ops["Attrition status"] = ops.apply(
    lambda row: status(
        row["Monthly attrition (%)"], row["Attrition target (%)"], False
    ), axis=1
)

display_columns = [
    "department_id", "department_name",
    "Attendance (%)", "Attendance target (%)", "Attendance status",
    "Overtime (%)", "Overtime target (%)", "Overtime status",
    "Monthly attrition (%)", "Attrition target (%)", "Attrition status",
]

display_ops = ops[display_columns].copy()

for column in [
    "Attendance (%)", "Attendance target (%)",
    "Overtime (%)", "Overtime target (%)",
    "Monthly attrition (%)", "Attrition target (%)",
]:
    display_ops[column] = display_ops[column].map(
        lambda value: f"{value:.2f}%" if pd.notna(value) else "N/A"
    )

st.dataframe(
    display_ops,
    hide_index=True,
    use_container_width=True,
)

st.caption(
    "Attendance is on target when it meets or exceeds its target. "
    "Overtime and monthly attrition are on target when they are at or "
    "below their targets. Department-level group sizes are retained in "
    "the source metric outputs."
)


# Month-over-month insight strip.
st.header("3. What changed since last month")

insights = []

if revenue_value is not None and previous_revenue is not None:
    change = revenue_value - previous_revenue
    direction = "increased" if change > 0 else "decreased" if change < 0 else "was unchanged"
    insights.append(
        f"Revenue {direction} by {money_crore(abs(change))}."
    )

if profit_value is not None and previous_profit is not None:
    change = profit_value - previous_profit
    direction = "increased" if change > 0 else "decreased" if change < 0 else "was unchanged"
    insights.append(
        f"Net profit {direction} by {money_crore(abs(change))}."
    )

if margin_value is not None and previous_margin is not None:
    change = margin_value - previous_margin
    direction = "increased" if change > 0 else "decreased" if change < 0 else "was unchanged"
    insights.append(
        f"Operating margin {direction} by {abs(change):.2f} percentage points."
    )

if payroll_value is not None and previous_payroll is not None:
    change = payroll_value - previous_payroll
    direction = "increased" if change > 0 else "decreased" if change < 0 else "was unchanged"
    insights.append(
        f"Payroll as a share of revenue {direction} by {abs(change):.2f} percentage points."
    )

if dso_value is not None and previous_dso is not None:
    change = dso_value - previous_dso
    direction = "increased" if change > 0 else "decreased" if change < 0 else "was unchanged"
    insights.append(
        f"DSO {direction} by {abs(change):.2f} days."
    )

if insights:
    for item in insights:
        st.write(f"- {item}")
else:
    st.info("Previous-month comparison is unavailable for this selection.")


st.divider()
st.caption(
    "Metric lineage: M16–M21 for financial KPIs; M04, M11 and M13 "
    "for department-level workforce indicators; kpi_targets.csv for "
    "operational targets. No financial target thresholds are present "
    "in the supplied target file."
)

