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

#Streamlit page configuration
st.set_page_config(page_title="CEIC Series Data Visualizer", layout="wide")

def initialize_session_state():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'ceic_client' not in st.session_state:
        st.session_state.ceic_client = None
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
        # Ensure a key exists before accessing it
        if list(options.keys()):
             selected_option = st.selectbox(f"Select an option ({json_file.replace('_data.json', '')}):", list(options.keys()))
             selected_values[json_file] = options[selected_option]
        else:
             st.warning(f"No options found in {json_file}")
             selected_values[json_file] = None # Or handle appropriately

    return selected_values


def search_series(keyword, dropdown):
    # Use the client from session state
    ceic_client = st.session_state.ceic_client

    if not ceic_client:
        st.error("CEIC client not initialized.")
        return

    #Search series using keyword and dropdown parameters
    frequency_id = dropdown.get("frequencies_data.json")
    geo_id = dropdown.get("geo_data.json")
    status_id = dropdown.get("statuses_data.json")

    # Check if required dropdown values were selected
    if frequency_id is None or geo_id is None or status_id is None:
        st.warning("Please ensure all dropdowns have valid selections.")
        return

    search_params = {
        "keyword": keyword,
        "frequency": [frequency_id],
        "geo": [geo_id],
        "status": [status_id],
        "with_vintage_enabled_only": "TRUE"
    }
    
    try:
        search_results = ceic_client.search(**search_params)
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
                st.error("No results found for the given criteria.")
                st.session_state.series_options = {} # Clear previous results if any
                st.session_state.series_id = None
        else:
            st.error("Search returned no results.")
            st.session_state.series_options = {} # Clear previous results
            st.session_state.series_id = None

    except Exception as e:
        st.error(f"An error occurred during search: {e}")
        st.session_state.series_options = {} # Clear previous results
        st.session_state.series_id = None


def display_series_options():
    # Dropdown to select founded series
    if st.session_state.series_options:
        # Get the current selected key or the first key if not set
        current_key = next(iter(st.session_state.series_options.keys()), None)
        if 'selected_series_key' in st.session_state and st.session_state.selected_series_key in st.session_state.series_options:
            current_key = st.session_state.selected_series_key
        elif list(st.session_state.series_options.keys()):
            current_key = list(st.session_state.series_options.keys())[0]

        if current_key:
            selected_series = st.selectbox(
                "Select a series:",
                options=list(st.session_state.series_options.keys()),
                index=list(st.session_state.series_options.keys()).index(current_key),
                key='selected_series_key' # Use a consistent key for the selectbox
            )
            st.session_state.series_id = st.session_state.series_options[selected_series]
        else:
            st.warning("Search for series to populate this list.")
            st.session_state.series_id = None

    else:
        st.warning("Search for series to populate this list.")
        st.session_state.series_id = None


def display_visualizations():

    # Use the client from session state
    ceic_client = st.session_state.ceic_client

    if not ceic_client:
        st.error("CEIC client not initialized.")
        return

    if st.session_state.series_id is None:
        st.error("No series selected. Please select a series from the dropdown.")
        return

    # Pass the client object to the Visualizer
    visualizer = SeriesVisualizer(ceic_client, st.session_state.series_id)
    with st.spinner("Fetching data..."):
        visualizer.fetch_all_data()
    
    # Check for errors during fetching
    if visualizer.metadata is None or visualizer.series_data is None or visualizer.df_reversed is None:
         st.error("Failed to fetch all necessary data for visualizations. Please try a different series or check API connectivity.")
         # Optionally display what *was* fetched if anything
         if visualizer.metadata: st.write("Metadata fetched.")
         if visualizer.series_data: st.write("Series data fetched.")
         if visualizer.df_reversed is not None: st.write("Vintages data fetched.")
         return

    #Time series data
    st.subheader("Time Series Data")
    df_series = visualizer.process_series_data()
    if df_series is not None:
        fig = visualizer.plot_series(df_series)
        if fig:
            st.plotly_chart(fig)
        else:
            st.error("Failed to plot series data.") # Should not happen if df_series is not None and data is valid
    else:
        st.error("Failed to process series data.")

    # Vintages Table
    st.subheader("Vintages Table with Highlights")
    df_styled = visualizer.style_vintages_table()
    if df_styled is not None:
         st.dataframe(df_styled)
    else:
         st.error("Failed to style vintages table.") # Should not happen if df_reversed is not None

    # Vintages Heatmap
    st.subheader("Heatmap of Vintage Changes")
    fig_heatmap = visualizer.plot_vintages_heatmap()
    if fig_heatmap:
        st.pyplot(fig_heatmap)
    else:
         st.error("Failed to plot vintages heatmap.") # Should not happen if df_reversed is not None

    #Animated Timeseries Vintages
    st.subheader("Animated Timeseries Vintages")
    fig_animated = visualizer.plot_animated_vintages()
    if fig_animated:
        st.plotly_chart(fig_animated)
    else:
         st.error("Failed to plot animated vintages.") # Should not happen if df_reversed is not None
    
    # Vintage comparison Between dates
    st.subheader("Vintage Comparison Between Two Dates")
    fig_comparison = visualizer.plot_vintage_comparison()
    if fig_comparison:
        st.plotly_chart(fig_comparison)
    else:
         st.error("Failed to plot vintage comparison.") # Should not happen if df_reversed is not None

    # Difference between first and last
    st.subheader("Difference Between Last and First Available Values per Vintage")
    fig_bar = visualizer.plot_vintage_differences()
    if fig_bar:
        st.pyplot(fig_bar)
    else:
         st.error("Failed to plot vintage differences.") # Should not happen if df_reversed is not None

def login_page():
    st.title("CEIC Data Visualizer Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if not username or not password:
            st.warning("Please enter both username and password.")
            return

        with st.spinner("Logging in..."):
            try:
                # Attempt to login to CEIC
                client = Ceic.login(username, password)
                st.session_state.ceic_client = client
                st.session_state.logged_in = True
                st.success("Login successful!")
                # Rerun to switch to the main app view
                st.rerun()
            except Exception as e:
                st.error(f"Login failed: {e}")
                st.session_state.logged_in = False
                st.session_state.ceic_client = None


def main_app():
    # Title
    st.title("CEIC Series Data Visualizer")

    # Sidebar
    with st.sidebar:
        st.title("Filters")
        keyword = st.text_input("Keyword")
        dropdown = load_json_dropdown(JSON_FILES) # Make sure JSON files exist

        # Check if dropdown values are valid before enabling search
        dropdown_valid = all(value is not None for value in dropdown.values())
        search_button = st.button("Search Series", disabled=not dropdown_valid)

    # Search function with keyword
    if search_button and keyword and dropdown_valid:
        search_series(keyword, dropdown)

    # Series list dropdown
    display_series_options()

    # Load button
    load_data = st.button("Load Data", disabled=not st.session_state.series_options)

    # Load data with selected Series id
    if st.session_state.series_id and load_data:
        display_visualizations()
    elif load_data and st.session_state.series_id is None:
        st.warning("Please select a series before loading data.")


def main():
    initialize_session_state()

    if st.session_state.logged_in:
        main_app()
    else:
        login_page()


if __name__ == '__main__':
    # Make sure JSON files are present (simple check)
    for fname in JSON_FILES:
        if not os.path.exists(fname):
            st.error(f"Required file '{fname}' not found. Please ensure the JSON files are in the same directory as app.py.")
            st.stop() # Stop execution if files are missing

    main()