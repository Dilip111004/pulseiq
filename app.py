import streamlit as st

st.set_page_config(
    page_title="PulseIQ Analytics Platform",
    page_icon="📊",
    layout="wide"
)

pages = {
    "PHASE 2 - OFFICIAL TASKS": [
        st.Page("pages/2_Attendance_and_Leave.py", title="PQ-06 | Attendance & Leave", default=True),
        st.Page("pages/3_Attrition_Analytics.py", title="PQ-07 | Attrition Analytics"),
        st.Page("pages/4_Team_Productivity.py", title="PQ-08 | Team Productivity"),
        st.Page("pages/5_Payroll_Cost.py", title="PQ-09 | Payroll Cost"),
        st.Page("pages/6_Budget_vs_Actual.py", title="PQ-10 | Budget vs Actual"),
    ],
    "ADDITIONAL ANALYTICS": [
        st.Page("pages/9_Cross_Department_Impact.py", title="Cross-Department Impact"),
        st.Page("pages/10_AI_Signals.py", title="AI Signals"),
        st.Page("pages/11_Executive_Scorecard.py", title="Executive Scorecard"),
        st.Page("pages/12_Custom_KPI_Builder.py", title="Custom KPI Builder"),
    ],
}

navigation = st.navigation(pages, position="sidebar")
navigation.run()
