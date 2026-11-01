from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# --------------------------------------------------
# PulseIQ | Phase 2 | PQ-11 P&L and Expense Analytics
# --------------------------------------------------

st.set_page_config(
    page_title="PulseIQ | P&L and Expense Analytics",
    page_icon="📈",
    layout="wide",
)

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "outputs"


@st.cache_data
def load_csv(filename):
    path = OUTPUTS / filename
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


pl = load_csv("pq11_monthly_pl.csv")
categories = load_csv("pq11_expense_by_category.csv")
vendors = load_csv("pq11_top_vendors.csv")
reconciliation = load_csv("pq11_expense_ledger_reconciliation.csv")

st.title("PulseIQ")
st.subheader("Profit & Loss and Expense Analytics")
st.caption(
    "Phase 2 | PQ-11 | Monthly financial performance, "
    "expense categories, vendor spend and ledger reconciliation."
)

required_pl = {
    "month", "operating_revenue", "other_income", "total_income",
    "expenses", "net_profit", "m17_net_profit", "m17_difference",
}
if pl.empty or not required_pl.issubset(pl.columns):
    st.error("Monthly P&L data is missing or has invalid columns.")
    st.stop()

pl["month"] = pd.to_datetime(pl["month"], errors="coerce")
numeric_columns = [
    "operating_revenue", "other_income", "total_income",
    "expenses", "net_profit", "m17_net_profit", "m17_difference",
]
for column in numeric_columns:
    pl[column] = pd.to_numeric(pl[column], errors="coerce")

pl = pl.dropna(subset=["month"]).sort_values("month")

# --------------------------------------------------
# Filters
# --------------------------------------------------

st.sidebar.header("Dashboard Filters")

min_month = pl["month"].min().date()
max_month = pl["month"].max().date()

date_range = st.sidebar.date_input(
    "Month range",
    value=(min_month, max_month),
    min_value=min_month,
    max_value=max_month,
)

if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_month, max_month

filtered = pl[
    pl["month"].dt.date.between(start_date, end_date)
].copy()

if filtered.empty:
    st.warning("No P&L records match the selected month range.")
    st.stop()

# --------------------------------------------------
# KPI cards
# --------------------------------------------------

total_revenue = filtered["operating_revenue"].sum()
total_other_income = filtered["other_income"].sum()
total_income = filtered["total_income"].sum()
total_expenses = filtered["expenses"].sum()
net_profit = filtered["net_profit"].sum()
profit_margin = (
    net_profit / total_income * 100 if total_income else 0
)

c1, c2, c3 = st.columns(3)
c1.metric("Operating revenue", f"INR {total_revenue / 10000000:.2f} Cr")
c2.metric("Other income", f"INR {total_other_income / 100000:.2f} L")
c3.metric("Total expenses", f"INR {total_expenses / 10000000:.2f} Cr")

c4, c5 = st.columns(2)
c4.metric("Net profit", f"INR {net_profit / 100000:.2f} L")
c5.metric("Net profit margin", f"{profit_margin:.2f}%")

st.caption(
    f"Showing {len(filtered)} months from "
    f"{start_date.strftime('%Y-%m')} to {end_date.strftime('%Y-%m')}."
)

# --------------------------------------------------
# Monthly financial performance
# --------------------------------------------------

st.markdown("### 1. Monthly revenue, expenses and profit")

monthly_display = filtered.melt(
    id_vars="month",
    value_vars=["total_income", "expenses", "net_profit"],
    var_name="measure",
    value_name="amount",
)

monthly_display["measure"] = monthly_display["measure"].map({
    "total_income": "Total income",
    "expenses": "Expenses",
    "net_profit": "Net profit",
})

fig = px.line(
    monthly_display,
    x="month",
    y="amount",
    color="measure",
    markers=True,
    title="Monthly financial performance",
    labels={
        "month": "Month",
        "amount": "Amount (INR)",
        "measure": "Measure",
    },
)
fig.update_layout(hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------
# P&L detail
# --------------------------------------------------

st.markdown("### 2. Monthly profit and loss statement")

pnl_table = filtered[[
    "month", "operating_revenue", "other_income",
    "total_income", "expenses", "net_profit",
]].copy()

pnl_table["month"] = pnl_table["month"].dt.strftime("%Y-%m")
pnl_table = pnl_table.rename(columns={
    "month": "Month",
    "operating_revenue": "Operating revenue (INR)",
    "other_income": "Other income (INR)",
    "total_income": "Total income (INR)",
    "expenses": "Expenses (INR)",
    "net_profit": "Net profit (INR)",
})

st.dataframe(
    pnl_table.style.format({
        column: "₹{:,.2f}"
        for column in pnl_table.columns
        if column != "Month"
    }),
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "Operating revenue uses accounts 4001–4004. "
    "Other income uses account 4900 and is displayed separately."
)

# --------------------------------------------------
# Expense categories
# --------------------------------------------------

st.markdown("### 3. Expense by category")

if not categories.empty:
    categories["amount_excl_gst"] = pd.to_numeric(
        categories["amount_excl_gst"], errors="coerce"
    )
    category_view = categories.sort_values(
        "amount_excl_gst", ascending=False
    )

    fig = px.bar(
        category_view,
        x="amount_excl_gst",
        y="category",
        orientation="h",
        title="Expense by category (excluding GST)",
        labels={
            "amount_excl_gst": "Expense excluding GST (INR)",
            "category": "Category",
        },
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        category_view.rename(columns={
            "account_code": "Account code",
            "category": "Category",
            "expense_count": "Expense count",
            "amount_excl_gst": "Amount excluding GST (INR)",
            "gst_amount": "GST (INR)",
            "total_amount_incl_gst": "Total including GST (INR)",
        }).style.format({
            "Amount excluding GST (INR)": "₹{:,.2f}",
            "GST (INR)": "₹{:,.2f}",
            "Total including GST (INR)": "₹{:,.2f}",
        }),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.warning("Expense category data is unavailable.")

# --------------------------------------------------
# Vendor spend
# --------------------------------------------------

st.markdown("### 4. Top 10 vendors")

if not vendors.empty:
    vendors["amount_excl_gst"] = pd.to_numeric(
        vendors["amount_excl_gst"], errors="coerce"
    )
    top_vendors = vendors.sort_values(
        "amount_excl_gst", ascending=False
    ).head(10)

    fig = px.bar(
        top_vendors.sort_values("amount_excl_gst"),
        x="amount_excl_gst",
        y="vendor_name",
        orientation="h",
        title="Top 10 vendors by spend (excluding GST)",
        labels={
            "amount_excl_gst": "Spend excluding GST (INR)",
            "vendor_name": "Vendor",
        },
    )
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        top_vendors[[
            "vendor_id", "vendor_name", "expense_count",
            "amount_excl_gst", "gst_amount", "total_amount_incl_gst",
        ]].rename(columns={
            "vendor_id": "Vendor ID",
            "vendor_name": "Vendor",
            "expense_count": "Expense count",
            "amount_excl_gst": "Spend excluding GST (INR)",
            "gst_amount": "GST (INR)",
            "total_amount_incl_gst": "Total including GST (INR)",
        }).style.format({
            "Spend excluding GST (INR)": "₹{:,.2f}",
            "GST (INR)": "₹{:,.2f}",
            "Total including GST (INR)": "₹{:,.2f}",
        }),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.warning("Vendor data is unavailable.")

# --------------------------------------------------
# Reconciliation
# --------------------------------------------------

st.markdown("### 5. Expense-to-ledger reconciliation")

if not reconciliation.empty:
    reconciliation["difference"] = pd.to_numeric(
        reconciliation["difference"], errors="coerce"
    )
    reconciliation["clean_expense_excl_gst"] = pd.to_numeric(
        reconciliation["clean_expense_excl_gst"], errors="coerce"
    )
    reconciliation["ledger_net_expense"] = pd.to_numeric(
        reconciliation["ledger_net_expense"], errors="coerce"
    )

    exceptions = reconciliation[
        reconciliation["difference"].abs() > 0.01
    ].copy()

    if exceptions.empty:
        st.success("All expense categories reconcile with the ledger.")
    else:
        st.warning(
            f"{len(exceptions)} expense category/categories have "
            "a difference between clean expense records and the ledger."
        )

    st.dataframe(
        reconciliation.rename(columns={
            "account_code": "Account code",
            "category": "Category",
            "clean_expense_count": "Clean expense count",
            "clean_expense_excl_gst": "Clean expense (INR)",
            "ledger_net_expense": "Ledger expense (INR)",
            "difference": "Difference (INR)",
        }).style.format({
            "Clean expense (INR)": "₹{:,.2f}",
            "Ledger expense (INR)": "₹{:,.2f}",
            "Difference (INR)": "₹{:,.2f}",
        }),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.warning("Expense reconciliation data is unavailable.")

# --------------------------------------------------
# M17 validation
# --------------------------------------------------

st.markdown("### 6. Governed net profit validation")

max_difference = filtered["m17_difference"].abs().max()

if pd.notna(max_difference) and max_difference <= 0.01:
    st.success(
        "PQ-11 monthly net profit matches governed metric M17 "
        "for every month in the selected range."
    )
else:
    st.error(
        f"M17 reconciliation difference detected. "
        f"Maximum absolute difference: ₹{max_difference:,.2f}"
    )

# --------------------------------------------------
# Source exception
# --------------------------------------------------

st.markdown("### 7. Source data exception")

st.warning(
    "**EXP-00371 — Travel & Conveyance — ₹164,090.00**\n\n"
    "This expense is present in the ledger but excluded from the clean "
    "expense fact because its source total is ₹500 higher than "
    "amount excluding GST plus GST. The raw source record is preserved "
    "and the expense remains quarantined. This explains the difference "
    "in account 5106 reconciliation. Vendor and category charts use "
    "clean expense records and therefore exclude this record."
)

# --------------------------------------------------
# Reconciliation limitation
# --------------------------------------------------

st.markdown("### 8. P&L reference and reconciliation scope")

st.info(
    "The Phase 1 README does not contain a monthly P&L headline table. "
    "The April 2025 P&L is checked against the available reconciliation "
    "answer-key sample, and all 18 monthly net profit values are checked "
    "against governed metric M17. This dashboard does not claim an "
    "18-month README headline reconciliation."
)

st.caption(
    "PulseIQ | Phase 2 | PQ-11 | Source: warehouse.fact_ledger, "
    "dim_account, fact_expense and dim_vendor. "
    "Expense category and vendor spend exclude GST."
)
