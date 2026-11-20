from pathlib import Path
import duckdb
import pandas as pd
import streamlit as st
import plotly.express as px
import numpy as np

st.set_page_config(
    page_title="PQ-12 | Receivables and Cash Flow",
    layout="wide"
)

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "outputs" / "pulseiq.duckdb"

st.title("PQ-12 | Invoices, Receivables and Cash Flow")
st.caption("Receivables ageing and monthly cash movement")

if not DB_PATH.exists():
    st.error(f"DuckDB database not found: {DB_PATH}")
    st.stop()


@st.cache_data
def load_data():
    con = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        invoices = con.execute("""
            SELECT
                i.invoice_id,
                i.invoice_number,
                i.client_id,
                c.client_name,
                CAST(i.invoice_date AS DATE) AS invoice_date,
                CAST(i.due_date AS DATE) AS due_date,
                i.total_amount,
                i.amount_paid,
                i.balance_due,
                i.status,
                i.days_to_pay,
                i.days_past_due_at_cutoff,
                i.ageing_bucket_at_cutoff
            FROM warehouse.fact_invoice i
            LEFT JOIN warehouse.dim_client c
                ON i.client_id = c.client_id
        """).df()

        payments = con.execute("""
            SELECT
                payment_id,
                invoice_id,
                CAST(payment_date AS DATE) AS payment_date,
                amount,
                payment_mode
            FROM warehouse.fact_invoice_payment
        """).df()

        expenses = con.execute("""
            SELECT
                expense_id,
                CAST(paid_date AS DATE) AS paid_date,
                total_amount,
                status,
                vendor_id
            FROM warehouse.fact_expense
            WHERE paid_date IS NOT NULL
        """).df()

        return invoices, payments, expenses

    finally:
        con.close()


try:
    invoices, payments, expenses = load_data()

except Exception as exc:
    st.error(f"Could not load warehouse data: {exc}")
    st.stop()


# --------------------------------------------------
# DATA PREPARATION
# --------------------------------------------------

for col in ["invoice_date", "due_date"]:
    invoices[col] = pd.to_datetime(invoices[col], errors="coerce")

payments["payment_date"] = pd.to_datetime(
    payments["payment_date"], errors="coerce"
)

expenses["paid_date"] = pd.to_datetime(
    expenses["paid_date"], errors="coerce"
)

invoices["balance_due"] = pd.to_numeric(
    invoices["balance_due"], errors="coerce"
).fillna(0)

invoices["days_past_due_at_cutoff"] = pd.to_numeric(
    invoices["days_past_due_at_cutoff"], errors="coerce"
).fillna(0)

invoices["days_to_pay"] = pd.to_numeric(
    invoices["days_to_pay"], errors="coerce"
)

OPEN_STATUSES = ["SENT", "OVERDUE", "PARTIALLY_PAID"]

open_invoices = invoices[
    invoices["status"].isin(OPEN_STATUSES)
    & (invoices["balance_due"] > 0)
].copy()

# Calculate ageing from the supplied cutoff-day field.
days = open_invoices["days_past_due_at_cutoff"]

open_invoices["Ageing Bucket"] = np.select(
    [
        days <= 0,
        (days >= 1) & (days <= 30),
        (days >= 31) & (days <= 60),
        (days >= 61) & (days <= 90),
        days > 90
    ],
    [
        "Not yet due",
        "0-30 days",
        "31-60 days",
        "61-90 days",
        "90+ days"
    ],
    default="Not classified"
)

bucket_order = [
    "Not yet due",
    "0-30 days",
    "31-60 days",
    "61-90 days",
    "90+ days",
    "Not classified"
]


def format_inr_crore(value):
    return f"₹{value / 10000000:,.2f} Cr"


# --------------------------------------------------
# RECEIVABLES OVERVIEW
# --------------------------------------------------

st.header("1. Receivables Overview")

total_receivables = open_invoices["balance_due"].sum()

overdue_invoices = open_invoices[
    open_invoices["days_past_due_at_cutoff"] > 0
]

overdue_amount = overdue_invoices["balance_due"].sum()

not_due_amount = open_invoices.loc[
    open_invoices["days_past_due_at_cutoff"] <= 0,
    "balance_due"
].sum()

partial_count = (
    open_invoices["status"] == "PARTIALLY_PAID"
).sum()

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Open Receivables",
    format_inr_crore(total_receivables)
)

c2.metric(
    "Overdue Receivables",
    format_inr_crore(overdue_amount)
)

c3.metric(
    "Not Yet Due",
    format_inr_crore(not_due_amount)
)

c4.metric(
    "Overdue Invoices",
    f"{len(overdue_invoices):,}"
)

st.caption(
    "Open statuses included: SENT, OVERDUE and PARTIALLY_PAID. "
    "Ageing is based on days_past_due_at_cutoff."
)

st.write(
    f"Partially paid open invoices: **{partial_count:,}**"
)


# --------------------------------------------------
# RECEIVABLES AGEING
# --------------------------------------------------

st.header("2. Receivables Ageing")

ageing = (
    open_invoices.groupby("Ageing Bucket", observed=False)
    .agg(
        Invoice_Count=("invoice_id", "count"),
        Outstanding=("balance_due", "sum")
    )
    .reindex(bucket_order, fill_value=0)
    .reset_index()
)

ageing["Invoice_Count"] = ageing["Invoice_Count"].fillna(0).astype(int)
ageing["Outstanding"] = ageing["Outstanding"].fillna(0)

fig_ageing = px.bar(
    ageing,
    x="Ageing Bucket",
    y="Outstanding",
    color="Ageing Bucket",
    text="Outstanding",
    title="Outstanding Receivables by Ageing Bucket",
    hover_data={
        "Invoice_Count": True,
        "Outstanding": ":,.2f"
    }
)

fig_ageing.update_traces(
    texttemplate="₹%{y:,.0f}",
    textposition="outside",
    cliponaxis=False
)

fig_ageing.update_layout(
    xaxis_title="Ageing Bucket",
    yaxis_title="Outstanding Amount (₹)",
    showlegend=False
)

st.plotly_chart(fig_ageing, use_container_width=True)

ageing_display = ageing.copy()
ageing_display["Outstanding"] = ageing_display["Outstanding"].map(
    lambda x: f"₹{x:,.2f}"
)

st.dataframe(
    ageing_display,
    use_container_width=True,
    hide_index=True
)


# --------------------------------------------------
# AGEING RECONCILIATION
# --------------------------------------------------

st.subheader("Ageing Reconciliation")

bucket_total = ageing["Outstanding"].sum()
difference = total_receivables - bucket_total

rc1, rc2, rc3 = st.columns(3)

rc1.metric(
    "Total Open Receivables",
    format_inr_crore(total_receivables)
)

rc2.metric(
    "Ageing Bucket Total",
    format_inr_crore(bucket_total)
)

rc3.metric(
    "Difference",
    f"₹{difference:,.2f}"
)

if abs(difference) < 0.01:
    st.success("PASS: Ageing buckets reconcile to total open receivables.")
else:
    st.error(
        f"FAIL: Ageing difference is ₹{difference:,.2f}. "
        "Investigate unclassified or missing ageing records."
    )


# --------------------------------------------------
# MONTHLY CASH INFLOW AND OUTFLOW
# --------------------------------------------------

st.header("5. Monthly Cash Flow")

cash_in = (
    payments.dropna(subset=["payment_date"])
    .assign(
        period=lambda df: df["payment_date"].dt.strftime("%Y-%m")
    )
    .groupby("period")["amount"]
    .sum()
    .rename("Cash Inflow")
)

paid_expenses = expenses[
    (expenses["status"] == "PAID")
    & expenses["paid_date"].notna()
].copy()

cash_out = (
    paid_expenses.assign(
        period=lambda df: df["paid_date"].dt.strftime("%Y-%m")
    )
    .groupby("period")["total_amount"]
    .sum()
    .rename("Cash Outflow")
)

cash_flow = pd.concat(
    [cash_in, cash_out],
    axis=1
).fillna(0).reset_index()

cash_flow = cash_flow.rename(
    columns={"index": "period"}
)

cash_flow = cash_flow.sort_values("period")

cash_flow["Net Cash Movement"] = (
    cash_flow["Cash Inflow"] - cash_flow["Cash Outflow"]
)

if not cash_flow.empty:

    fig_cash = px.bar(
        cash_flow,
        x="period",
        y=["Cash Inflow", "Cash Outflow"],
        barmode="group",
        title="Monthly Cash Inflow vs Cash Outflow"
    )

    fig_cash.update_layout(
        xaxis_title="Month",
        yaxis_title="Amount (₹)",
        legend_title="Cash Movement",
        hovermode="x unified"
    )

    st.plotly_chart(
        fig_cash,
        use_container_width=True
    )

    fig_net = px.line(
        cash_flow,
        x="period",
        y="Net Cash Movement",
        markers=True,
        title="Monthly Net Cash Movement"
    )

    fig_net.update_layout(
        xaxis_title="Month",
        yaxis_title="Net Cash Movement (₹)"
    )

    st.plotly_chart(
        fig_net,
        use_container_width=True
    )

    with st.expander("View Monthly Cash Flow Details"):

        cash_display = cash_flow.copy()

        for col in [
            "Cash Inflow",
            "Cash Outflow",
            "Net Cash Movement"
        ]:
            cash_display[col] = cash_display[col].map(
                lambda x: f"₹{x:,.2f}"
            )

        st.dataframe(
            cash_display,
            use_container_width=True,
            hide_index=True
        )

else:
    st.warning("No cash flow records found.")


# --------------------------------------------------
# CASH FLOW SUMMARY
# --------------------------------------------------

total_cash_in = payments["amount"].sum()

total_cash_out = paid_expenses["total_amount"].sum()

net_cash_movement = total_cash_in - total_cash_out

cc1, cc2, cc3 = st.columns(3)

cc1.metric(
    "Total Cash Inflow",
    format_inr_crore(total_cash_in)
)

cc2.metric(
    "Total Cash Outflow",
    format_inr_crore(total_cash_out)
)

cc3.metric(
    "Net Cash Movement",
    format_inr_crore(net_cash_movement)
)


# --------------------------------------------------
# KEY FINDINGS
# --------------------------------------------------

st.header("7. Key Findings")

st.write(
    f"1. Total open receivables are "
    f"{format_inr_crore(total_receivables)}."
)

st.write(
    f"2. Overdue receivables account for "
    f"{format_inr_crore(overdue_amount)}."
)

# METHODOLOGY
# --------------------------------------------------

st.info(
    "Methodology: Open receivables include SENT, OVERDUE and "
    "PARTIALLY_PAID invoices with a positive balance. Ageing uses "
    "days_past_due_at_cutoff. Cash inflow uses fact_invoice_payment "
    "payment dates and amounts. Cash outflow uses PAID fact_expense "
    "records, paid dates and total_amount. Cash movement is a "
    "transaction-based view and may not equal the full ledger cash "
    "movement."
)

st.caption(
    "Sources: warehouse.fact_invoice, warehouse.fact_invoice_payment, "
    "warehouse.dim_client and warehouse.fact_expense."
)
