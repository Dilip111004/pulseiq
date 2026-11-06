from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
OUTPUTS = ROOT / "outputs"

st.set_page_config(page_title="PQ-14 | AI Signals", page_icon="ðŸ¤–", layout="wide")
st.title("PQ-14 | AI Signals Dashboard")
st.caption("Anomaly monitoring, attrition-risk signals and workforce forecasts.")

def crore(value):
    value = 0 if pd.isna(value) else float(value)
    return f"\u20B9{value / 10_000_000:,.2f} Cr"

def ai_label():
    pass

@st.cache_data
def load_data():
    anomaly = pd.read_csv(CLEAN / "fact_anomaly.csv")
    forecast = pd.read_csv(CLEAN / "fact_forecast.csv")
    actual = pd.read_csv(CLEAN / "fact_headcount_monthly.csv")
    error = pd.read_csv(OUTPUTS / "m28_forecast_error_mape.csv")
    risk_file = CLEAN / "fact_attrition_risk.csv"
    risk = pd.read_csv(risk_file) if risk_file.exists() else pd.DataFrame()

    anomaly["money_at_risk"] = pd.to_numeric(anomaly["money_at_risk"], errors="coerce")
    anomaly["flagged_bool"] = anomaly["flagged"].astype(str).str.strip().str.upper().eq("Y")

    forecast["forecast_month"] = pd.to_datetime(forecast["forecast_month"], errors="coerce")
    for c in ["forecast_value", "lower_80", "upper_80"]:
        forecast[c] = pd.to_numeric(forecast[c], errors="coerce")

    actual["month_start_date"] = pd.to_datetime(actual["month_start_date"], errors="coerce")
    for c in ["headcount_start", "headcount_end", "exits", "attrition_rate_monthly_pct"]:
        if c in actual:
            actual[c] = pd.to_numeric(actual[c], errors="coerce")

    if not error.empty:
        error["month_start_date"] = pd.to_datetime(error["month_start_date"], errors="coerce")
        for c in ["forecast_value", "actual_value", "mape_pct"]:
            if c in error:
                error[c] = pd.to_numeric(error[c], errors="coerce")
    return anomaly, forecast, actual, error, risk

try:
    anomaly, forecast, actual, forecast_error, attrition_risk = load_data()
except Exception as exc:
    st.error(f"Unable to load AI Signals data: {exc}")
    st.stop()

# 1. Anomaly detection
st.header("1. Anomaly Detection")
payroll = anomaly[anomaly["source_dataset"].eq("payroll_monthly_features")].copy()
attendance = anomaly[anomaly["source_dataset"].eq("attendance_monthly_features")].copy()
flags = int(anomaly["flagged_bool"].sum())
money_risk = payroll["money_at_risk"].sum(min_count=1)
money_risk = 0.0 if pd.isna(money_risk) else float(money_risk)
money_rows = int((payroll["money_at_risk"].fillna(0) > 0).sum())
no_money_rows = int((anomaly["money_at_risk"].isna() | anomaly["money_at_risk"].eq(0)).sum())

a, b, c, d = st.columns(4)
a.metric("Anomaly records", f"{len(anomaly):,}")
b.metric("Flagged records", f"{flags:,}")
c.metric("Payroll money at risk", crore(money_risk))
d.metric("Records with positive money at risk", f"{money_rows:,}")
st.caption(f"Money at risk totals {crore(money_risk)} across {money_rows:,} payroll records. {no_money_rows:,} records have no positive money-at-risk value. These are review amounts, not confirmed losses.")

summary = anomaly.groupby(["source_dataset", "reason_code"], dropna=False).agg(
    records=("result_id", "count"), money_at_risk=("money_at_risk", "sum")
).reset_index().fillna({"money_at_risk": 0})

left, right = st.columns(2)
with left:
    st.subheader("Flagged records by anomaly type")
    counts = summary.groupby("reason_code", as_index=False)["records"].sum().sort_values("records", ascending=False)
    fig = go.Figure(go.Bar(x=counts["records"], y=counts["reason_code"], orientation="h",
                           text=counts["records"], textposition="auto"))
    fig.update_layout(xaxis_title="Flagged records", yaxis_title="Anomaly type",
                      yaxis=dict(autorange="reversed"), height=470,
                      margin=dict(l=10, r=10, t=20, b=10))
    st.plotly_chart(fig, use_container_width=True)
    ai_label()
    st.info("Statistical outliers are the largest group by count. A flag identifies an unusual pattern; it does not establish an error or fraud.")

with right:
    st.subheader("Payroll money at risk by anomaly type")
    risk_chart = summary[summary["source_dataset"].eq("payroll_monthly_features")]
    risk_chart = risk_chart[risk_chart["money_at_risk"] > 0].sort_values("money_at_risk", ascending=False)
    fig = go.Figure(go.Bar(x=risk_chart["money_at_risk"], y=risk_chart["reason_code"],
                           orientation="h", text=risk_chart["money_at_risk"].map(crore),
                           textposition="auto", hovertemplate="%{y}<br>\u20B9%{x:,.2f}<extra></extra>"))
    fig.update_layout(xaxis_title="Money at risk (\u20B9)", yaxis_title="Payroll anomaly type",
                      yaxis=dict(autorange="reversed"), height=470,
                      margin=dict(l=10, r=10, t=20, b=10))
    st.plotly_chart(fig, use_container_width=True)
    ai_label()
    st.info("Statistical outliers and gross-above-norm records contribute the largest amounts. Review source payroll records before taking action.")

st.subheader("Anomaly detail")
source_filter = st.selectbox("Select anomaly source", ["All sources", "Payroll", "Attendance"])
detail = payroll if source_filter == "Payroll" else attendance if source_filter == "Attendance" else anomaly
st.dataframe(detail[["source_dataset", "period", "employee_id", "reason_code", "reason_text", "money_at_risk", "model_version"]],
             use_container_width=True, hide_index=True)

# 2. Attrition risk
st.divider()
st.header("2. Attrition-Risk Signals")
if attrition_risk.empty:
    st.warning("fact_attrition_risk.csv is unavailable or empty; no attrition-risk chart can be displayed.")
elif "risk_band" in attrition_risk.columns:
    bands = attrition_risk["risk_band"].fillna("Unclassified").value_counts().rename_axis("Risk band").reset_index(name="Employees")
    order = {"High": 0, "Medium": 1, "Low": 2}
    bands["_order"] = bands["Risk band"].map(order).fillna(3)
    bands = bands.sort_values("_order")
    x, y = st.columns([1, 2])
    x.metric("Risk records", f"{len(attrition_risk):,}")
    x.caption("Source model note: baseline demo model. High = top 10%; Medium = next 20%.")
    with y:
        fig = go.Figure(go.Bar(x=bands["Risk band"], y=bands["Employees"], text=bands["Employees"], textposition="auto"))
        fig.update_layout(xaxis_title="Model risk band", yaxis_title="Employees", height=350,
                          margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)
        ai_label()
        st.info("Risk bands are model-generated support signals, not predictions that an employee will leave. Never use them alone for employment decisions.")
    cols = [c for c in ["department_id", "risk_band", "risk_score_12m", "top_reason_1", "top_reason_2", "top_reason_3", "model_note"] if c in attrition_risk.columns]
    st.dataframe(attrition_risk[cols], use_container_width=True, hide_index=True)
else:
    st.warning("fact_attrition_risk.csv does not contain risk_band.")

# 3. Forecast versus actual
st.divider()
st.header("3. Forecast vs Actual")
st.info("The shaded region is the supplied 80% forecast interval. It is an estimated range, not a guarantee.")
metric = st.selectbox("Forecast metric", ["headcount_end", "attrition_rate_monthly_pct"],
                      format_func=lambda v: "Headcount" if v == "headcount_end" else "Monthly attrition rate")
mf = forecast[forecast["metric"].eq(metric)].copy()

if mf.empty:
    st.warning("No forecast records are available for this metric.")
else:
    departments = sorted(mf["department_id"].dropna().unique().tolist())
    if metric == "headcount_end":
        default = "ALL" if "ALL" in departments else departments[0]
        dept = st.selectbox("Forecast scope", departments, index=departments.index(default),
                            format_func=lambda v: "All departments" if v == "ALL" else v)
    else:
        dept = "ALL"
        st.caption("The supplied attrition forecast is company-wide (ALL).")

    selected = mf[mf["department_id"].eq(dept)].sort_values("forecast_month")
    fig = go.Figure()
    actual_scope = actual[actual["department_id"].ne("D00")].copy()

    if metric == "headcount_end":
        if dept == "ALL":
            actual_series = actual_scope.groupby("month_start_date", as_index=False).agg(
                actual_value=("headcount_end", "sum"))
        else:
            actual_series = actual[actual["department_id"].eq(dept)][
                ["month_start_date", "headcount_end"]].rename(columns={"headcount_end": "actual_value"})
        actual_note = "Actual headcount is available through September 2026. ALL scope sums departments and excludes D00."
        y_title = "Headcount"
        actual_name = "Actual headcount"
    else:
        actual_series = actual_scope.groupby("month_start_date", as_index=False).agg(
            total_exits=("exits", "sum"), total_start=("headcount_start", "sum"))
        actual_series["actual_value"] = actual_series["total_exits"] / actual_series["total_start"].replace(0, pd.NA) * 100
        actual_note = "Company-wide actual attrition = total monthly exits Ã· total starting headcount Ã— 100, excluding D00. Department percentages are not added together."
        y_title = "Monthly attrition rate (%)"
        actual_name = "Actual attrition rate"

    actual_series = actual_series.dropna(subset=["month_start_date", "actual_value"]).sort_values("month_start_date")
    fig.add_trace(go.Scatter(x=actual_series["month_start_date"], y=actual_series["actual_value"],
                             mode="lines", name=actual_name, line=dict(width=2)))
    fig.add_trace(go.Scatter(x=selected["forecast_month"], y=selected["lower_80"], mode="lines",
                             line=dict(width=0), name="80% lower bound", showlegend=False))
    fig.add_trace(go.Scatter(x=selected["forecast_month"], y=selected["upper_80"], mode="lines",
                             line=dict(width=0), fill="tonexty", fillcolor="rgba(99,110,250,0.18)",
                             name="Supplied 80% interval"))
    fig.add_trace(go.Scatter(x=selected["forecast_month"], y=selected["forecast_value"],
                             mode="lines+markers", name="AI forecast", line=dict(width=3, dash="dash")))
    fig.update_layout(xaxis_title="Month", yaxis_title=y_title, hovermode="x unified",
                      height=500, legend=dict(orientation="h", y=1.12),
                      margin=dict(l=10, r=10, t=45, b=10))
    st.plotly_chart(fig, use_container_width=True)
    ai_label()
    st.info(actual_note)

    if not selected.empty:
        first, last = selected.iloc[0], selected.iloc[-1]
        st.caption(f"Method: {last['method']} | Model: {last['model_version']} | Trained through: {last['trained_through']} | Horizon: {first['forecast_month']:%b %Y} to {last['forecast_month']:%b %Y}")
    st.subheader("Forecast records")
    st.dataframe(selected[["forecast_month", "department_id", "forecast_value", "lower_80", "upper_80", "method", "trained_through", "model_version"]],
                 use_container_width=True, hide_index=True)

# 4. Forecast error
st.divider()
st.header("4. Forecast Error and Measurement Status")
if forecast_error.empty:
    st.warning("No forecast error records are available.")
else:
    statuses = forecast_error["measurement_status"].fillna("UNKNOWN").value_counts().rename_axis("Status").reset_index(name="Records")
    st.dataframe(statuses, use_container_width=True, hide_index=True)
    measurable = forecast_error[forecast_error["mape_pct"].notna()]
    c1, c2, c3 = st.columns(3)
    c1.metric("Error records", f"{len(forecast_error):,}")
    c2.metric("Measurable MAPE", f"{len(measurable):,}")
    c3.metric("Not yet measurable", f"{forecast_error['mape_pct'].isna().sum():,}")
    if measurable.empty:
        st.info("Forecast accuracy is not yet measurable. Actual data ends in September 2026, while the forecast horizon begins in October 2026. All 66 MAPE rows have NULL actual values and NULL MAPE. A 12% forecast error cannot be validated from these records.")
    else:
        st.dataframe(measurable, use_container_width=True, hide_index=True)
    st.caption("The MAPE output contains 66 headcount forecast-error rows. The six company-wide attrition forecasts are not included in that output, so their forecast errors are not measured here.")
    st.subheader("Forecast error evidence")
    cols = [c for c in ["month_start_date", "department_id", "forecast_value", "actual_value", "mape_pct", "measurement_status"] if c in forecast_error.columns]
    st.dataframe(forecast_error[cols], use_container_width=True, hide_index=True)

# 5. Governance notes
st.divider()
st.header("5. Interpretation and Human Review")
st.markdown("""
- **Anomaly detection:** flags identify unusual patterns; they do not prove fraud, misconduct or incorrect payments.
- **Money at risk:** amounts associated with flagged payroll records, not confirmed financial losses.
- **Attrition risk:** the source describes a baseline demo model. Risk bands are support signals, never decisions about employees.
- **Forecasts:** estimates based on the stated method and training cutoff. The supplied 80% interval is not a guarantee.
- **Forecast accuracy:** assess only after matching actual results become available for forecast months.
""")
