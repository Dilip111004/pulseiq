from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# --------------------------------------------------
# PulseIQ | Phase 2: Team Productivity (PQ-08)
# --------------------------------------------------

st.set_page_config(
    page_title="PulseIQ | Team Productivity",
    page_icon="📈",
    layout="wide",
)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "clean"

st.title("PulseIQ | Team Productivity Analytics")
st.caption(
    "PQ-08 | Team velocity, cycle time, delivery performance, "
    "blocked work, and reopened tasks"
)
# --------------------------------------------------
# Load source data
# --------------------------------------------------

@st.cache_data
def load_data():
    """Load the clean task, team, and sprint datasets."""
    required_files = {
        "tasks": "fact_task.csv",
        "teams": "dim_team.csv",
        "sprints": "dim_sprint.csv",
    }

    data = {}

    for key, filename in required_files.items():
        path = DATA / filename

        if not path.exists():
            st.error(f"Required data file is missing: {path}")
            st.stop()

        data[key] = pd.read_csv(path, low_memory=False)

    return data


data = load_data()

tasks = data["tasks"].copy()
teams = data["teams"].copy()
sprints = data["sprints"].copy()

st.success(
    f"Loaded {len(tasks):,} task records, "
    f"{len(teams):,} teams, and {len(sprints):,} sprints."
)

# --------------------------------------------------
# Validate columns and prepare data
# --------------------------------------------------

required_task_columns = {
    "task_id",
    "team_id",
    "sprint_id",
    "story_points",
    "created_date",
    "started_date",
    "due_date",
    "completed_date",
    "status",
    "reopened_count",
    "cycle_time_days",
    "is_overdue_at_cutoff",
    "completed_on_time",
}

required_team_columns = {
    "team_id",
    "team_name",
}

required_sprint_columns = {
    "sprint_id",
    "sprint_name",
    "start_date",
    "end_date",
    "working_days",
}

if not required_task_columns.issubset(tasks.columns):
    st.error("The task file is missing required columns.")
    st.stop()

if not required_team_columns.issubset(teams.columns):
    st.error("The team file is missing required columns.")
    st.stop()

if not required_sprint_columns.issubset(sprints.columns):
    st.error("The sprint file is missing required columns.")
    st.stop()

# Convert date fields
task_date_columns = [
    "created_date",
    "started_date",
    "due_date",
    "completed_date",
]

for column in task_date_columns:
    tasks[column] = pd.to_datetime(
        tasks[column],
        errors="coerce",
    )

sprints["start_date"] = pd.to_datetime(
    sprints["start_date"],
    errors="coerce",
)

sprints["end_date"] = pd.to_datetime(
    sprints["end_date"],
    errors="coerce",
)

# Convert numeric fields safely
for column in ["story_points", "cycle_time_days", "reopened_count"]:
    tasks[column] = pd.to_numeric(
        tasks[column],
        errors="coerce",
    )

# Standardize text flags
for column in ["is_overdue_at_cutoff", "completed_on_time"]:
    tasks[column] = (
        tasks[column]
        .astype("string")
        .str.strip()
        .str.upper()
    )

tasks["status"] = tasks["status"].astype("string").str.strip()

st.success("Required columns validated and dates prepared.")

# --------------------------------------------------
# Dashboard filters
# --------------------------------------------------

st.sidebar.header("Dashboard filters")

# Build readable sprint labels
sprint_options = sprints.sort_values("start_date").copy()

sprint_options["sprint_label"] = (
    sprint_options["sprint_name"]
    + " ("
    + sprint_options["start_date"].dt.strftime("%d %b %Y")
    + " – "
    + sprint_options["end_date"].dt.strftime("%d %b %Y")
    + ")"
)

sprint_labels = sprint_options["sprint_label"].tolist()

# Start with the three most recent sprints to keep charts readable.
# All 38 sprints remain available in the selector.
selected_sprint_labels = st.sidebar.multiselect(
    "Select sprints",
    options=sprint_labels,
    default=sprint_labels[-3:],
    help="Choose one or more sprints to analyse. The default shows the three most recent sprints.",
)

selected_sprint_ids = sprint_options.loc[
    sprint_options["sprint_label"].isin(selected_sprint_labels),
    "sprint_id",
].tolist()

# Build readable team options
team_options = teams.sort_values("team_name").copy()

selected_team_names = st.sidebar.multiselect(
    "Select teams",
    options=team_options["team_name"].tolist(),
    default=team_options["team_name"].tolist(),
    help="Choose one or more teams to compare.",
)

selected_team_ids = team_options.loc[
    team_options["team_name"].isin(selected_team_names),
    "team_id",
].tolist()

# Filter task records using the selected teams and sprints
filtered_tasks = tasks[
    tasks["team_id"].isin(selected_team_ids)
    & tasks["sprint_id"].isin(selected_sprint_ids)
].copy()

st.caption(
    f"Current selection: {len(selected_team_ids)} teams and "
    f"{len(selected_sprint_ids)} sprints."
)

# --------------------------------------------------
# Calculate productivity metrics
# --------------------------------------------------

# Completed work excludes cancelled tasks.
completed_tasks = filtered_tasks[
    filtered_tasks["status"] == "Done"
].copy()

# Sprint velocity: completed story points per team and sprint.
velocity = (
    completed_tasks.groupby(["team_id", "sprint_id"], as_index=False)
    .agg(
        velocity_story_points=("story_points", "sum"),
        completed_tasks=("task_id", "nunique"),
    )
)

# Cycle time: average cycle time for completed tasks with valid values.
cycle_time = (
    completed_tasks.dropna(subset=["cycle_time_days"])
    .groupby(["team_id", "sprint_id"], as_index=False)
    .agg(
        average_cycle_time_days=("cycle_time_days", "mean"),
        median_cycle_time_days=("cycle_time_days", "median"),
    )
)
# Overdue tasks: count tasks explicitly flagged Y.
# Cancelled tasks are excluded from overdue work.
overdue = (
    filtered_tasks[
        (filtered_tasks["is_overdue_at_cutoff"] == "Y")
        & (filtered_tasks["status"] != "Cancelled")
    ]
    .groupby(["team_id", "sprint_id"], as_index=False)
    .agg(overdue_tasks=("task_id", "nunique"))
)

# On-time delivery: completed tasks with a valid Y/N on-time flag.
valid_on_time = completed_tasks[
    completed_tasks["completed_on_time"].isin(["Y", "N"])
].copy()

on_time = (
    valid_on_time.groupby(["team_id", "sprint_id"], as_index=False)
    .agg(
        on_time_tasks=(
            "completed_on_time",
            lambda values: (values == "Y").sum(),
        ),
        eligible_completed_tasks=("task_id", "nunique"),
    )
)

on_time["on_time_rate_pct"] = (
    100
    * on_time["on_time_tasks"]
    / on_time["eligible_completed_tasks"].replace(0, pd.NA)
)

# Blocked work: current tasks with Blocked status.
blocked = (
    filtered_tasks[filtered_tasks["status"] == "Blocked"]
    .groupby(["team_id", "sprint_id"], as_index=False)
    .agg(blocked_tasks=("task_id", "nunique"))
)

# Reopened work: count tasks with one or more recorded reopen events.
reopened = (
    filtered_tasks[filtered_tasks["reopened_count"] > 0]
    .groupby(["team_id", "sprint_id"], as_index=False)
    .agg(
        reopened_tasks=("task_id", "nunique"),
        reopen_events=("reopened_count", "sum"),
    )
)

st.success("Productivity metrics calculated.")

# --------------------------------------------------
# Headline KPI cards
# --------------------------------------------------

st.divider()
st.subheader("Team productivity overview")

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

total_completed = completed_tasks["task_id"].nunique()

total_story_points = completed_tasks["story_points"].sum(
    min_count=1
)

if pd.isna(total_story_points):
    total_story_points = 0

kpi1.metric(
    "Completed tasks",
    f"{total_completed:,}",
)

kpi2.metric(
    "Completed story points",
    f"{total_story_points:,.0f}",
)

if not completed_tasks["cycle_time_days"].dropna().empty:
    average_cycle_time = completed_tasks["cycle_time_days"].mean()
    kpi3.metric(
        "Average cycle time",
        f"{average_cycle_time:.1f} days",
    )
else:
    kpi3.metric("Average cycle time", "N/A")

total_blocked = filtered_tasks.loc[
    filtered_tasks["status"] == "Blocked",
    "task_id",
].nunique()

kpi4.metric(
    "Currently blocked tasks",
    f"{total_blocked:,}",
)

total_reopened = filtered_tasks.loc[
    filtered_tasks["reopened_count"] > 0,
    "task_id",
].nunique()

kpi5.metric(
    "Tasks reopened",
    f"{total_reopened:,}",
)

st.caption(
    "Completed work includes tasks marked Done. Cancelled tasks are excluded "
    "from completed-work metrics and are not counted as overdue or outstanding work."
)

# --------------------------------------------------
# Team velocity chart
# --------------------------------------------------

st.divider()
st.subheader("1. Team Velocity")

st.caption(
    "Velocity is the sum of story points for tasks marked Done, "
    "grouped by team and sprint."
)

velocity_view = velocity.merge(
    teams[["team_id", "team_name"]],
    on="team_id",
    how="left",
)

velocity_view = velocity_view.merge(
    sprints[["sprint_id", "sprint_name"]],
    on="sprint_id",
    how="left",
)

if velocity_view.empty:
    st.info(
        "No completed tasks are available for the selected teams "
        "and sprints."
    )
else:
    velocity_chart = px.bar(
        velocity_view,
        x="team_name",
        y="velocity_story_points",
        color="sprint_name",
        barmode="group",
        title="Completed story points by team and sprint",
        labels={
            "team_name": "Team",
            "velocity_story_points": "Completed story points",
            "sprint_name": "Sprint",
        },
    )

    velocity_chart.update_layout(
        xaxis_title="Team",
        yaxis_title="Completed story points",
        legend_title_text="Sprint",
    )

    st.plotly_chart(
        velocity_chart,
        width="stretch",
    )

# --------------------------------------------------
# Cycle-time chart
# --------------------------------------------------

st.divider()
st.subheader("2. Cycle Time")

st.caption(
    "Average cycle time is calculated from completed tasks "
    "with valid cycle-time values. Lower values indicate faster delivery."
)

cycle_time_view = cycle_time.merge(
    teams[["team_id", "team_name"]],
    on="team_id",
    how="left",
)

cycle_time_view = cycle_time_view.merge(
    sprints[["sprint_id", "sprint_name"]],
    on="sprint_id",
    how="left",
)

if cycle_time_view.empty:
    st.info(
        "No valid cycle-time data is available for the selected teams "
        "and sprints."
    )
else:
    cycle_time_chart = px.bar(
        cycle_time_view,
        x="team_name",
        y="average_cycle_time_days",
        color="sprint_name",
        barmode="group",
        title="Average cycle time by team and sprint",
        labels={
            "team_name": "Team",
            "average_cycle_time_days": "Average cycle time (days)",
            "sprint_name": "Sprint",
        },
        hover_data={
            "median_cycle_time_days": ":.2f",
        },
    )

    cycle_time_chart.update_layout(
        xaxis_title="Team",
        yaxis_title="Average cycle time (days)",
        legend_title_text="Sprint",
    )

    st.plotly_chart(
        cycle_time_chart,
        width="stretch",
    )

# --------------------------------------------------
# Overdue and on-time delivery charts
# --------------------------------------------------

st.divider()
st.subheader("3. Overdue Work and On-Time Delivery")

overdue_view = overdue.merge(
    teams[["team_id", "team_name"]],
    on="team_id",
    how="left",
).merge(
    sprints[["sprint_id", "sprint_name"]],
    on="sprint_id",
    how="left",
)

on_time_view = on_time.merge(
    teams[["team_id", "team_name"]],
    on="team_id",
    how="left",
).merge(
    sprints[["sprint_id", "sprint_name"]],
    on="sprint_id",
    how="left",
)

left, right = st.columns(2)

with left:
    st.caption(
        "Tasks explicitly flagged as overdue in the source data."
    )

    if overdue_view.empty:
        st.info("No overdue tasks are recorded for this selection.")
    else:
        overdue_chart = px.bar(
            overdue_view,
            x="team_name",
            y="overdue_tasks",
            color="sprint_name",
            barmode="group",
            title="Overdue tasks by team and sprint",
            labels={
                "team_name": "Team",
                "overdue_tasks": "Overdue tasks",
                "sprint_name": "Sprint",
            },
        )

        st.plotly_chart(
            overdue_chart,
            width="stretch",
        )

with right:
    st.caption(
        "On-time rate = completed tasks marked Y divided by "
        "completed tasks with a valid Y/N flag."
    )

    if on_time_view.empty:
        st.info("No eligible on-time delivery data is available.")
    else:
        on_time_chart = px.bar(
            on_time_view,
            x="team_name",
            y="on_time_rate_pct",
            color="sprint_name",
            barmode="group",
            title="On-time delivery rate by team and sprint",
            labels={
                "team_name": "Team",
                "on_time_rate_pct": "On-time rate (%)",
                "sprint_name": "Sprint",
            },
        )

        on_time_chart.update_layout(
            yaxis_range=[0, 100],
        )

        st.plotly_chart(
            on_time_chart,
            width="stretch",
        )
# --------------------------------------------------
# Blocked and reopened work
# --------------------------------------------------

st.divider()
st.subheader("4. Blocked and Reopened Work")

blocked_view = blocked.merge(
    teams[["team_id", "team_name"]],
    on="team_id",
    how="left",
).merge(
    sprints[["sprint_id", "sprint_name"]],
    on="sprint_id",
    how="left",
)

reopened_view = reopened.merge(
    teams[["team_id", "team_name"]],
    on="team_id",
    how="left",
).merge(
    sprints[["sprint_id", "sprint_name"]],
    on="sprint_id",
    how="left",
)

left, right = st.columns(2)

with left:
    st.caption(
        "Tasks currently marked Blocked in the selected task records."
    )

    if blocked_view.empty:
        st.info("No blocked tasks are recorded for this selection.")
    else:
        blocked_chart = px.bar(
            blocked_view,
            x="team_name",
            y="blocked_tasks",
            color="sprint_name",
            barmode="group",
            title="Blocked tasks by team and sprint",
            labels={
                "team_name": "Team",
                "blocked_tasks": "Blocked tasks",
                "sprint_name": "Sprint",
            },
        )

        st.plotly_chart(
            blocked_chart,
            width="stretch",
        )

with right:
    st.caption(
        "Reopened tasks have one or more recorded reopen events."
    )

    if reopened_view.empty:
        st.info("No reopened tasks are recorded for this selection.")
    else:
        reopened_chart = px.bar(
            reopened_view,
            x="team_name",
            y="reopened_tasks",
            color="sprint_name",
            barmode="group",
            title="Reopened tasks by team and sprint",
            labels={
                "team_name": "Team",
                "reopened_tasks": "Reopened tasks",
                "sprint_name": "Sprint",
            },
        )

        st.plotly_chart(
            reopened_chart,
            width="stretch",
        )
# --------------------------------------------------
# Three key findings
# --------------------------------------------------

st.divider()
st.subheader("5. Key Findings")

finding_count = 0

# Finding 1: Team with the highest total completed story points
if not velocity.empty:
    team_velocity = velocity.groupby("team_id").agg(
        total_story_points=("velocity_story_points", "sum")
    ).reset_index()

    team_velocity = team_velocity.merge(
        teams[["team_id", "team_name"]],
        on="team_id",
        how="left",
    )

    if not team_velocity.empty:
        top_team = team_velocity.loc[
            team_velocity["total_story_points"].idxmax()
        ]

        st.markdown(
            f"**Finding 1 — Velocity:** "
            f"**{top_team['team_name']}** delivered the most completed "
            f"story points in the selected sprints: "
            f"**{top_team['total_story_points']:.0f} points**."
        )
        finding_count += 1

# Finding 2: Team with the highest average cycle time.
# Calculate from individual completed tasks so larger and smaller sprints
# are weighted by their actual number of tasks, not equally by sprint.
if not completed_tasks.empty:
    team_cycle = (
        completed_tasks.dropna(subset=["cycle_time_days"])
        .groupby("team_id", as_index=False)
        .agg(
            average_cycle_time_days=("cycle_time_days", "mean"),
            completed_tasks_with_cycle_time=("task_id", "nunique"),
        )
    )

    team_cycle = team_cycle.merge(
        teams[["team_id", "team_name"]],
        on="team_id",
        how="left",
    )

    if not team_cycle.empty:
        slowest_team = team_cycle.loc[
            team_cycle["average_cycle_time_days"].idxmax()
        ]

        st.markdown(
            f"**Finding 2 — Cycle time:** "
            f"**{slowest_team['team_name']}** had the highest average "
            f"cycle time across the selected sprints: "
            f"**{slowest_team['average_cycle_time_days']:.2f} days**."
        )
        finding_count += 1

# Finding 3: Team with the most blocked tasks
if not blocked.empty:
    team_blocked = blocked.groupby("team_id").agg(
        total_blocked_tasks=("blocked_tasks", "sum")
    ).reset_index()

    team_blocked = team_blocked.merge(
        teams[["team_id", "team_name"]],
        on="team_id",
        how="left",
    )

    if not team_blocked.empty:
        most_blocked_team = team_blocked.loc[
            team_blocked["total_blocked_tasks"].idxmax()
        ]

        st.markdown(
            f"**Finding 3 — Blocked work:** "
            f"**{most_blocked_team['team_name']}** had the most blocked "
            f"tasks in the selected sprints: "
            f"**{most_blocked_team['total_blocked_tasks']:.0f} tasks**."
        )
        finding_count += 1

if finding_count < 3:
    st.info(
        f"Only {finding_count} findings could be calculated. "
        "Select more teams or sprints to broaden the analysis."
    )

st.caption(
    "Findings update with the selected filters. High velocity alone "
    "does not necessarily indicate better team performance."
)