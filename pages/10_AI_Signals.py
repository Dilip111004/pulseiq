from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
OUTPUTS = ROOT / "outputs"

st.set_page_config(
    page_title="PQ-14 | AI Signals",
    page_icon="🤖",
    layout="wide",
)

st.title("PQ-14 | AI Signals Dashboard")
st.caption(
    "Anomaly monitoring and forecast analysis | "
    "AI-generated outputs are labelled and should not be treated as confirmed facts."
)


@st.cache_data
def load_data():
    anomaly = pd.read_csv(CLEAN / "fact_anomaly.csv")
    forecast = pd.read_csv(CLEAN / "fact_forecast.csv")
    actual = pd.read_csv(CLEAN / "fact_headcount_monthly.csv")
    forecast_error = pd.read_csv(OUTPUTS / "m28_forecast_error_mape.csv")

    anomaly["money_at_risk"] = pd.to_numeric(
        anomaly["money_at_risk"], errors="coerce"
    )

    forecast["forecast_month"] = pd.to_datetime(
        forecast["forecast_month"], errors="coerce"
    )
    forecast["forecast_value"] = pd.to_numeric(
        forecast["forecast_value"], errors="coerce"
    )
    forecast["lower_80"] = pd.to_numeric(
        forecast["lower_80"], errors="coerce"
    )
    forecast["upper_80"] = pd.to_numeric(
        forecast["upper_80"], errors="coerce"
    )

    actual["month_start_date"] = pd.to_datetime(
        actual["month_start_date"], errors="coerce"
    )
    actual["headcount_end"] = pd.to_numeric(
        actual["headcount_end"], errors="coerce"
    )

    return anomaly, forecast, actual, forecast_error


try:
    anomaly, forecast, actual, forecast_error = load_data()
except FileNotFoundError as exc:
    st.error(f"Required project file is missing: {exc}")
    st.stop()
except Exception as exc:
    st.error(f"Unable to load AI Signals data: {exc}")
    st.stop()


# ---------------------------------------------------------
# ANOMALY OVERVIEW
# ---------------------------------------------------------

st.header("1. Anomaly Detection")

payroll_anomalies = anomaly[
    anomaly["source_dataset"].eq("payroll_monthly_features")
].copy()

attendance_anomalies = anomaly[
    anomaly["source_dataset"].eq("attendance_monthly_features")
].copy()

total_flags = int(anomaly["flagged"].fillna(False).astype(bool).sum())
payroll_risk = payroll_anomalies["money_at_risk"].sum(min_count=1)
payroll_risk = 0 if pd.isna(payroll_risk) else float(payroll_risk)

money_records = int(payroll_anomalies["money_at_risk"].notna().sum())

col1, col2, col3, col4 = st.columns(4)

col1.metric("Anomaly records", f"{len(anomaly):,}")
col2.metric("Flagged records", f"{total_flags:,}")
col3.metric("Payroll money at risk", f"₹{payroll_risk:,.0f}")
col4.metric("Payroll risk records", f"{money_records:,}")

st.caption(
    "Money at risk is summed only for payroll anomalies. "
    "Attendance anomaly records do not contain money-at-risk values in the source data."
)

reason_summary = (
    anomaly.groupby(
        ["source_dataset", "reason_code"],
        dropna=False,
    )
    .agg(
        records=("result_id", "count"),
        money_at_risk=("money_at_risk", "sum"),
    )
    .reset_index()
)

reason_summary["money_at_risk"] = reason_summary["money_at_risk"].fillna(0)

left, right = st.columns(2)

with left:
    st.subheader("Flagged records by anomaly type")

    reason_chart = (
        reason_summary.groupby("reason_code", as_index=False)["records"]
        .sum()
        .sort_values("records", ascending=True)
    )

    fig = go.Figure(
        go.Bar(
            x=reason_chart["records"],
            y=reason_chart["reason_code"],
            orientation="h",
            text=reason_chart["records"],
            textposition="auto",
        )
    )
    fig.update_layout(
        xaxis_title="Number of flagged records",
        yaxis_title="Anomaly type",
        height=480,
        margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Payroll money at risk by anomaly type")

    risk_chart = (
        reason_summary[
            reason_summary["source_dataset"].eq("payroll_monthly_features")
        ]
        .sort_values("money_at_risk", ascending=True)
    )

    fig = go.Figure(
        go.Bar(
            x=risk_chart["money_at_risk"],
            y=risk_chart["reason_code"],
            orientation="h",
            text=risk_chart["money_at_risk"].map(
                lambda value: f"₹{value:,.0f}"
            ),
            textposition="auto",
        )
    )
    fig.update_layout(
        xaxis_title="Money at risk (₹)",
        yaxis_title="Payroll anomaly type",
        height=480,
        margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Anomaly detail")

source_filter = st.selectbox(
    "Select anomaly source",
    ["All sources", "Payroll", "Attendance"],
)

if source_filter == "Payroll":
    detail = payroll_anomalies
elif source_filter == "Attendance":
    detail = attendance_anomalies
else:
    detail = anomaly

st.dataframe(
    detail[
        [
            "source_dataset",
            "period",
            "employee_id",
            "reason_code",
            "reason_text",
            "money_at_risk",
            "model_version",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)


# ---------------------------------------------------------
# FORECAST OVERVIEW
# ---------------------------------------------------------

st.divider()
st.header("2. Forecast vs Actual")

st.info(
    "Forecast values are AI/model outputs, not confirmed results. "
    "The shaded area represents the supplied 80% confidence interval."
)

metric_choice = st.selectbox(
    "Forecast metric",
    ["headcount_end", "attrition_rate_monthly_pct"],
    format_func=lambda value: (
        "Headcount" if value == "headcount_end"
        else "Monthly attrition rate"
    ),
)

metric_forecast = forecast[
    forecast["metric"].eq(metric_choice)
].copy()

if metric_forecast.empty:
    st.warning("No forecast records are available for this metric.")
else:
    departments = sorted(
        metric_forecast["department_id"].dropna().unique().tolist()
    )

    if metric_choice == "headcount_end":
        default_department = "ALL" if "ALL" in departments else departments[0]
        selected_department = st.selectbox(
            "Forecast scope",
            departments,
            index=departments.index(default_department),
            format_func=lambda value: (
                "All departments" if value == "ALL" else value
            ),
        )
    else:
        selected_department = "ALL"
        st.caption("The supplied attrition forecast is company-wide (ALL).")

    selected_forecast = metric_forecast[
        metric_forecast["department_id"].eq(selected_department)
    ].sort_values("forecast_month")

    fig = go.Figure()

    if metric_choice == "headcount_end":
        if selected_department == "ALL":
            actual_series = (
                actual.groupby("month_start_date", as_index=False)
                .agg(actual_value=("headcount_end", "sum"))
            )
        else:
            actual_series = actual[
                actual["department_id"].eq(selected_department)
            ][["month_start_date", "headcount_end"]].rename(
                columns={"headcount_end": "actual_value"}
            )

        actual_series = actual_series.dropna().sort_values("month_start_date")

        fig.add_trace(
            go.Scatter(
                x=actual_series["month_start_date"],
                y=actual_series["actual_value"],
                mode="lines",
                name="Actual headcount",
                line=dict(width=2),
            )
        )

        y_title = "Headcount"

    else:
        actual_series = pd.DataFrame()
        y_title = "Monthly attrition rate (%)"

        st.caption(
            "The supplied forecast is company-wide. "
            "A matching company-wide actual series is not supplied as a separate record, "
            "so this chart shows the forecast and its confidence interval only."
        )

    # Confidence interval: lower bound followed by upper bound.
    fig.add_trace(
        go.Scatter(
            x=selected_forecast["forecast_month"],
            y=selected_forecast["lower_80"],
            mode="lines",
            line=dict(width=0),
            name="80% lower bound",
            showlegend=False,
            hovertemplate="Lower bound: %{y:,.2f}<extra></extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=selected_forecast["forecast_month"],
            y=selected_forecast["upper_80"],
            mode="lines",
            line=dict(width=0),
            fill="tonexty",
            fillcolor="rgba(99, 110, 250, 0.18)",
            name="80% confidence interval",
            hovertemplate="Upper bound: %{y:,.2f}<extra></extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=selected_forecast["forecast_month"],
            y=selected_forecast["forecast_value"],
            mode="lines+markers",
            name="AI forecast",
            line=dict(width=3, dash="dash"),
        )
    )

    fig.update_layout(
        xaxis_title="Month",
        yaxis_title=y_title,
        hovermode="x unified",
        height=500,
        legend=dict(orientation="h", y=1.12),
        margin=dict(l=10, r=10, t=45, b=10),
    )

    st.plotly_chart(fig, use_container_width=True)

    if not selected_forecast.empty:
        first = selected_forecast.iloc[0]
        last = selected_forecast.iloc[-1]

        st.caption(
            f"Forecast method: {last['method']} | "
            f"Model version: {last['model_version']} | "
            f"Trained through: {last['trained_through']} | "
            f"Forecast horizon: {first['forecast_month']:%b %Y} "
            f"to {last['forecast_month']:%b %Y}"
        )

    st.subheader("Forecast records")
    st.dataframe(
        selected_forecast[
            [
                "forecast_month",
                "department_id",
                "forecast_value",
                "lower_80",
                "upper_80",
                "method",
                "trained_through",
                "model_version",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------
# FORECAST ERROR STATUS
# ---------------------------------------------------------

st.divider()
st.header("3. Forecast Error and Measurement Status")

if forecast_error.empty:
    st.warning("No forecast error records are available.")
else:
    statuses = (
        forecast_error["measurement_status"]
        .fillna("UNKNOWN")
        .value_counts()
        .rename_axis("Status")
        .reset_index(name="Records")
    )

    st.dataframe(statuses, use_container_width=True, hide_index=True)

    measurable = forecast_error[
        forecast_error["mape_pct"].notna()
    ]

    if measurable.empty:
        st.info(
            "Forecast accuracy is not yet measurable. "
            "The available forecast horizon begins after the last known actual month. "
            "MAPE is intentionally NULL until matching actual values become available. "
            "No forecast accuracy score has been fabricated."
        )
    else:
        st.metric(
            "Measured forecast records",
            f"{len(measurable):,}",
        )
        st.dataframe(
            measurable,
            use_container_width=True,
            hide_index=True,
        )

st.caption(
    "Interpretation: anomaly flags identify records for review; "
    "they do not independently prove fraud or error. "
    "Forecasts are estimates and must be reviewed against future actual results."
)
