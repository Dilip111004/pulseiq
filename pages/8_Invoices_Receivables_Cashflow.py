from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"

st.set_page_config(page_title="Invoices, Receivables & Cash Flow", layout="wide")
st.title("Invoices, Receivables & Cash Flow")
st.caption("PQ-12 | Reporting cutoff: 30 September 2026")

def load_csv(name):
    path = OUT / name
    if not path.exists():
        st.error(f"Missing file: {path}. Run: python src/run_pq12.py")
        st.stop()
    return pd.read_csv(path)

ageing = load_csv("pq12_receivables_ageing.csv")
clients = load_csv("pq12_client_payment_behaviour.csv")
overdue = load_csv("pq12_overdue_clients.csv")
cash = load_csv("pq12_monthly_cash_flow.csv")

bucket_order = ["Current", "1-30 days", "31-60 days", "61-90 days", "90+ days"]
ageing = ageing.set_index("ageing_bucket").reindex(bucket_order, fill_value=0).reset_index()

open_receivables = ageing["receivables"].sum()
overdue_total = overdue["overdue_balance"].sum()
avg_days = (clients["avg_days_to_pay"] * clients["paid_invoices"]).sum() / clients["paid_invoices"].sum()
total_cash_in = cash["cash_in"].sum()
total_cash_out = cash["cash_out"].sum()

def inr(value):
    return f"₹{value:,.0f}"

k1, k2, k3, k4 = st.columns(4)
k1.metric("Open receivables", inr(open_receivables))
k2.metric("Overdue receivables", inr(overdue_total))
k3.metric("Average days to pay", f"{avg_days:.1f} days")
k4.metric("Net cash movement", inr(total_cash_in - total_cash_out))

st.divider()
left, right = st.columns(2)

with left:
    st.subheader("Receivables ageing")
    fig = px.bar(
        ageing, x="ageing_bucket", y="receivables",
        text="receivables", category_orders={"ageing_bucket": bucket_order},
        labels={"ageing_bucket": "Ageing bucket", "receivables": "Receivables (₹)"}
    )
    fig.update_traces(texttemplate="₹%{text:,.0f}", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(ageing, use_container_width=True, hide_index=True)

with right:
    st.subheader("Monthly cash in vs cash out")
    cash["month_start"] = pd.to_datetime(cash["month_start"])
    cash["month"] = cash["month_start"].dt.strftime("%b %Y")
    cash_long = cash.melt(
        id_vars=["month_start", "month"],
        value_vars=["cash_in", "cash_out"],
        var_name="cash_type", value_name="amount"
    )
    fig = px.bar(
        cash_long, x="month", y="amount", color="cash_type", barmode="group",
        labels={"month": "Month", "amount": "Amount (₹)", "cash_type": "Cash movement"}
    )
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Slowest-paying clients")
slow = clients.sort_values("avg_days_to_pay", ascending=False).head(10)
st.dataframe(
    slow[["client_name", "paid_invoices", "avg_days_to_pay",
          "payment_terms_days", "avg_days_over_terms"]],
    use_container_width=True, hide_index=True
)

st.subheader("Overdue clients")
st.dataframe(
    overdue.sort_values("overdue_balance", ascending=False),
    use_container_width=True, hide_index=True
)

st.subheader("Cash movement summary")
c1, c2, c3 = st.columns(3)
c1.metric("Total cash in", inr(total_cash_in))
c2.metric("Total cash out", inr(total_cash_out))
c3.metric("Net cash movement", inr(total_cash_in - total_cash_out))

st.caption("Cash in uses invoice payment dates. Cash out includes paid expenses only. Ageing includes SENT, OVERDUE and PARTIALLY_PAID invoices with a positive balance.")
