#!/usr/bin/env python3
"""PulseIQ Phase 3 Streamlit entry point with automatic DuckDB initialization."""

from pathlib import Path
import subprocess
import sys

import duckdb
import streamlit as st

st.set_page_config(
    page_title="PulseIQ | Phase 3",
    page_icon="📊",
    layout="wide",
)

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "outputs" / "pulseiq.duckdb"


def database_is_usable() -> bool:
    """Return True only when the DuckDB file exists and can be opened."""
    if not DB_PATH.is_file() or DB_PATH.stat().st_size == 0:
        return False
    try:
        with duckdb.connect(str(DB_PATH), read_only=True) as con:
            con.execute("SELECT 1").fetchone()
        return True
    except Exception:
        return False


@st.cache_resource(show_spinner="Preparing PulseIQ data warehouse...")
def initialize_database() -> tuple[bool, str]:
    """Build the clean data and warehouse once per Streamlit server process."""
    if database_is_usable():
        return True, "Existing DuckDB warehouse is ready."

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Remove only an absent/unusable generated database, never source CSV files.
    if DB_PATH.exists():
        DB_PATH.unlink()

    commands = [
        [sys.executable, str(ROOT / "src" / "run_etl.py")],
        [sys.executable, str(ROOT / "src" / "build_warehouse.py")],
    ]
    output = []

    for command in commands:
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        output.append("$ " + " ".join(command))
        if result.stdout:
            output.append(result.stdout)
        if result.stderr:
            output.append(result.stderr)

        if result.returncode != 0:
            if DB_PATH.exists():
                DB_PATH.unlink()
            return False, "\n".join(output) + (
                f"\nPipeline stopped with exit code {result.returncode}."
            )

    if not database_is_usable():
        if DB_PATH.exists():
            DB_PATH.unlink()
        return False, "\n".join(output) + (
            "\nPipeline finished, but the DuckDB file is missing or unusable."
        )

    return True, "\n".join(output) or "DuckDB warehouse created successfully."


st.set_page_config(
    page_title="PulseIQ | Phase 3",
    page_icon="📊",
    layout="wide",
)

ready, details = initialize_database()
if not ready:
    st.error("PulseIQ could not initialize its DuckDB warehouse.")
    st.code(details)
    st.stop()

pages = {
    "PHASE 3 - MONEY AND INSIGHT": [
        st.Page(
            "pages/13_PL_and_Expense_Analytics.py",
            title="PQ-11 | P&L and Expense Analytics",
            default=True,
        ),
        st.Page(
            "pages/14_Invoices_Receivables_Cash_Flow.py",
            title="PQ-12 | Invoices, Receivables and Cash Flow",
        ),
        st.Page(
            "pages/9_Cross_Department_Impact.py",
            title="PQ-13 | Cross-Department Impact",
        ),
        st.Page(
            "pages/10_AI_Signals.py",
            title="PQ-14 | AI Signals",
        ),
        st.Page(
            "pages/11_Executive_Scorecard.py",
            title="PQ-15 | Executive Scorecard",
        ),
    ],
    "HIDDEN PAGES": [
        st.Page(
            "pages/2_Attendance_and_Leave.py",
            title="Attendance and Leave",
            visibility="hidden",
        ),
        st.Page(
            "pages/3_Attrition_Analytics.py",
            title="Attrition Analytics",
            visibility="hidden",
        ),
    ],
}

navigation = st.navigation(pages, position="sidebar")
navigation.run()
