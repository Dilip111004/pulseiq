from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
CLEAN = ROOT / "data" / "clean"

st.set_page_config(
    page_title="PulseIQ | Executive Scorecard",
    page_icon="ðŸ“Š",
    layout="wide"
)

st.markdown("""
<style>
.block-container {
    padding-top: 5.0rem;
    padding-bottom: 0.5rem;
}
.kpi-reason {
    font-size: 0.78rem;
    color: #64748b;
    min-height: 38px;
}
.kpi-target {
    font-size: 0.78rem;
    color: #475569;
}
.kpi-status {
    font-size: 0.8rem;
    font-weight: 600;
}
.kpi-reason + [data-testid="stPageLink"] {
    max-width: 100%;
}
[data-testid="stPageLink"] a {
    width: 100%;
    box-sizing: border-box;
    justify-content: center;
    white-space: normal;
    overflow-wrap: anywhere;
    text-align: center;
}
@media print {
    @page {
        size: A4 landscape;
        margin: 7mm;
    }
    header, footer, [data-testid="stSidebar"],
    [data-testid="stToolbar"], [data-testid="stDecoration"],
    [data-testid="stHeaderActionElements"],
    .stButton, [data-testid="stPageLink"] {
        display: none !important;
    }
    .block-container {
        padding: 0 !important;
        max-width: 100% !important;
    }
    [data-testid="stMetric"] {
        break-inside: avoid;
        padding: 5px !important;
    }
    .kpi-reason {
        font-size: 8pt;
        min-height: 25px;
    }
    h1 {
        font-size: 20pt !important;
    }
    h2, h3 {
        font-size: 12pt !important;
    }
    [data-testid="stVerticalBlock"] {
        gap: 0.35rem;
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
def load_data():
    return {
        "revenue": read_metric("m16_revenue.csv"),
        "profit": read_metric("m17_net_profit.csv"),
        "margin": read_metric("m18_operating_margin.csv"),
        "payroll": read_metric("m19_payroll_as_pct_revenue.csv"),
        "dso": read_metric("m20_days_sales_outstanding.csv"),
        "overdue": read_metric("m21_overdue_receivables.csv"),
        "attendance": read_metric("m13_attendance_rate.csv"),
        "attrition": read_metric("m04_attrition_rate_monthly.csv"),
        "overtime": read_metric("m11_overtime_share.csv"),
        "targets": pd.read_csv(CLEAN / "kpi_targets.csv"),
        "financial_targets": pd.read_csv(CLEAN / "financial_kpi_targets.csv"),
    }


try:
    data = load_data()
except Exception as exc:
    st.error(f"Unable to load scorecard data: {exc}")
    st.stop()


date_columns = {
    "revenue": "month_start_date",
    "profit": "month_start_date",
    "margin": "month_start_date",
    "payroll": "month_start_date",
    "dso": "month_end_date",
    "overdue": "report_date",
    "attendance": "month_end_date",
    "attrition": "month_start_date",
    "overtime": "month_end_date",
    "targets": "month",
    "financial_targets": "month",
}

for name, column in date_columns.items():
    data[name][column] = pd.to_datetime(
        data[name][column], errors="coerce"
    )

numeric_columns = {
    "revenue": ["revenue"],
    "profit": ["net_profit"],
    "margin": ["operating_margin_pct"],
    "payroll": ["payroll_pct_revenue"],
    "dso": ["dso_days"],
    "overdue": ["overdue_receivables"],
    "attendance": ["attendance_rate", "group_size"],
    "attrition": ["attrition_rate_monthly_pct", "group_size"],
    "targets": [
        "attendance_rate_target",
        "attrition_monthly_target_pct",
        "overtime_share_target_pct",
    ],
    "financial_targets": [
        "revenue_target",
        "net_profit_target",
        "operating_margin_target_pct",
        "payroll_pct_revenue_target",
        "overdue_receivables_target",
        "dso_target_days",
    ],
}

for name, columns in numeric_columns.items():
    for column in columns:
        data[name][column] = pd.to_numeric(
            data[name][column], errors="coerce"
        )


# Company-wide financial reporting months.
available = set(
    data["revenue"].loc[
        data["revenue"]["department_id"].eq("ALL"),
        "month_start_date"
    ].dropna().dt.strftime("%Y-%m")
)

for name in ["profit", "margin", "payroll"]:
    months_for_metric = set(
        data[name].loc[
            data[name]["department_id"].eq("ALL"),
            "month_start_date"
        ].dropna().dt.strftime("%Y-%m")
    )
    available &= months_for_metric

months = sorted(available)

if not months:
    st.error("No common financial reporting months are available.")
    st.stop()


def company_value(name, date_column, month, value_column):
    frame = data[name]
    rows = frame[
        frame["department_id"].eq("ALL")
        & frame[date_column].dt.to_period("M").eq(
            pd.Period(month, freq="M")
        )
    ]
    if rows.empty:
        return None

    values = pd.to_numeric(rows[value_column], errors="coerce").dropna()
    return float(values.sum()) if not values.empty else None


def weighted_value(frame, date_column, month, value_column):
    rows = frame[
        frame[date_column].dt.to_period("M").eq(
            pd.Period(month, freq="M")
        )
    ].copy()

    rows = rows.dropna(subset=[value_column, "group_size"])
    rows = rows[rows["group_size"] > 0]

    if rows.empty:
        return None

    return float(
        (rows[value_column] * rows["group_size"]).sum()
        / rows["group_size"].sum()
    )


def weighted_target(month, target_column, group_frame, date_column):
    targets = data["targets"][
        data["targets"]["month"].dt.to_period("M").eq(
            pd.Period(month, freq="M")
        )
    ][["department_id", target_column]].copy()

    weights = group_frame[
        group_frame[date_column].dt.to_period("M").eq(
            pd.Period(month, freq="M")
        )
    ][["department_id", "group_size"]].copy()

    merged = targets.merge(
        weights, on="department_id", how="inner",
        validate="one_to_one"
    ).dropna(subset=[target_column, "group_size"])

    merged = merged[merged["group_size"] > 0]

    if merged.empty:
        return None

    return float(
        (merged[target_column] * merged["group_size"]).sum()
        / merged["group_size"].sum()
    )


def month_end(month):
    return pd.Period(month, freq="M").end_time.normalize()


def get_values(month):
    end = month_end(month)

    revenue_rows = data["revenue"][
        data["revenue"]["department_id"].eq("ALL")
        & data["revenue"]["month_start_date"].dt.to_period("M").eq(
            pd.Period(month, freq="M")
        )
    ]

    revenue = (
        float(revenue_rows["revenue"].sum())
        if not revenue_rows.empty else None
    )

    return {
        "Revenue": revenue,
        "Net profit": company_value(
            "profit", "month_start_date", month, "net_profit"
        ),
        "Operating margin": company_value(
            "margin", "month_start_date", month,
            "operating_margin_pct"
        ),
        "Payroll / revenue": company_value(
            "payroll", "month_start_date", month,
            "payroll_pct_revenue"
        ),
        "Overdue receivables": company_value(
            "overdue", "report_date", end.strftime("%Y-%m"),
            "overdue_receivables"
        ),
        "DSO": company_value(
            "dso", "month_end_date", month, "dso_days"
        ),
        "Attendance": weighted_value(
            data["attendance"], "month_end_date", month,
            "attendance_rate"
        ),
        "Attrition": weighted_value(
            data["attrition"], "month_start_date", month,
            "attrition_rate_monthly_pct"
        ),
    }


def get_target(name, month):
    if name == "Attendance":
        return weighted_target(
            month, "attendance_rate_target",
            data["attendance"], "month_end_date"
        )
    if name == "Attrition":
        return weighted_target(
            month, "attrition_monthly_target_pct",
            data["attrition"], "month_start_date"
        )

    target_columns = {
        "Revenue": "revenue_target",
        "Net profit": "net_profit_target",
        "Operating margin": "operating_margin_target_pct",
        "Payroll / revenue": "payroll_pct_revenue_target",
        "Overdue receivables": "overdue_receivables_target",
        "DSO": "dso_target_days",
    }
    column = target_columns.get(name)
    if column is None:
        return None

    rows = data["financial_targets"][
        data["financial_targets"]["month"].dt.to_period("M")
        == pd.Period(month, freq="M")
    ]
    if rows.empty or pd.isna(rows.iloc[0][column]):
        return None
    return float(rows.iloc[0][column])


def format_value(name, value):
    if value is None or pd.isna(value):
        return "N/A"

    if name in ["Revenue", "Net profit", "Overdue receivables"]:
        return f"\u20B9{value / 10000000:,.2f} Cr"
    if name == "DSO":
        return f"{value:.1f} days"
    if name == "Attendance":
        return f"{value * 100:.2f}%"
    return f"{value:.2f}%"


def format_target(name, target):
    if target is None or pd.isna(target):
        return "Target: Not configured"
    if name in ["Revenue", "Net profit", "Overdue receivables"]:
        return f"Target: \u20B9{target / 10000000:,.2f} Cr"
    if name == "DSO":
        return f"Target: {target:.1f} days"
    if name == "Attendance":
        return f"Target: {target * 100:.2f}%"
    return f"Target: {target:.2f}%"


def get_status(name, value, target):
    if value is None or target is None:
        return "Not configured", "âšª"

    higher_is_better = [
        "Revenue", "Net profit", "Operating margin", "Attendance"
    ]
    if name in higher_is_better:
        passed = value >= target
    else:
        passed = value <= target

    return ("On target", "ðŸŸ¢") if passed else ("Needs attention", "ðŸ”´")


def trend_text(current, previous, name):
    if current is None or previous is None:
        return "Trend: unavailable"

    difference = current - previous

    if name in ["Revenue", "Net profit", "Overdue receivables"]:
        return f"Change: INR {abs(difference) / 10000000:.2f} Cr"
    if name == "DSO":
        return f"Change: {difference:+.2f} days"
    if name == "Attendance":
        return f"Change: {difference * 100:+.2f} pp"
    return f"Change: {difference:+.2f} pp"


reasons = {
    "Revenue": "Shows the scale of business income generated.",
    "Net profit": "Shows how much profit remains after expenses.",
    "Operating margin": "Measures profitability relative to operating revenue.",
    "Payroll / revenue": "Shows how much revenue is consumed by payroll.",
    "Overdue receivables": "Highlights money clients have not paid on time.",
    "DSO": "Shows how long the business takes to collect sales revenue.",
    "Attendance": "Indicates workforce availability and operational reliability.",
    "Attrition": "Tracks the rate at which employees leave the organisation.",
}

details = {
    "Revenue": ("pages/13_PL_and_Expense_Analytics.py", "P&L and Expense Analytics"),
    "Net profit": ("pages/13_PL_and_Expense_Analytics.py", "P&L and Expense Analytics"),
    "Operating margin": ("pages/13_PL_and_Expense_Analytics.py", "P&L and Expense Analytics"),
    "Payroll / revenue": ("pages/13_PL_and_Expense_Analytics.py", "P&L and Expense Analytics"),
    "Overdue receivables": ("pages/14_Invoices_Receivables_Cash_Flow.py", "Invoices and Receivables"),
    "DSO": ("pages/14_Invoices_Receivables_Cash_Flow.py", "Invoices and Receivables"),
    "Attendance": ("pages/2_Attendance_and_Leave.py", "Attendance and Leave"),
    "Attrition": ("pages/3_Attrition_Analytics.py", "Attrition Analytics"),
}

st.title("PQ-15 | Executive Company-Health Scorecard")
st.caption(
    "PQ-15 | Eight founder-level KPIs | Governed metric views and supplied targets"
)

selected_month = st.selectbox(
    "Reporting month",
    options=months,
    index=len(months) - 1,
    format_func=lambda value: pd.Timestamp(
        value + "-01"
    ).strftime("%B %Y")
)

current = get_values(selected_month)
selected_index = months.index(selected_month)
previous_month = months[selected_index - 1] if selected_index > 0 else None
previous = get_values(previous_month) if previous_month else {}

st.subheader("Eight headline KPIs")

kpi_names = [
    "Revenue", "Net profit", "Operating margin", "Payroll / revenue",
    "Overdue receivables", "DSO", "Attendance", "Attrition"
]

for row_start in [0, 4]:
    columns = st.columns(4)
    for i, name in enumerate(kpi_names[row_start:row_start + 4]):
        value = current[name]
        target = get_target(name, selected_month)
        status, symbol = get_status(name, value, target)
        previous_value = previous.get(name)

        with columns[i]:
            with st.container(border=True):
                st.markdown(f"**{name}**")
                st.metric(
                    label="Current value",
                    value=format_value(name, value),
                    delta=trend_text(value, previous_value, name)
                    if previous_month else None,
                    delta_color="off"
                )
                st.markdown(
                    f'<div class="kpi-target">{format_target(name, target)}</div>',
                    unsafe_allow_html=True
                )
                st.markdown(
                    f'<div class="kpi-status">{status}</div>',
                    unsafe_allow_html=True
                )
                st.markdown(
                    f'<div class="kpi-reason">{reasons[name]}</div>',
                    unsafe_allow_html=True
                )
                page, label = details[name]
                st.page_link(page, label="Open details", use_container_width=True)


st.divider()
st.subheader("Three-month financial trend")

trend_rows = []
for month in months[-3:]:
    values = get_values(month)
    trend_rows.append({
        "Month": pd.Timestamp(month + "-01").strftime("%b %Y"),
        "Revenue (INR Cr)": (
            values["Revenue"] / 10000000
            if values["Revenue"] is not None else None
        ),
        "Net profit (INR Cr)": (
            values["Net profit"] / 10000000
            if values["Net profit"] is not None else None
        ),
    })

trend_df = pd.DataFrame(trend_rows).set_index("Month")
st.line_chart(trend_df, use_container_width=True)


st.subheader("Target and status methodology")
st.caption(
    "Attendance and attrition targets are weighted by the corresponding "
    "department group sizes. Attendance is on target when it meets or "
    "exceeds its target; attrition is on target when it is at or below "
    "its target. Financial targets are not present in the supplied "
    "kpi_targets.csv, so financial KPIs are marked Not rated rather than "
    "being assigned invented thresholds."
)

st.subheader("Why these eight KPIs?")
st.markdown("""
| KPI | Why a founder needs it |
|---|---|
| Revenue | Measures business income and commercial scale. |
| Net profit | Shows whether the business is generating profit. |
| Operating margin | Shows operating profitability. |
| Payroll / revenue | Highlights workforce cost relative to revenue. |
| Overdue receivables | Identifies delayed customer collections. |
| DSO | Measures the speed of receivables collection. |
| Attendance | Indicates workforce availability. |
| Attrition | Signals employee exits and workforce stability. |
""")

st.subheader("Three measures not selected as headline KPIs")
st.markdown("""
1. **Overtime share:** Useful operational diagnostic, but it is better
   retained as a supporting workforce measure alongside attendance.
2. **Forecast accuracy:** The supplied forecast-error output has no
   overlapping actuals for the forecast horizon, so measured accuracy
   cannot currently be reported.
3. **Task completion:** A target exists in `kpi_targets.csv`, but no
   corresponding task-completion metric view was supplied for this
   scorecard. A target alone is not a measured KPI.
""")

st.divider()
st.caption(
    "Traceability: M16 revenue | M17 net profit | M18 operating margin | "
    "M19 payroll/revenue | M20 DSO | M21 overdue receivables | "
    "M13 attendance | M04 attrition | kpi_targets.csv for operational targets."
)

