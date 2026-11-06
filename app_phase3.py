import streamlit as st

st.set_page_config(
    page_title="PulseIQ | Phase 3",
    page_icon="📊",
    layout="wide"
)

pages = {
    "PHASE 3 - MONEY AND INSIGHT": [
        st.Page("pages/13_PL_and_Expense_Analytics.py",
                title="PQ-11 | P&L and Expense Analytics", default=True),
        st.Page("pages/14_Invoices_Receivables_Cash_Flow.py",
                title="PQ-12 | Invoices, Receivables and Cash Flow"),
        st.Page("pages/9_Cross_Department_Impact.py",
                title="PQ-13 | Cross-Department Impact"),
        st.Page("pages/10_AI_Signals.py",
                title="PQ-14 | AI Signals"),
        st.Page("pages/11_Executive_Scorecard.py",
                title="PQ-15 | Executive Scorecard"),
    ],
    "HIDDEN PAGES": [
        st.Page("pages/2_Attendance_and_Leave.py",
                title="Attendance and Leave", visibility="hidden"),
        st.Page("pages/3_Attrition_Analytics.py",
                title="Attrition Analytics", visibility="hidden"),
    ]
}

navigation = st.navigation(pages, position="sidebar")
navigation.run()
