import streamlit as st
from google.oauth2 import service_account
from google.cloud import bigquery
import pandas as pd
import altair as alt
from datetime import datetime, timedelta, date

from data_sources import big_query
from dashboard_utils import gui


def monthly_downloads(start_date):
    df = big_query.get_data_frame_from_raw_sql(
        f"""
        SELECT
            date_trunc(date, MONTH) as date,
            project,
            SUM(downloads) as downloads
        FROM streamlit.streamlit.pypi_downloads
        WHERE date >= '{start_date}'
            AND project NOT IN ('shiny')
        GROUP BY 1,2
        ORDER BY 1,2 ASC
        """
    )

    # Percentage difference (between 0-1) of downloads of current vs previous month
    df["delta"] = (df.groupby(["project"])["downloads"].pct_change()).fillna(0)

    return df


def weekly_downloads(start_date):
    df = big_query.get_data_frame_from_raw_sql(
        f"""
        SELECT
            date_trunc(date, WEEK) as date,
            project,
            SUM(downloads) as downloads
        FROM streamlit.streamlit.pypi_downloads
        WHERE date >= '{start_date}'
            AND project NOT IN ('shiny')
        GROUP BY 1,2
        ORDER BY 1,2 ASC
        """
    )

    # Percentage difference (between 0-1) of downloads of current vs previous month
    df["delta"] = (df.groupby(["project"])["downloads"].pct_change()).fillna(0)

    return df


def plot_all_downloads(
    source, x="date", y="downloads", group="project", axis_scale="linear"
):

    if st.checkbox("View logarithmic scale"):
        axis_scale = "log"

    brush = alt.selection_interval(encodings=["x"], empty="all")

    click = alt.selection_multi(encodings=["color"])

    lines = (
        (
            alt.Chart(source)
            .mark_line(point=True)
            .encode(
                x=x,
                y=alt.Y("downloads", scale=alt.Scale(type=f"{axis_scale}")),
                color=group,
                tooltip=[
                    "date",
                    "project",
                    "downloads",
                    alt.Tooltip("delta", format=".2%"),
                ],
            )
        )
        .add_selection(brush)
        .properties(width=550)
        .transform_filter(click)
    )

    bars = (
        alt.Chart(source)
        .mark_bar()
        .encode(
            y=group,
            color=group,
            x=alt.X("downloads:Q", scale=alt.Scale(type=f"{axis_scale}")),
            tooltip=["date", "downloads", alt.Tooltip("delta", format=".2%")],
        )
        .transform_filter(brush)
        .properties(width=550)
        .add_selection(click)
    )

    return lines & bars


def plot_streamlit_downloads(source, x="date", y="downloads"):
    # Create a selection that chooses the nearest point & selects based on x-value
    hover = alt.selection_single(
        fields=[x],
        nearest=True,
        on="mouseover",
        empty="none",
    )

    lines = (
        alt.Chart(source)
        .mark_line(point="transparent")
        .encode(x=x, y=y)
        .transform_calculate(color='datum.delta < 0 ? "red" : "green"')
    )

    # Draw points on the line, highlight based on selection, color based on delta
    points = (
        lines.transform_filter(hover)
        .mark_circle(size=65)
        .encode(color=alt.Color("color:N", scale=None))
    )

    # Draw an invisible rule at the location of the selection
    tooltips = (
        alt.Chart(source)
        .mark_rule(opacity=0)
        .encode(
            x=x,
            y=y,
            tooltip=[x, y, alt.Tooltip("delta", format=".2%")],
        )
        .add_selection(hover)
    )

    return (lines + points + tooltips).interactive()


def main():

    # Note that page title/favicon are set in the __main__ clause below,
    # so they can also be set through the mega multipage app (see ../streamlit_app.py).

    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input(
            "Select start date",
            date(2020, 1, 1),
            min_value=datetime.strptime("2020-01-01", "%Y-%m-%d"),
            max_value=datetime.now(),
        )

    with col2:
        time_frame = st.selectbox(
            "Select weekly or monthly downloads", ("weekly", "monthly")
        )

    # PREPARING DATA FOR WEEKLY AND MONTHLY

    df_monthly = monthly_downloads(start_date)
    df_weekly = weekly_downloads(start_date)

    streamlit_data_monthly = df_monthly[df_monthly["project"] == "streamlit"]
    streamlit_data_weekly = df_weekly[df_weekly["project"] == "streamlit"]

    package_names = df_monthly["project"].drop_duplicates()

    if time_frame == "weekly":
        selected_data_streamlit = streamlit_data_weekly
        selected_data_all = df_weekly
    else:
        selected_data_streamlit = streamlit_data_monthly
        selected_data_all = df_monthly

    ## STREAMLIT DOWNLOADS

    st.header("Streamlit downloads")

    st.altair_chart(
        plot_streamlit_downloads(selected_data_streamlit), use_container_width=True
    )

    # OTHER DOWNLOADS

    st.header("Compare other package downloads")

    instructions = """
    Click and drag line chart to select and pan date interval\n
    Hover over bar chart to view downloads\n
    Click on a bar to highlight that package
    """
    select_packages = st.multiselect(
        "Select Python packages to compare",
        package_names,
        default=["streamlit", "dash", "panel", "voila"],
        help=instructions,
    )

    select_packages_df = pd.DataFrame(select_packages).rename(columns={0: "project"})

    if not select_packages:
        st.stop()

    filtered_df = selected_data_all[
        selected_data_all["project"].isin(select_packages_df["project"])
    ]

    st.altair_chart(plot_all_downloads(filtered_df), use_container_width=True)


gui.icon("⬇️")
st.title("Downloads")
st.write(
    "Metrics on how often Streamlit is being downloaded from PyPI (Python's main "
    "package repository, i.e. where `pip install streamlit` downloads the package from)."
)
main()
