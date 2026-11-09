from pathlib import Path
import argparse
import sys
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.chart import BarChart, Reference
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
CLEAN = ROOT / "data" / "clean"
REPORTS = OUT / "monthly_reports"

FILES = {
    "headcount": ("m01_headcount.csv", "month_start_date"),
    "hires": ("m02_hires.csv", "month_start_date"),
    "exits": ("m03_exits.csv", "month_start_date"),
    "attrition": ("m04_attrition_rate_monthly.csv", "month_start_date"),
    "rolling": ("m05_attrition_rate_rolling_12m.csv", "month_start_date"),
    "voluntary": ("m06_voluntary_attrition_rate.csv", "month_start_date"),
    "gross": ("m07_gross_pay.csv", "month_end_date"),
    "net": ("m08_net_pay.csv", "month_end_date"),
    "employer": ("m09_employer_cost.csv", "month_end_date"),
    "cost_head": ("m10_cost_per_head.csv", "month_end_date"),
    "overtime": ("m11_overtime_share.csv", "month_end_date"),
    "variable": ("m12_variable_pay_share.csv", "month_end_date"),
    "attendance": ("m13_attendance_rate.csv", "month_end_date"),
    "late": ("m14_late_arrival_rate.csv", "month_end_date"),
    "leave": ("m15_leave_without_pay_days.csv", "month_end_date"),
    "revenue": ("m16_revenue.csv", "month_start_date"),
    "profit": ("m17_net_profit.csv", "month_start_date"),
    "margin": ("m18_operating_margin.csv", "month_start_date"),
    "payroll_pct": ("m19_payroll_as_pct_revenue.csv", "month_start_date"),
    "dso": ("m20_days_sales_outstanding.csv", "month_end_date"),
}

def load_data():
    result = {}
    missing = []
    for key, (filename, date_col) in FILES.items():
        path = OUT / filename
        if not path.exists():
            missing.append(str(path.relative_to(ROOT)))
            continue
        df = pd.read_csv(path)
        if date_col not in df.columns:
            raise ValueError(f"{filename}: missing date column {date_col}")
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        result[key] = df
    if missing:
        raise FileNotFoundError("Missing metric files:\n" + "\n".join(missing))
    return result

def rows_for(data, key, month):
    date_col = FILES[key][1]
    return data[key][data[key][date_col].dt.to_period("M") == month].copy()

def metric_map(data, key, value_col, month):
    df = rows_for(data, key, month)
    if df.empty or value_col not in df.columns:
        return {}
    return df.drop_duplicates("department_id").set_index("department_id")[value_col].to_dict()

def style(ws, title):
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A4"
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=6)
    c = ws.cell(1, 1, title)
    c.font = Font(name="Aptos Display", size=16, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor="17365D")
    ws.row_dimensions[1].height = 30
    for cell in ws[3]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="4472C4")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[3].height = 32

def finish(ws):
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        width = 12
        for cell in col:
            if cell.value is not None:
                width = max(width, min(len(str(cell.value)) + 2, 38))
        ws.column_dimensions[letter].width = width
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_setup.orientation = "landscape"

def add_chart(ws, title, value_col, anchor, x_title):
    if ws.max_row < 4:
        return
    chart = BarChart()
    chart.type = "bar"
    chart.style = 10
    chart.title = title
    chart.y_axis.title = "Department"
    chart.x_axis.title = x_title
    chart.add_data(
        Reference(ws, min_col=value_col, min_row=3, max_row=ws.max_row),
        titles_from_data=True
    )
    chart.set_categories(
        Reference(ws, min_col=2, min_row=4, max_row=ws.max_row)
    )
    chart.height = 7
    chart.width = 13
    ws.add_chart(chart, anchor)

def build(month_text):
    month = pd.Period(month_text, freq="M")
    if month < pd.Period("2025-04", freq="M"):
        raise ValueError("Full monthly report coverage starts in April 2025.")

    data = load_data()
    required = ["gross", "attendance", "revenue", "profit", "margin", "payroll_pct"]
    unavailable = [k for k in required if rows_for(data, k, month).empty]
    if unavailable:
        raise ValueError(
            f"Cannot create a complete pack for {month}; missing month data: "
            + ", ".join(unavailable)
        )

    departments = pd.read_csv(CLEAN / "dim_department.csv")
    targets = pd.read_csv(CLEAN / "kpi_targets.csv")
    targets["month"] = pd.to_datetime(targets["month"], errors="coerce")
    target_month = targets[targets["month"].dt.to_period("M") == month]

    names = departments.set_index("department_id")["department_name"].to_dict()
    dept_ids = sorted(d for d in names if d != "D00")
    headcount = metric_map(data, "headcount", "headcount", month)

    wb = Workbook()
    ws = wb.active
    ws.title = "Executive Finance"
    ws.append(["PulseIQ Monthly Management Pack"])
    start = month.to_timestamp()
    end = month.to_timestamp(how="end").normalize()
    ws.append([f"Reporting period: {start:%d %b %Y} to {end:%d %b %Y}"])
    ws.append(["Metric", "Value", "Unit / note"])

    rev = rows_for(data, "revenue", month)
    rev = rev[rev["department_id"].astype(str).str.upper() == "ALL"]
    revenue = pd.to_numeric(rev["revenue"], errors="coerce").sum(min_count=1)

    def company_value(key, col):
        df = rows_for(data, key, month)
        if "department_id" in df.columns:
            df = df[df["department_id"].astype(str).str.upper() == "ALL"]
        if col not in df.columns:
            raise ValueError(f"Expected column {col} not found in {key}")
        vals = pd.to_numeric(df[col], errors="coerce").dropna()
        return vals.iloc[0] if len(vals) else None

    finance = [
        ("Revenue", revenue, "Currency; sum of company ALL account-code rows"),
        ("Net profit", company_value("profit", "net_profit"), "Currency; company-level"),
        ("Operating margin", company_value("margin", "operating_margin_pct"), "Percent; source units"),
        ("Payroll / revenue", company_value("payroll_pct", "payroll_pct_revenue"), "Percent; source units"),
        ("Days sales outstanding", company_value("dso", "dso_days"), "Days; company-level"),
    ]
    for row in finance:
        ws.append(list(row))
    ws.append([])
    ws.append(["Data cut-off", end.to_pydatetime(), "Requested reporting month; source month availability validated"])
    ws.append(["Full-pack coverage", "April 2025 onward", "Requires payroll, attendance and finance sources"])
    style(ws, f"PulseIQ | Executive Finance | {month}")

    # Workforce movement
    w = wb.create_sheet("Workforce Movement")
    w.append(["Workforce Movement"])
    w.append([f"Reporting month: {month}"])
    w.append(["Department ID", "Department", "Headcount", "Hires", "Exits",
              "Monthly attrition %", "Rolling 12M attrition %", "Voluntary attrition %"])
    maps = {
        "hires": metric_map(data, "hires", "hires", month),
        "exits": metric_map(data, "exits", "exits", month),
        "attr": metric_map(data, "attrition", "attrition_rate_monthly_pct", month),
        "rolling": metric_map(data, "rolling", "attrition_rate_rolling_12m_pct", month),
        "voluntary": metric_map(data, "voluntary", "voluntary_attrition_rate_pct", month),
    }
    for d in dept_ids:
        w.append([d, names[d], headcount.get(d), maps["hires"].get(d),
                  maps["exits"].get(d), maps["attr"].get(d),
                  maps["rolling"].get(d), maps["voluntary"].get(d)])
    style(w, f"PulseIQ | Workforce Movement | {month}")
    add_chart(w, "Headcount by Department", 3, "J3", "Employees")

    # Payroll and employer cost
    p = wb.create_sheet("Payroll & Employer Cost")
    p.append(["Payroll & Employer Cost"])
    p.append([f"Reporting month: {month}"])
    p.append(["Department ID", "Department", "Gross pay", "Net pay", "Employer cost",
              "Cost per head", "Overtime share %", "Variable pay share %"])
    payroll = {
        "gross": metric_map(data, "gross", "gross_pay", month),
        "net": metric_map(data, "net", "net_pay", month),
        "employer": metric_map(data, "employer", "employer_cost", month),
        "cost_head": metric_map(data, "cost_head", "cost_per_head", month),
        "overtime": metric_map(data, "overtime", "overtime_share_pct", month),
        "variable": metric_map(data, "variable", "variable_pay_share_pct", month),
    }
    for d in dept_ids:
        p.append([d, names[d], payroll["gross"].get(d), payroll["net"].get(d),
                  payroll["employer"].get(d), payroll["cost_head"].get(d),
                  payroll["overtime"].get(d), payroll["variable"].get(d)])
    style(p, f"PulseIQ | Payroll & Employer Cost | {month}")
    add_chart(p, "Gross Pay by Department", 3, "J3", "Currency")
    add_chart(p, "Overtime Share by Department", 7, "J18", "Percent")

    # Attendance and leave
    a = wb.create_sheet("Attendance & Leave")
    a.append(["Attendance & Leave"])
    a.append([f"Reporting month: {month}"])
    a.append(["Department ID", "Department", "Attendance rate",
              "Late arrivals / present day", "Leave without pay days"])
    attendance = metric_map(data, "attendance", "attendance_rate", month)
    late = metric_map(data, "late", "late_arrivals_per_present_day", month)
    leave = metric_map(data, "leave", "leave_without_pay_days", month)
    for d in dept_ids:
        a.append([d, names[d], attendance.get(d), late.get(d), leave.get(d)])
    style(a, f"PulseIQ | Attendance & Leave | {month}")
    add_chart(a, "Attendance Rate by Department", 3, "G3", "Rate")
    add_chart(a, "Leave Without Pay by Department", 5, "G18", "Days")

    # Department scorecard; missing targets remain blank and are labelled.
    s = wb.create_sheet("Department Scorecard")
    s.append(["Department Scorecard"])
    s.append([f"Reporting month: {month}"])
    s.append(["Department ID", "Department", "Headcount", "Attendance actual",
              "Attendance target", "Overtime actual %", "Overtime target %",
              "Monthly attrition actual %", "Attrition target %",
              "Task completion target %", "Target status notes"])

    target_map = target_month.set_index("department_id").to_dict("index")
    for d in dept_ids:
        t = target_map.get(d, {})
        notes = []
        if not t:
            notes.append("No target row")
        if pd.isna(t.get("task_completion_target_pct", float("nan"))):
            notes.append("Task completion target unavailable")
        s.append([
            d, names[d], headcount.get(d), attendance.get(d),
            t.get("attendance_rate_target"), payroll["overtime"].get(d),
            t.get("overtime_share_target_pct"), maps["attr"].get(d),
            t.get("attrition_monthly_target_pct"),
            t.get("task_completion_target_pct"),
            "; ".join(notes) if notes else "Targets available as supplied"
        ])
    style(s, f"PulseIQ | Department Scorecard | {month}")

    # Format percentage fields without changing source values.
    for r in range(4, s.max_row + 1):
        for c in (4, 5):
            s.cell(r, c).number_format = "0.00%"
        for c in (6, 7, 8, 9, 10):
            s.cell(r, c).number_format = '0.00'

    for r in range(4, 9):
        if r in (4, 5):
            ws.cell(r, 2).number_format = '₹#,##0.00'
        elif r in (6, 7):
            ws.cell(r, 2).number_format = '0.00"%"'
        else:
            ws.cell(r, 2).number_format = "0.00"

    for sheet in wb.worksheets:
        finish(sheet)

    REPORTS.mkdir(parents=True, exist_ok=True)
    output = REPORTS / f"PulseIQ_Monthly_Report_{month}.xlsx"
    wb.save(output)
    print(f"PASS: Report created: {output}")
    print(f"Reporting period: {start:%Y-%m-%d} to {end:%Y-%m-%d}")
    print(f"Data cut-off: {end:%Y-%m-%d}")
    print("Sheets: " + ", ".join(wb.sheetnames))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True, help="YYYY-MM")
    args = parser.parse_args()
    try:
        build(args.month)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

if __name__ == "__main__":
    main()
