from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION

OUT = Path("outputs/submission")
OUT.mkdir(parents=True, exist_ok=True)
ppt = Presentation()
ppt.slide_width = Inches(13.333)
ppt.slide_height = Inches(7.5)

NAVY = RGBColor(20, 35, 62)
BLUE = RGBColor(48, 105, 180)
TEAL = RGBColor(25, 145, 140)
LIGHT = RGBColor(239, 244, 249)
DARK = RGBColor(38, 48, 60)
GREY = RGBColor(105, 116, 128)
WHITE = RGBColor(255, 255, 255)
ORANGE = RGBColor(222, 142, 45)
RED = RGBColor(185, 65, 65)

def textbox(slide, x, y, w, h, text, size=18, color=DARK, bold=False):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.06)
    tf.margin_right = Inches(0.06)
    tf.margin_top = Inches(0.04)
    p = tf.paragraphs[0]
    p.text = text
    p.font.name = "Aptos"
    p.font.size = Pt(size)
    p.font.bold = bold
    p.font.color.rgb = color
    return box

def base(title, section="PULSEIQ | BOARD REVIEW"):
    slide = ppt.slides.add_slide(ppt.slide_layouts[6])
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = WHITE
    band = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, ppt.slide_width, Inches(0.72))
    band.fill.solid()
    band.fill.fore_color.rgb = NAVY
    band.line.fill.background()
    textbox(slide, 0.48, 0.12, 11.9, 0.42, title, 23, WHITE, True)
    textbox(slide, 0.5, 7.12, 10.5, 0.2, section + "  |  September 2026 source snapshot", 9, GREY)
    return slide

def bullet_block(slide, items, x=0.7, y=1.35, w=11.9, h=4.9, size=20):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.12)
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = item
        p.level = 0
        p.font.name = "Aptos"
        p.font.size = Pt(size)
        p.font.color.rgb = DARK
        p.space_after = Pt(16)
        p.bullet = True
    return box

def kpi(slide, x, y, w, label, value, sub, accent=BLUE):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(1.55))
    shape.fill.solid()
    shape.fill.fore_color.rgb = LIGHT
    shape.line.color.rgb = accent
    textbox(slide, x+0.15, y+0.12, w-0.3, 0.3, label.upper(), 10, GREY, True)
    textbox(slide, x+0.15, y+0.48, w-0.3, 0.52, value, 25, NAVY, True)
    textbox(slide, x+0.15, y+1.08, w-0.3, 0.3, sub, 10, GREY)

def add_chart(slide, categories, values, x, y, w, h, series_name="Value"):
    data = CategoryChartData()
    data.categories = categories
    data.add_series(series_name, values)
    chart = slide.shapes.add_chart(
        XL_CHART_TYPE.BAR_CLUSTERED, Inches(x), Inches(y), Inches(w), Inches(h), data
    ).chart
    chart.has_legend = False
    chart.has_title = False
    chart.value_axis.has_major_gridlines = True
    chart.category_axis.reverse_order = True
    chart.chart_style = 10
    return chart

# 1 — Cover
s = ppt.slides.add_slide(ppt.slide_layouts[6])
s.background.fill.solid()
s.background.fill.fore_color.rgb = NAVY
textbox(s, 0.85, 1.25, 11.5, 0.6, "PULSEIQ", 18, RGBColor(120, 190, 220), True)
textbox(s, 0.85, 2.0, 11.4, 1.4, "People, cost and delivery\nperformance review", 34, WHITE, True)
textbox(s, 0.9, 4.15, 10.5, 0.6, "Board pack | September 2026 data snapshot", 20, WHITE)
textbox(s, 0.9, 6.55, 10.5, 0.3, "Decision focus: improve visibility, validate populations and manage cash conversion", 12, RGBColor(195, 210, 225))

# 2 — Executive overview
s = base("Executive overview")
kpi(s, 0.65, 1.25, 2.85, "Headcount fact", "441", "11 department IDs incl. D00", BLUE)
kpi(s, 3.75, 1.25, 2.85, "Employer cost", "₹5.55 Cr", "September payroll fact", TEAL)
kpi(s, 6.85, 1.25, 2.85, "Attendance", "95.19%", "Weighted attendance ratio", BLUE)
kpi(s, 9.95, 1.25, 2.75, "SP-38 completion", "85.51%", "673 of 787 planned tasks", ORANGE)
bullet_block(s, [
    "Payroll contains 444 distinct employees; headcount fact totals 441. Reconcile before using the two populations interchangeably.",
    "Invoice balance due is ₹14.04 Cr at the source snapshot; most of it is classified as not yet due.",
    "The immediate management opportunity is stronger data reconciliation, receivables visibility and sprint delivery follow-through."
], y=3.25, h=3.3, size=17)

# 3 — People
s = base("People | workforce distribution")
kpi(s, 0.7, 1.15, 3.0, "Headcount fact total", "441", "September 2026", BLUE)
kpi(s, 4.0, 1.15, 3.0, "Department IDs", "11", "Includes D00", TEAL)
dept = ["D01","D02","D03","D04","D05","D06","D07","D08","D09","D10","D00"]
vals = [167,26,52,46,13,59,20,17,29,11,1]
add_chart(s, dept, vals, 0.8, 3.0, 7.0, 3.7, "Headcount")
textbox(s, 8.15, 3.0, 4.3, 2.8,
        "Largest recorded department: D01 (167).\n\nThe fact table includes D00 (1), which should be checked against the department master and reporting rules before board-level segmentation.", 17, DARK)

# 4 — Cost
s = base("Cost | September payroll")
kpi(s, 0.7, 1.25, 3.65, "Gross pay", "₹5.48 Cr", "SUM(gross_pay)", BLUE)
kpi(s, 4.85, 1.25, 3.65, "Employer cost", "₹5.55 Cr", "SUM(employer_cost)", TEAL)
kpi(s, 9.0, 1.25, 3.65, "Net pay", "₹4.81 Cr", "SUM(net_pay)", ORANGE)
bullet_block(s, [
    "Payroll fact contains 7,340 rows across the inspected coverage period; September contains 444 distinct employees.",
    "Employer cost is the broader employer-side cost measure in the metric dictionary.",
    "Recommendation: monitor gross pay and employer cost together, and reconcile payroll headcount with the workforce snapshot."
], y=3.45, h=2.9, size=17)

# 5 — Attendance
s = base("People operations | attendance")
kpi(s, 0.8, 1.35, 3.4, "Attendance ratio", "95.19%", "Dictionary formula; ratio × 100", TEAL)
kpi(s, 4.55, 1.35, 3.4, "Scheduled days", "9,111", "September 2026", BLUE)
kpi(s, 8.3, 1.35, 3.4, "Employees", "444", "Distinct attendance records", ORANGE)
bullet_block(s, [
    "Attendance is calculated as (present days + 0.5 × unpaid half days) divided by scheduled days.",
    "Use the weighted numerator and denominator; do not average department attendance percentages.",
    "Recommendation: review attendance exceptions and trends by department in the governed dashboard, applying minimum-group suppression."
], y=3.55, h=2.7, size=17)

# 6 — Cash / receivables
s = base("Cash | invoice receivables snapshot")
kpi(s, 0.7, 1.15, 3.3, "Balance due", "₹14.04 Cr", "742 invoice records", BLUE)
buckets = ["Not yet due","1–30 days","61–90 days","90+ days","Settled / n.a."]
amounts = [112283412,22133626,1940982,3036258,1028724]
add_chart(s, buckets, [v/10000000 for v in amounts], 0.8, 2.85, 7.0, 3.8, "₹ Crore")
textbox(s, 8.1, 2.9, 4.45, 3.3,
        "₹11.23 Cr is classified as not yet due.\n\n₹2.21 Cr is in the 1–30 day bucket; ₹0.19 Cr in 61–90 days; ₹0.30 Cr in 90+ days.\n\nThis is the invoice source snapshot, not a September-only invoice cohort.", 16, DARK)

# 7 — Team delivery
s = base("Execution | SP-38 team delivery")
kpi(s, 0.7, 1.15, 3.0, "Planned tasks", "787", "Non-cancelled tasks", BLUE)
kpi(s, 4.0, 1.15, 3.0, "Completed", "673", "Status = Done", TEAL)
kpi(s, 7.3, 1.15, 3.0, "Completion", "85.51%", "673 / 787", ORANGE)
kpi(s, 10.6, 1.15, 2.0, "Teams", "16", "Sprint scope", BLUE)
team_names = ["Support Tooling","Sales Enablement","QA Automation","Platform Core","DevOps & Reliability","Payments & Billing","Mobile Apps","ML Services","HR Systems","Internal IT","Finance Automation","Growth Marketing","Data Platform","Product Squad","Analytics & BI","Design Systems"]
team_done = [87,80,59,57,53,41,47,39,36,37,23,26,25,24,21,18]
add_chart(s, team_names, team_done, 0.8, 3.0, 8.0, 3.75, "Done tasks")
textbox(s, 9.0, 3.0, 3.6, 3.3,
        "SP-38 is the selected sprint in the source inspection.\n\nThe largest done-task counts are Support Tooling (87) and Sales Enablement (80). Counts are not completion rates; compare with each team's planned workload before ranking performance.", 15, DARK)

# 8 — Risks / interpretation
s = base("What the numbers do — and do not — say")
bullet_block(s, [
    "Population reconciliation: September headcount fact = 441; payroll and attendance facts each contain 444 distinct employees.",
    "Department master: D00 appears in the headcount fact output; validate whether it is a valid reporting bucket.",
    "Receivables: ₹14.04 Cr is a snapshot across 742 invoice records; it is not a September-only balance movement.",
    "Team delivery: SP-38 completion is a sprint-level measure. Do not convert it into a monthly KPI.",
    "Data freshness: source files extend through September 2026 for payroll, attendance and tasks; no automated refresh success is claimed."
], y=1.45, h=5.2, size=18)

# 9 — Decisions / actions
s = base("Board decisions | recommended next actions")
bullet_block(s, [
    "Approve a workforce-to-payroll reconciliation: resolve the 441 vs 444 population difference and D00 classification.",
    "Assign a receivables owner to review overdue buckets, beginning with the 1–30 day and 90+ day balances.",
    "Use attendance as a weighted operational KPI; investigate exceptions through privacy-safe department views.",
    "Ask delivery leads to pair completed-task counts with planned workload and sprint-level completion rates.",
    "Require metric ownership, formula lineage, source freshness and minimum-group suppression before wider dashboard access."
], y=1.5, h=4.9, size=19)
textbox(s, 0.8, 6.45, 11.7, 0.35, "Decision requested: endorse the reconciliation and operating-review actions above.", 15, BLUE, True)

ppt_path = OUT / "PulseIQ_Board_Pack_September_2026.pptx"
ppt.save(ppt_path)

demo = """PULSEIQ — FIVE-MINUTE DEMO SCRIPT

0:00–0:30 | Opening
Introduce PulseIQ as a governed people, cost and delivery analytics solution. State that the displayed operational snapshot is September 2026 and that the invoice balance is a source snapshot.

0:30–1:20 | Workforce and KPI Builder
Open the dashboard and the Custom KPI Builder. Select a governed KPI and reporting month. Show the metric definition, formula, source, grain, owner and minimum group size. Explain that demo roles simulate access views and are not production authentication.

1:20–2:10 | Cost and attendance
Show gross pay, employer cost and attendance. Explain that attendance is calculated from summed present days, half-day adjustment and scheduled days. Do not average department percentages.

2:10–3:00 | Cash and receivables
Show the invoice ageing view. Point out that the ₹14.04 Cr balance due is a snapshot across 742 invoice records, with ₹11.23 Cr classified as not yet due. Avoid describing it as September-only movement.

3:00–3:50 | Team delivery
Open the sprint/team view and select SP-38. Show 673 completed out of 787 planned tasks (85.51%). Explain that the metric is sprint-level, not monthly.

3:50–4:35 | API and lineage
Show the API documentation at /docs, the metric catalog at /metrics, and one metric endpoint. Open docs/data_lineage.md to show source, formula, owner, grain and freshness.

4:35–5:00 | Close
Summarize the next actions: reconcile workforce populations, review receivables, investigate attendance exceptions and pair team output counts with planned workload.

DEMO SAFETY NOTES
- Start the API locally with: .\\.venv\\Scripts\\python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8000
- Start the Streamlit dashboard using the project's established app command.
- Do not claim the API or dashboard is publicly hosted.
- Do not present the demo role selector as real authentication.
- Do not reveal individual salary details during a public demo.
"""
demo_path = OUT / "PulseIQ_Five_Minute_Demo_Script.txt"
demo_path.write_text(demo, encoding="utf-8")

print(f"CREATED: {ppt_path}")
print(f"CREATED: {demo_path}")
print(f"SLIDES: {len(ppt.slides)}")
