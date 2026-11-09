from pathlib import Path
import duckdb
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(
    page_title="PQ-11 | P&L Analytics",
    layout="wide"
)

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "outputs" / "pulseiq.duckdb"

st.title("PQ-11 | P&L and Expense Analytics")
st.caption("Monthly profitability, expense categories and vendor analysis")

if not DB_PATH.exists():
    st.error(f"DuckDB database not found: {DB_PATH}")
    st.stop()


@st.cache_data
def load_data():
    con = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        pnl = con.execute("""
            SELECT
                CAST(l.entry_date AS DATE) AS entry_date,
                CAST(l.account_code AS VARCHAR) AS account_code,
                a.account_name,
                a.account_type,
                l.signed_amount_debit_positive
            FROM warehouse.fact_ledger l
            JOIN warehouse.dim_account a
              ON CAST(l.account_code AS VARCHAR)
               = CAST(a.account_code AS VARCHAR)
            WHERE
                COALESCE(CAST(a.is_group AS VARCHAR), 'N') <> 'Y'
                AND (
                    CAST(a.account_code AS VARCHAR) LIKE '4%'
                    OR CAST(a.account_code AS VARCHAR) LIKE '5%'
                )
        """).df()

        expenses = con.execute("""
            SELECT
                CAST(e.expense_date AS DATE) AS expense_date,
                CAST(e.category_account AS VARCHAR) AS account_code,
                a.account_name AS category,
                e.vendor_id,
                v.vendor_name,
                e.amount_excl_gst
            FROM warehouse.fact_expense e
            LEFT JOIN warehouse.dim_account a
              ON CAST(e.category_account AS VARCHAR)
               = CAST(a.account_code AS VARCHAR)
            LEFT JOIN warehouse.dim_vendor v
              ON e.vendor_id = v.vendor_id
        """).df()

        return pnl, expenses

    finally:
        con.close()


try:
    ledger, expenses = load_data()

except Exception as exc:
    st.error(f"Could not load warehouse data: {exc}")
    st.stop()


ledger["entry_date"] = pd.to_datetime(ledger["entry_date"])
expenses["expense_date"] = pd.to_datetime(expenses["expense_date"])

ledger["period"] = ledger["entry_date"].dt.strftime("%Y-%m")
expenses["period"] = expenses["expense_date"].dt.strftime("%Y-%m")

ledger["account_code"] = ledger["account_code"].astype(str)

# --------------------------------------------------
# MONTHLY PROFIT AND LOSS
# --------------------------------------------------

revenue_rows = ledger[
    ledger["account_code"].str.startswith("4")
    & (ledger["account_code"] != "4900")
]

other_income_rows = ledger[
    ledger["account_code"] == "4900"
]

expense_rows = ledger[
    ledger["account_code"].str.startswith("5")
]

monthly_revenue = (
    revenue_rows.groupby("period")["signed_amount_debit_positive"]
    .sum()
    .mul(-1)
)

monthly_other_income = (
    other_income_rows.groupby("period")["signed_amount_debit_positive"]
    .sum()
    .mul(-1)
)

monthly_expenses = (
    expense_rows.groupby("period")["signed_amount_debit_positive"]
    .sum()
)

periods = sorted(ledger["period"].dropna().unique())

monthly = pd.DataFrame({"period": periods})

monthly["Operating Revenue"] = (
    monthly["period"].map(monthly_revenue).fillna(0)
)

monthly["Other Income"] = (
    monthly["period"].map(monthly_other_income).fillna(0)
)

monthly["Expenses"] = (
    monthly["period"].map(monthly_expenses).fillna(0)
)

monthly["Operating Profit"] = (
    monthly["Operating Revenue"] - monthly["Expenses"]
)

monthly["Net Profit"] = (
    monthly["Operating Profit"] + monthly["Other Income"]
)

monthly["Operating Margin %"] = (
    monthly["Operating Profit"]
    / monthly["Operating Revenue"].replace(0, pd.NA)
) * 100


# --------------------------------------------------
# MONTH FILTER
# --------------------------------------------------

st.subheader("Monthly P&L")

selected_periods = st.multiselect(
    "Select months",
    options=periods,
    default=periods
)

if not selected_periods:
    st.warning("Select at least one month.")
    st.stop()

view = monthly[
    monthly["period"].isin(selected_periods)
].copy()

expense_view = expenses[
    expenses["period"].isin(selected_periods)
].copy()


# --------------------------------------------------
# KPI CARDS - CRORE FORMATTING
# --------------------------------------------------

total_revenue = view["Operating Revenue"].sum()
total_other_income = view["Other Income"].sum()
total_expenses = view["Expenses"].sum()

operating_profit = total_revenue - total_expenses
net_profit = operating_profit + total_other_income

operating_margin = (
    operating_profit / total_revenue * 100
    if total_revenue else 0
)


def format_inr_crore(value):
    return f"₹{value / 10_000_000:,.2f} Cr"


c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Operating Revenue",
    format_inr_crore(total_revenue)
)

c2.metric(
    "Total Expenses",
    format_inr_crore(total_expenses)
)

c3.metric(
    "Net Profit",
    format_inr_crore(net_profit)
)

c4.metric(
    "Operating Margin",
    f"{operating_margin:.2f}%"
)


# --------------------------------------------------
# MONTHLY P&L TABLE
# --------------------------------------------------

st.dataframe(
    view.style.format({
        "Operating Revenue": "₹{:,.2f}",
        "Other Income": "₹{:,.2f}",
        "Expenses": "₹{:,.2f}",
        "Operating Profit": "₹{:,.2f}",
        "Net Profit": "₹{:,.2f}",
        "Operating Margin %": "{:.2f}%"
    }),
    use_container_width=True,
    hide_index=True
)


# --------------------------------------------------
# REVENUE, EXPENSE AND PROFIT TREND
# --------------------------------------------------

st.subheader("Revenue, Expenses and Profit Trend")

trend = view.melt(
    id_vars="period",
    value_vars=[
        "Operating Revenue",
        "Expenses",
        "Operating Profit"
    ],
    var_name="Metric",
    value_name="Amount"
)

fig = px.line(
    trend,
    x="period",
    y="Amount",
    color="Metric",
    markers=True,
    title="Monthly financial performance"
)

fig.update_layout(
    xaxis_title="Month",
    yaxis_title="Amount (₹)",
    hovermode="x unified"
)

st.plotly_chart(
    fig,
    use_container_width=True
)


# --------------------------------------------------
# EXPENSE CATEGORY AND VENDOR ANALYSIS
# --------------------------------------------------

st.subheader("Expense Analysis")

if not expense_view.empty:

    category_data = (
        expense_view.groupby(
            ["account_code", "category"],
            dropna=False
        )["amount_excl_gst"]
        .sum()
        .reset_index()
        .sort_values(
            "amount_excl_gst",
            ascending=False
        )
    )

    vendor_data = (
        expense_view.groupby(
            ["vendor_id", "vendor_name"],
            dropna=False
        )["amount_excl_gst"]
        .sum()
        .reset_index()
        .sort_values(
            "amount_excl_gst",
            ascending=False
        )
        .head(10)
    )

    col1, col2 = st.columns(2)

    with col1:

        st.markdown("**Expenses by Category**")

        fig_category = px.bar(
            category_data,
            x="amount_excl_gst",
            y="category",
            orientation="h",
            title="Expense category totals (excluding GST)"
        )

        fig_category.update_layout(
            yaxis={"categoryorder": "total ascending"},
            xaxis_title="Amount excluding GST (₹)",
            yaxis_title="Category"
        )

        st.plotly_chart(
            fig_category,
            use_container_width=True
        )

    with col2:

        st.markdown("**Top 10 Vendors**")

        fig_vendor = px.bar(
            vendor_data,
            x="amount_excl_gst",
            y="vendor_name",
            orientation="h",
            title="Top 10 vendors (excluding GST)"
        )

        fig_vendor.update_layout(
            yaxis={"categoryorder": "total ascending"},
            xaxis_title="Amount excluding GST (₹)",
            yaxis_title="Vendor"
        )

        st.plotly_chart(
            fig_vendor,
            use_container_width=True
        )

    with st.expander("View Expense Category Details"):
        st.dataframe(
            category_data.style.format({
                "amount_excl_gst": "₹{:,.2f}"
            }),
            use_container_width=True,
            hide_index=True
        )

    with st.expander("View Top 10 Vendor Details"):
        st.dataframe(
            vendor_data.style.format({
                "amount_excl_gst": "₹{:,.2f}"
            }),
            use_container_width=True,
            hide_index=True
        )

else:
    st.warning("No expense records found for the selected months.")


# --------------------------------------------------
# EXPENSE-TO-LEDGER RECONCILIATION
# --------------------------------------------------

st.subheader("Expense-to-Ledger Reconciliation")

con = duckdb.connect(
    str(DB_PATH),
    read_only=True
)

try:

    recon = con.execute("""
        SELECT
            COUNT(*) AS expense_records,

            COUNT(e.ledger_entry_id)
                AS linked_records,

            COUNT(DISTINCT e.ledger_entry_id)
                AS distinct_linked_entries,

            SUM(e.amount_excl_gst)
                AS expense_amount_excl_gst,

            SUM(e.total_amount)
                AS expense_total_incl_gst,

            SUM(
                CASE
                    WHEN l.entry_id IS NOT NULL
                    THEN 1 ELSE 0
                END
            ) AS matching_ledger_lines,

            SUM(
                CASE
                    WHEN l.entry_id IS NOT NULL
                     AND ABS(l.debit - e.amount_excl_gst) < 0.01
                    THEN 1 ELSE 0
                END
            ) AS debit_matches_excl_gst

        FROM warehouse.fact_expense e

        LEFT JOIN warehouse.fact_ledger l
          ON e.ledger_entry_id = l.entry_id
         AND CAST(e.category_account AS VARCHAR)
           = CAST(l.account_code AS VARCHAR)

    """).df()

finally:
    con.close()


r = recon.iloc[0]

st.markdown("**Reconciliation Summary**")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Expense Records",
    f"{int(r['expense_records']):,}"
)

col2.metric(
    "Linked Records",
    f"{int(r['linked_records']):,}"
)

col3.metric(
    "Matching Ledger Lines",
    f"{int(r['matching_ledger_lines']):,}"
)

col4.metric(
    "Debit Matches",
    f"{int(r['debit_matches_excl_gst']):,}"
)


recon_details = pd.DataFrame({
    "Reconciliation Metric": [
        "Distinct linked entries",
        "Expense amount excluding GST",
        "Expense total including GST",
        "Ledger debit matches excluding GST"
    ],

    "Value": [
        f"{int(r['distinct_linked_entries']):,}",
        f"₹{r['expense_amount_excl_gst']:,.2f}",
        f"₹{r['expense_total_incl_gst']:,.2f}",
        f"{int(r['debit_matches_excl_gst']):,}"
    ]
})

st.dataframe(
    recon_details,
    use_container_width=True,
    hide_index=True
)

st.caption(
    "Reconciliation covers the full expense table, not just selected months. "
    "Expense ledger debits are compared with amount_excl_gst, not total_amount."
)


# --------------------------------------------------
# KEY FINDINGS
# --------------------------------------------------

st.subheader("Key Findings")

if len(monthly) >= 2:

    first = monthly.iloc[0]
    last = monthly.iloc[-1]

    revenue_change = (
        last["Operating Revenue"] - first["Operating Revenue"]
    )

    margin_change = (
        last["Operating Margin %"] - first["Operating Margin %"]
    )

    st.write(
        f"1. Operating revenue changed by "
        f"₹{revenue_change:,.2f} between "
        f"{first['period']} and {last['period']}."
    )

    st.write(
        f"2. Operating margin changed by "
        f"{margin_change:.2f} percentage points between "
        f"{first['period']} and {last['period']}."
    )

if not expense_view.empty:

    vendor_spend = (
        expense_view.groupby("vendor_name")["amount_excl_gst"]
        .sum()
    )

    largest = vendor_spend.idxmax()
    largest_amount = vendor_spend.max()

    st.write(
        f"3. Highest vendor spend in the selected period: "
        f"{largest} (₹{largest_amount:,.2f}, excluding GST)."
    )


# --------------------------------------------------
# BUSINESS INTERPRETATION
# --------------------------------------------------

st.info(
    "Interpretation: If revenue rises while margin falls, investigate "
    "salary and overtime growth, operating expenses, vendor costs, "
    "and changes in revenue mix. Confirm causes against supporting "
    "transaction-level records."
)


# --------------------------------------------------
# DATA SOURCE AND METHODOLOGY
# --------------------------------------------------

st.caption(
    "Source: warehouse.fact_ledger, warehouse.dim_account, "
    "warehouse.fact_expense and warehouse.dim_vendor. "
    "P&L uses ledger detail accounts, excluding group accounts. "
    "Expense category and vendor analysis uses bill-level "
    "amount_excl_gst."
)
