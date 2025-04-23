import streamlit as st
from series import SeriesVisualizer
import plotly.express as px
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from ceic_api_client.pyceic import Ceic
import os
import json

#CONSTANTS
JSON_FILES = ["geo_data.json", "frequencies_data.json", "statuses_data.json"]
USERNAME = os.environ.get("CEIC_USERNAME")
PASSWORD = os.environ.get("CEIC_PASSWORD")
CEIC_CLIENT = Ceic.login(USERNAME, PASSWORD) 

#Streamlit page configuration
st.set_page_config(page_title="CEIC Series Data Visualizer", layout="wide")

def initialize_session_state():
    if 'series_id' not in st.session_state:
        st.session_state.series_id = None
    if 'series_options' not in st.session_state:
        st.session_state.series_options = {}


def load_json_dropdown(json_files):
    
    #Read the json files specified to get the values to load in the dropdown menu
    selected_values = {}
    for json_file in json_files:
        with open(json_file, "r", encoding="utf-8") as file:
            data = json.load(file)
        # Filter just countries to avoid fetching wrong ids in geo response
        if json_file == "geo_data.json":
            data = [item for item in data if item.get("type") == "COUNTRY"]

        # key is "name" or "title" in case of the  geo_data 
        key_name = "name" if "name" in data[0] else "title"
        options = {item[key_name]: item["id"] for item in data}
        
        # Dropdown options
        selected_option = st.selectbox(f"Select an option ({json_file}):", list(options.keys()))
        selected_values[json_file] = options[selected_option]
        
    return selected_values


def search_series(keyword, dropdown):
    #Search series using keyword and dropdown parameters
    frequency_id = dropdown["frequencies_data.json"]
    geo_id = dropdown["geo_data.json"]
    status_id = dropdown["statuses_data.json"]

    search_params = {
        "keyword": keyword,
        "frequency": [frequency_id],
        "geo": [geo_id],
        "status": [status_id],
        "with_vintage_enabled_only": "TRUE"
    }
    
    search_results = CEIC_CLIENT.search(**search_params)
    series_options = {}

    if search_results:
        #Search trough all the results pages
        for result_page in search_results:
            if hasattr(result_page, 'data') and hasattr(result_page.data, 'items'):
                for series in result_page.data.items:
                    name = series.metadata.name
                    series_id = series.metadata.id
                    label = f"{name} (ID: {series_id})"
                    series_options[label] = series_id
        #Updates the session_state
        if series_options:
            st.session_state.series_options = series_options
        else:
            st.error("No results found.")
    else:
        st.error("Search failed.")


def display_series_options():
    # Dropdown to selct founded series
    if st.session_state.series_options:
        selected_series = st.selectbox(
            "Select a series:",
            options=list(st.session_state.series_options.keys()),
            index=0
        )
        st.session_state.series_id = st.session_state.series_options[selected_series]
    else:
        st.warning("Search for series to populate this list.")


def display_visualizations():

    visualizer = SeriesVisualizer(CEIC_CLIENT, st.session_state.series_id)
    with st.spinner("Fetching data..."):
        visualizer.fetch_all_data()
    
    if visualizer.metadata is None:
        st.error("No metadata found for the provided series ID.")
        return

    #Time series data
    st.subheader("Time Series Data")
    df_series = visualizer.process_series_data()
    if df_series is not None:
        fig = visualizer.plot_series(df_series)
        if fig:
            st.plotly_chart(fig)
    else:
        st.error("Failed to fetch series data.")

    # Vintages Table
    st.subheader("Vintages Table with Highlights")
    df_styled = visualizer.style_vintages_table()
    st.dataframe(df_styled)
    
    # Vintages Heatmap
    st.subheader("Heatmap of Vintage Changes")
    fig_heatmap = visualizer.plot_vintages_heatmap()
    if fig_heatmap:
        st.pyplot(fig_heatmap)
    
    #Animated Timeseries Vintages
    st.subheader("Animated Timeseries Vintages")
    fig_animated = visualizer.plot_animated_vintages()
    if fig_animated:
        st.plotly_chart(fig_animated)
    
    # Vintage comparison Between dates
    st.subheader("Vintage Comparison Between Two Dates")
    fig_comparison = visualizer.plot_vintage_comparison()
    if fig_comparison:
        st.plotly_chart(fig_comparison)
    
    # Difference between first and last
    st.subheader("Difference Between Last and First Available Values per Vintage")
    fig_bar = visualizer.plot_vintage_differences()
    if fig_bar:
        st.pyplot(fig_bar)



def main():

    initialize_session_state()

    # Sidebar
    with st.sidebar:
        st.title("Filters")
        keyword = st.text_input("Keyword")
        dropdown = load_json_dropdown(JSON_FILES)
        search_button = st.button("Search Series")

    # Load button
    load_data = st.button("Load Data")

    # Search function with keyword
    if search_button and keyword:
        search_series(keyword, dropdown)

    # Series list dropdown
    display_series_options()

    # Title
    st.title("CEIC Series Data Visualizer")

    # Load data with selected Series id
    if st.session_state.series_id and load_data:
        display_visualizations()


if __name__ == '__main__':
    main()