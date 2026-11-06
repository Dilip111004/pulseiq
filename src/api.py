from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"

METRICS = {
    "M01": ("fact_headcount_monthly.csv", "month_start_date"),
    "M07": ("fact_payroll.csv", "period_end_date"),
    "M09": ("fact_payroll.csv", "period_end_date"),
    "M13": ("fact_attendance_monthly.csv", "period_end_date"),
    "M22": ("fact_task.csv", "completed_date"),
}

app = FastAPI(
    title="PulseIQ Analytics API",
    version="1.0.0",
    description="Governed KPI endpoints backed by PulseIQ clean warehouse tables.",
)


def read_csv(filename: str) -> pd.DataFrame:
    path = CLEAN / filename
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"Source file unavailable: {filename}")
    return pd.read_csv(path)


def dictionary_row(metric_id: str) -> dict:
    dictionary = read_csv("metric_dictionary.csv")
    matches = dictionary.loc[dictionary["metric_id"] == metric_id]
    if matches.empty:
        raise HTTPException(status_code=404, detail="Metric definition not found.")
    row = matches.iloc[0].where(pd.notna(matches.iloc[0]), None).to_dict()
    return row


def latest_source_date(filename: str, date_column: str) -> Optional[str]:
    df = read_csv(filename)
    if date_column not in df.columns:
        return None
    dates = pd.to_datetime(df[date_column], errors="coerce").dropna()
    return dates.max().date().isoformat() if not dates.empty else None


def calculate_metric(metric_id: str, month: Optional[str], sprint_id: Optional[str]):
    filename, date_column = METRICS[metric_id]
    df = read_csv(filename)

    if metric_id == "M22":
        if not sprint_id:
            raise HTTPException(status_code=422, detail="sprint_id is required for M22.")
        if "sprint_id" not in df.columns:
            raise HTTPException(status_code=503, detail="sprint_id column is unavailable.")
        part = df.loc[df["sprint_id"].astype(str) == str(sprint_id)].copy()
        if part.empty:
            raise HTTPException(status_code=404, detail="No task records found for this sprint.")
        planned = part.loc[part["status"].astype(str).str.lower() != "cancelled"]
        done = planned.loc[planned["status"].astype(str).str.lower() == "done"]
        value = (len(done) / len(planned) * 100) if len(planned) else None
        return value, len(planned), latest_source_date(filename, "completed_date"), str(sprint_id)

    if not month:
        raise HTTPException(status_code=422, detail="month is required (YYYY-MM).")
    try:
        selected = pd.Period(month, freq="M")
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid month. Use YYYY-MM.")

    if date_column not in df.columns:
        raise HTTPException(status_code=503, detail=f"Date column unavailable: {date_column}")

    dates = pd.to_datetime(df[date_column], errors="coerce")
    part = df.loc[dates.dt.to_period("M") == selected].copy()
    if part.empty:
        raise HTTPException(status_code=404, detail=f"No source records for {month}.")

    if metric_id == "M01":
        value = float(part["headcount_end"].sum())
        population = int(value)
    elif metric_id == "M07":
        value = float(part["gross_pay"].sum())
        population = int(part["employee_id"].nunique())
    elif metric_id == "M09":
        value = float(part["employer_cost"].sum())
        population = int(part["employee_id"].nunique())
    elif metric_id == "M13":
        scheduled = float(part["scheduled_days"].sum())
        numerator = float(part["present_days"].sum()) + 0.5 * float(part["half_days_unpaid"].sum())
        value = numerator / scheduled if scheduled else None
        population = int(part["employee_id"].nunique())
    else:
        raise HTTPException(status_code=400, detail="Metric calculation is not configured.")

    return value, population, latest_source_date(filename, date_column), month


@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "service": "PulseIQ Analytics API", "version": "1.0.0"}


@app.get("/metrics", tags=["Metrics"])
def list_metrics():
    definitions = read_csv("metric_dictionary.csv")
    selected = definitions.loc[definitions["metric_id"].isin(METRICS)].copy()
    return {
        "count": len(selected),
        "metrics": selected.where(pd.notna(selected), None).to_dict(orient="records"),
    }


@app.get("/metrics/{metric_id}", tags=["Metrics"])
def get_metric(
    metric_id: str,
    month: Optional[str] = Query(default=None, description="Reporting month YYYY-MM; required except for M22."),
    sprint_id: Optional[str] = Query(default=None, description="Required for M22 task completion."),
):
    metric_id = metric_id.upper()
    if metric_id not in METRICS:
        raise HTTPException(status_code=404, detail="Unsupported metric. Use M01, M07, M09, M13 or M22.")

    definition = dictionary_row(metric_id)
    value, population, freshness, period = calculate_metric(metric_id, month, sprint_id)

    if population is not None and definition.get("minimum_group_size") is not None:
        try:
            threshold = int(float(definition["minimum_group_size"]))
        except (TypeError, ValueError):
            threshold = 0
        if threshold > 0 and population < threshold:
            raise HTTPException(status_code=403, detail="Result suppressed by the metric minimum-group-size rule.")

    return {
        "metric_id": metric_id,
        "metric_name": definition.get("metric_name"),
        "value": value,
        "unit": definition.get("unit"),
        "period": period,
        "grain": definition.get("grain"),
        "formula": definition.get("formula"),
        "business_definition": definition.get("business_definition"),
        "source_table": definition.get("source_table"),
        "owner_team": definition.get("owner_team"),
        "minimum_group_size": definition.get("minimum_group_size"),
        "population_count": population,
        "data_freshness": {
            "latest_source_date": freshness,
            "source_file": METRICS[metric_id][0],
        },
        "caveat": definition.get("caveat"),
    }
