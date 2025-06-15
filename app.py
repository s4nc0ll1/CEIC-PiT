import io
import streamlit as st
from series import SeriesVisualizer
import plotly.express as px
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from ceic_api_client.pyceic import Ceic
import os
import json
import sys
import re 
from PIL import Image
import base64
from script_generator import generate_python_script
from translations import TRANSLATIONS 

#CONSTANTS
FILTERS_DIR = "filters"
JSON_FILES = ["geo_data.json", "frequencies_data.json", "statuses_data.json"]
LABEL_MAP = {
    "geo_data.json": "Country", # These values will be used as keys for translation
    "frequencies_data.json": "Frequency",
    "statuses_data.json": "Status"
}

# Streamlit page configuration is set in main() after language initialization

def initialize_session_state():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'ceic_client' not in st.session_state:
        st.session_state.ceic_client = None
    if 'series_id_for_viz' not in st.session_state:
         st.session_state.series_id_for_viz = None
    if 'series_options' not in st.session_state:
        st.session_state.series_options = {}
    if 'selected_series_key' not in st.session_state:
        st.session_state.selected_series_key = None
    
    if 'visualizer_object' not in st.session_state:
        st.session_state.visualizer_object = None
    if 'plots_generated' not in st.session_state:
        st.session_state.plots_generated = False
    if 'cached_plots' not in st.session_state:
        st.session_state.cached_plots = {}
    if 'search_or_load_attempted' not in st.session_state:
        st.session_state.search_or_load_attempted = False
    
    if 'language' not in st.session_state: # Initialize language
        st.session_state.language = "EN"
    if 'page_config_set' not in st.session_state: # To ensure page_config is set only once
        st.session_state.page_config_set = False


# Translation helper function
def get_translation(key, *args): # Renamed from _
    lang = st.session_state.get('language', "EN")
    # Fallback to English if a key is missing in the current language, then to the key itself
    translation = TRANSLATIONS.get(lang, {}).get(key, TRANSLATIONS.get("EN", {}).get(key, key))
    if args:
        try:
            return translation.format(*args)
        except (KeyError, IndexError): # Handle cases where format specifiers don't match args
            return key # Fallback to key if formatting fails
    return translation

# Helper function to load JSON data safely
@st.cache_data(show_spinner=False)
def load_json_data(json_file):
    try:
        with open(json_file, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data
    except FileNotFoundError:
        st.error(get_translation("Error: Required file '{}' not found.", json_file))
        st.stop()
        return None 
    except json.JSONDecodeError:
        st.error(get_translation("Error: Could not decode JSON from '{}'. Please check the file content.", json_file))
        st.stop()
        return None 
    except Exception as e:
        st.error(get_translation("An unexpected error occurred loading '{}': {}", json_file, e))
        st.stop()
        return None 

def load_json_dropdown(json_files):
    selected_values = {}
    for json_file in json_files:
        full_path = os.path.join(FILTERS_DIR, json_file)
        data = load_json_data(full_path) 

        if not data:
             st.warning(get_translation("No options found or loaded from {}", full_path))
             selected_values[json_file] = None
             continue 

        if json_file == "geo_data.json":
            if isinstance(data, list):
                data = [item for item in data if item.get("type") == "COUNTRY"]
            else:
                 st.warning(get_translation("Unexpected data format in {}", full_path))
                 selected_values[json_file] = None
                 continue

        if not isinstance(data, list) or not data:
             st.warning(get_translation("No valid options found in {}", full_path))
             selected_values[json_file] = None
             continue

        first_item = data[0]
        key_name = None
        if "name" in first_item:
            key_name = "name"
        elif "title" in first_item:
            key_name = "title"
        else:
             st.warning(get_translation("Could not find 'name' or 'title' key in the first item of {}", full_path))
             selected_values[json_file] = None
             continue

        if "id" not in first_item:
            st.warning(get_translation("Could not find 'id' key in the first item of {}", full_path))
            selected_values[json_file] = None
            continue

        options = {item[key_name]: item["id"] for item in data if key_name in item and "id" in item}

        if not options:
             st.warning(get_translation("Failed to extract valid options from {}", full_path))
             selected_values[json_file] = None
             continue

        label_key = LABEL_MAP.get(json_file, json_file.replace('_data.json', '').capitalize())
        translated_label_value = get_translation(label_key) # Translate "Country", "Frequency", "Status"

        selectbox_key = f"selectbox_{json_file.replace('_data.json', '')}"
        selected_option = st.selectbox(get_translation("Select {}:", translated_label_value), list(options.keys()), key=selectbox_key)
        selected_values[json_file] = options[selected_option]

    return selected_values

def load_series_by_id(series_id_str):
    if not series_id_str:
        st.warning(get_translation("Please enter a Series ID to load."))
        st.session_state.series_options = {}
        st.session_state.series_id_for_viz = None
        st.session_state.selected_series_key = None
        return

    if not re.match(r'^[0-9]+$', series_id_str) and not series_id_str.startswith('SR'):
         st.warning(get_translation("Invalid Series ID format: '{}'. Please enter a numeric ID or an SR code.", series_id_str))
         st.session_state.series_options = {}
         st.session_state.series_id_for_viz = None
         st.session_state.selected_series_key = None
         return

    ceic_client = st.session_state.ceic_client
    if not ceic_client:
        st.error(get_translation("CEIC client not initialized."))
        return

    with st.spinner(get_translation("Loading Series ID {}...", series_id_str)):
        try:
            result = ceic_client.series_metadata(series_id=series_id_str)
            if result and hasattr(result, 'data') and result.data:
                series_info = result.data[0] 
                if hasattr(series_info, 'metadata') and hasattr(series_info.metadata, 'id'):
                    series_id = series_info.metadata.id 
                    name = getattr(series_info.metadata, 'name', 'Unnamed Series') 
                    label = f"{name} (ID: {series_id})"
                    st.session_state.series_options = {label: series_id}
                    st.session_state.series_id_for_viz = series_id
                    st.session_state.selected_series_key = label
                    st.success(get_translation("Successfully loaded Series ID {}.", series_id))
                    st.session_state.search_or_load_attempted = False 
                else:
                     st.error(get_translation("Could not retrieve metadata for Series ID {}. Please check the ID.", series_id_str))
                     st.session_state.series_options = {}
                     st.session_state.series_id_for_viz = None
                     st.session_state.selected_series_key = None
            else:
                st.error(get_translation("Series ID {} not found or accessible.", series_id_str))
                st.session_state.series_options = {}
                st.session_state.series_id_for_viz = None
                st.session_state.selected_series_key = None
        except Exception as e:
            st.error(get_translation("An error occurred loading Series ID {}: {}", series_id_str, e))
            st.session_state.series_options = {}
            st.session_state.series_id_for_viz = None
            st.session_state.selected_series_key = None


def search_series(keyword, dropdown):
    ceic_client = st.session_state.ceic_client
    if not ceic_client:
        st.error(get_translation("CEIC client not initialized."))
        return

    if not keyword:
        st.warning(get_translation("Please enter a keyword to search."))
        st.session_state.series_options = {}
        st.session_state.series_id_for_viz = None
        st.session_state.selected_series_key = None
        return

    frequency_id = dropdown.get("frequencies_data.json")
    geo_id = dropdown.get("geo_data.json")
    status_id = dropdown.get("statuses_data.json")

    if frequency_id is None or geo_id is None or status_id is None:
         st.warning(get_translation("Please ensure Frequency, Geo, and Status are selected for keyword search."))
         st.session_state.series_options = {}
         st.session_state.series_id_for_viz = None
         st.session_state.selected_series_key = None
         return

    search_params = {
        "keyword": keyword,
        "frequency": [frequency_id], 
        "geo": [geo_id],           
        "status": [status_id],       
        "with_vintage_enabled_only": "TRUE"
    }

    st.session_state.series_options = {}
    st.session_state.series_id_for_viz = None
    st.session_state.selected_series_key = None

    with st.spinner(get_translation("Searching for '{}' with filters...", keyword)):
        try:
            search_results_list = list(ceic_client.search(**search_params))
            series_options = {}
            if search_results_list:
                for result_page in search_results_list:
                    if hasattr(result_page, 'data') and hasattr(result_page.data, 'items'):
                        for series in result_page.data.items:
                            if hasattr(series, 'metadata') and hasattr(series.metadata, 'name') and hasattr(series.metadata, 'id'):
                                name = series.metadata.name
                                series_id = series.metadata.id
                                label = f"{name} (ID: {series_id})"
                                series_options[label] = series_id
                if series_options:
                    st.session_state.series_options = series_options
                    first_key = list(series_options.keys())[0]
                    st.session_state.series_id_for_viz = series_options[first_key]
                    st.session_state.selected_series_key = first_key
                    st.info(get_translation("Found {} series.", len(series_options)))
                    st.session_state.search_or_load_attempted = False 
                else:
                    st.error(get_translation("No results found for the given criteria."))
            else:
                st.error(get_translation("Search returned no results."))
        except Exception as e:
            st.error(get_translation("An error occurred during search: {}", e))


def display_series_selection():
    if st.session_state.series_options:
        total_series = len(st.session_state.series_options)
        st.subheader(get_translation("Select Series"))
        
        # Add info message with total series found
        st.info(get_translation("Found {} series matching your criteria.", total_series))
        
        options_keys = list(st.session_state.series_options.keys())
        default_index = 0
        if st.session_state.selected_series_key in options_keys:
            default_index = options_keys.index(st.session_state.selected_series_key)
        elif options_keys:
            st.session_state.selected_series_key = options_keys[0]
            st.session_state.series_id_for_viz = st.session_state.series_options[st.session_state.selected_series_key]
        
        selected_key_on_change = st.session_state.selected_series_key 
        
        selected_key = st.selectbox(
            get_translation("Choose a series:"),
            options=options_keys,
            index=default_index,
            key='series_selection_dropdown_main' 
        )

        if selected_key != selected_key_on_change: 
            st.session_state.series_id_for_viz = st.session_state.series_options[selected_key]
            st.session_state.selected_series_key = selected_key
            st.session_state.visualizer_object = None
            st.session_state.plots_generated = False
            st.session_state.cached_plots = {}
            st.rerun() 

    else: 
        if st.session_state.get('search_or_load_attempted', False):
            st.warning(get_translation("No series found from your recent search or load attempt. Please try different criteria or ID."))
        else:
            st.info(get_translation("Load a series by ID or perform a search to see options here."))
        
        st.session_state.series_id_for_viz = None 
        st.session_state.selected_series_key = None

def display_visualizations(force_reload=False):
    series_id_to_visualize = st.session_state.series_id_for_viz
    ceic_client = st.session_state.ceic_client

    if not series_id_to_visualize:
        st.error(get_translation("No series selected or loaded. Please load a series first."))
        st.session_state.plots_generated = False
        return

    if not ceic_client:
        st.error(get_translation("CEIC client not initialized."))
        st.session_state.plots_generated = False
        return

    visualizer = st.session_state.get('visualizer_object')

    if force_reload or visualizer is None or visualizer.series_id != series_id_to_visualize:
        st.subheader(f"{get_translation('Visualizing Series ID:')} {series_id_to_visualize}")
        current_visualizer = SeriesVisualizer(ceic_client, series_id_to_visualize)
        with st.spinner(get_translation("Fetching data for Series ID {}...", series_id_to_visualize)):
            current_visualizer.fetch_all_data()
        st.session_state.visualizer_object = current_visualizer
        visualizer = current_visualizer
        st.session_state.cached_plots = {} 
        st.session_state.plots_generated = False 
    
    if not visualizer:
        st.error(get_translation("Internal error: Visualizer not available.")) 
        return

    if visualizer.metadata:
        st.subheader(get_translation("Series Metadata"))
        meta = visualizer.metadata
        st.write(f"**{get_translation('ID:')}** {getattr(meta, 'id', 'N/A')}")
        st.write(f"**{get_translation('Name:')}** {getattr(meta, 'name', 'N/A')}")
        country_name = getattr(getattr(meta, 'country', None), 'name', 'N/A')
        st.write(f"**{get_translation('Country:')}** {country_name}") 
        frequency_name = getattr(getattr(meta, 'frequency', None), 'name', 'N/A')
        st.write(f"**{get_translation('Frequency:')}** {frequency_name}") 
        source_name = getattr(getattr(meta, 'source', None), 'name', 'N/A')
        st.write(f"**{get_translation('Source:')}** {source_name}")
        st.write(f"**{get_translation('Last Update Time:')}** {getattr(meta, 'last_update_time', 'N/A')}")
        st.write(f"**{get_translation('Last Value:')}** {getattr(meta, 'last_value', 'N/A')}")
        st.markdown("---")
    else:
        if force_reload : 
            st.error(get_translation("Failed to fetch metadata for Series ID {}. Visualizations cannot be displayed.", series_id_to_visualize))
        st.session_state.plots_generated = False 
        return

    cached_plots = st.session_state.get('cached_plots', {})
    made_new_plots_this_run = False 

    def manage_plot(plot_key, generation_func, *args):
        nonlocal made_new_plots_this_run
        if force_reload or plot_key not in cached_plots:
            try:
                plot_obj = generation_func(*args)
                cached_plots[plot_key] = plot_obj
                made_new_plots_this_run = True
                return plot_obj
            except Exception as e:
                st.error(get_translation("Error generating plot {}: {}", plot_key, e))
                cached_plots[plot_key] = None 
                return None
        return cached_plots.get(plot_key)

    if visualizer.series_data:
        st.subheader(get_translation("Revised Time Series data"))
        st.markdown(get_translation("The CEIC API allows you to access the normal up-to-date version of the series with the latest revisions applied to the selected economic variable."))
        df_series = visualizer.process_series_data()
        if df_series is not None and not df_series.empty:
            fig_series = manage_plot('series_plot', visualizer.plot_series, df_series)
            if fig_series: st.plotly_chart(fig_series, use_container_width=True)
        elif df_series is not None and df_series.empty:
            st.info(get_translation("No time series data points found for this series."))
        else: 
            st.error(get_translation("Failed to process series data."))
    else:
        st.info(get_translation("Time series data (latest revisions) not available for this series."))
    st.markdown("<br><br>", unsafe_allow_html=True)

    if visualizer.df_reversed is not None:
        st.subheader(get_translation("Vintages Matrix"))
        st.markdown(get_translation("The dataframe represents the latest vintages showing timepoint dates as rows and update_dates as columns. Timepoint changes (revisions) are highlighted in light purple"))
        df_styled = visualizer.style_vintages_table() 
        if df_styled: st.dataframe(df_styled)
        else: st.error(get_translation("Failed to style vintages table."))
        st.markdown("<br><br>", unsafe_allow_html=True)

        st.subheader(get_translation("Heatmap of Vintage Changes"))
        fig_heatmap = manage_plot('heatmap_plot', visualizer.plot_vintages_heatmap)
        if fig_heatmap: st.pyplot(fig_heatmap)
        st.markdown("<br><br>", unsafe_allow_html=True)

        st.subheader(get_translation("Animated Timeseries Vintages"))
        fig_animated = manage_plot('animated_vintages_plot', visualizer.plot_animated_vintages)
        if fig_animated: st.plotly_chart(fig_animated, use_container_width=True)
        st.markdown("<br><br>", unsafe_allow_html=True)

        st.subheader(get_translation("Vintage Comparison Between Two Dates"))
    
        # Get available dates from vintages data
        available_dates = visualizer.df_reversed.columns.strftime('%Y-%m-%d').tolist()
        
        # Create session state keys for selected dates
        key_prefix = f"vintage_dates_{st.session_state.series_id_for_viz}"
        date1_key = f"{key_prefix}_date1"
        date2_key = f"{key_prefix}_date2"
        
        # Initialize session state for dates
        if date1_key not in st.session_state:
            st.session_state[date1_key] = available_dates[0] if available_dates else None
        if date2_key not in st.session_state:
            st.session_state[date2_key] = available_dates[1] if len(available_dates) > 1 else None
        
        # Use columns for layout
        col1, col2 = st.columns(2)
        
        with col1:
            # Get current date1 from session state
            current_date1 = st.session_state[date1_key]
            # Create selectbox that updates session state directly
            new_date1 = st.selectbox(
                get_translation("Select First Date"),
                options=available_dates,
                index=available_dates.index(current_date1) if current_date1 in available_dates else 0,
                key=f"{key_prefix}_select1"
            )
            # Update session state immediately if changed
            if new_date1 != current_date1:
                st.session_state[date1_key] = new_date1
                # Force rerun to apply changes immediately
                st.rerun()
        
        with col2:
            # Get current date2 from session state
            current_date2 = st.session_state[date2_key]
            # Create selectbox that updates session state directly
            new_date2 = st.selectbox(
                get_translation("Select Second Date"),
                options=available_dates,
                index=available_dates.index(current_date2) if current_date2 in available_dates else 0,
                key=f"{key_prefix}_select2"
            )
            # Update session state immediately if changed
            if new_date2 != current_date2:
                st.session_state[date2_key] = new_date2
                # Force rerun to apply changes immediately
                st.rerun()
        
        # Generate plot with selected dates
        fig_comparison = manage_plot(
            f'vintage_comparison_plot_{st.session_state[date1_key]}_{st.session_state[date2_key]}', 
            visualizer.plot_vintage_comparison, 
            st.session_state[date1_key],
            st.session_state[date2_key]
        )
        
        if fig_comparison: 
            st.plotly_chart(fig_comparison, use_container_width=True)
        else:
            st.error(get_translation("Could not generate comparison for selected dates."))
        
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.subheader(get_translation("Difference Between Last and First Available Values per Vintage"))
        fig_bar = manage_plot('vintage_differences_plot', visualizer.plot_vintage_differences)
        if fig_bar: st.pyplot(fig_bar)
    else:
        st.info(get_translation("Vintages data not available for this series."))

    if made_new_plots_this_run or force_reload:
        st.session_state.cached_plots = cached_plots
    
    if visualizer.metadata: 
        st.session_state.plots_generated = True
    
    plt.close('all')


def login_page():

    col1, col2, col3 = st.columns([2, 1, 2])
    with col2:
        st.image("images/ceic.webp", width=250)

    col1, col2, col3 = st.columns([2.5, 3.5, 2])
    with col2:
        st.title("Point-in-Time Data Explorer") 
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("Username") 
        password = st.text_input("Password", type="password") 
        if st.button("Login"): 
            if not username or not password:
                st.warning("Please enter both username and password.") 
                return
            with st.spinner("Logging in..."): 
                try:
                    client = Ceic.login(username, password)
                    st.session_state.ceic_client = client
                    st.session_state.logged_in = True
                    st.success("Login successful!") 
                    st.rerun()
                except Exception as e:
                    # Keep error message in English for consistency on login page
                    st.error(f"Login failed: {e}. Please check your credentials and API server configuration.") 
                    st.session_state.logged_in = False
                    st.session_state.ceic_client = None


def display_code_export_buttons_sidebar():
    st.sidebar.markdown("---")
    st.sidebar.subheader(get_translation("View Code Examples"))
    
    current_series_id = st.session_state.get('series_id_for_viz')
    python_script_content = generate_python_script(str(current_series_id) if current_series_id else None)
    file_name_py = f"ceic_visualize_series_{current_series_id}.py" if current_series_id else "ceic_visualize_series_generic.py"

    if "ERROR: The file 'series.py' was not found" in python_script_content:
        st.sidebar.error(get_translation("Could not generate Python script: 'series.py' is missing."))
        st.sidebar.button(get_translation("Python Script"), key="python_script_btn_disabled_sidebar", disabled=True)
    else:
        # Load and encode Python logo
        python_logo = Image.open("images/python-logo.png")
        python_logo = python_logo.resize((20, 20))  # Resize to fit in button
        
        # Convert to base64 for embedding
        buffered = io.BytesIO()
        python_logo.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        img_html = f'<img src="data:image/png;base64,{img_str}" style="vertical-align: middle; margin-right: 8px;">'
        
        # Create download button with logo
        st.sidebar.markdown(
            f'<a href="data:text/plain;base64,{base64.b64encode(python_script_content.encode()).decode()}" '
            f'download="{file_name_py}" style="text-decoration: none;">'
            f'<button style="border: 1px solid #e0e0e0; color: black; padding: 10px 20px; '
            f'text-align: center; text-decoration: none; display: inline-block; font-size: 16px; '
            f'margin: 4px 2px; cursor: pointer; border-radius: 4px;">'
            f'{img_html}'
            f'{get_translation("Download Python Script")}'
            f'</button></a>',
            unsafe_allow_html=True
        )
        
        with st.sidebar.expander(get_translation("View Generated Python Script")):
            st.code(python_script_content, language="python")

def main_app():
    _, _, lang_col1, lang_col2 = st.columns([0.7, 0.1, 0.1, 0.1]) 
    with lang_col1:
        if st.button("EN", key="main_lang_en", use_container_width=True):
            if st.session_state.language != "EN":
                st.session_state.language = "EN"
                st.rerun()
    with lang_col2:
        if st.button("中文", key="main_lang_cn", use_container_width=True):
            if st.session_state.language != "CN":
                st.session_state.language = "CN"
                st.rerun()

    st.title(get_translation("CEIC Point-in-Time Data Explorer"))

    with st.sidebar:
        st.image("images/ceic.webp", width=250)
        st.title(get_translation("Data Loading Options"))
        st.subheader(get_translation("Load by Series ID"))
        direct_series_id_input = st.text_input(get_translation("Enter Series ID"), key="direct_id_input_sidebar").strip()
        load_id_button = st.button(get_translation("Load by ID"), disabled=not direct_series_id_input, key="load_id_btn")

        st.markdown("---")
        st.subheader(get_translation("Search by Filters"))
        keyword = st.text_input(get_translation("Keyword for Search"), key="keyword_input_sidebar")
        dropdown = load_json_dropdown(JSON_FILES) 
        dropdown_valid = all(value is not None for value in dropdown.values())
        search_button_disabled = not (keyword and dropdown_valid)
        search_button = st.button(get_translation("Search by Filters"), disabled=search_button_disabled, key="search_filters_btn")
        
        # Display code export buttons in the sidebar
        display_code_export_buttons_sidebar()


    if load_id_button:
        st.session_state.search_or_load_attempted = True 
        load_series_by_id(direct_series_id_input)
        st.session_state.visualizer_object = None 
        st.session_state.plots_generated = False
        st.session_state.cached_plots = {}
        # If a series ID was successfully loaded, series_id_for_viz will be set
        # The script generator will pick this up if display_code_export_buttons_sidebar is called after st.rerun()
        st.rerun() 

    if search_button:
        st.session_state.search_or_load_attempted = True 
        search_series(keyword, dropdown)
        st.session_state.visualizer_object = None 
        st.session_state.plots_generated = False
        st.session_state.cached_plots = {}
        # If search was successful, series_id_for_viz will be set
        st.rerun()

    display_series_selection()

    load_data_disabled = not st.session_state.series_id_for_viz
    load_data_button = st.button(get_translation("Load Data & Visualize"), disabled=load_data_disabled, key="load_data_visualize_btn")

    if load_data_button:
        display_visualizations(force_reload=True)
    elif st.session_state.get('plots_generated', False) and st.session_state.get('visualizer_object') is not None:
        display_visualizations(force_reload=False)


def main():
    initialize_session_state() 

    if not st.session_state.page_config_set:
        # Page title will be initially EN due to login page, then potentially update if lang changes
        # Or, we can set it based on current session language if we want it to reflect immediately after login
        st.set_page_config(page_title=get_translation("CEIC Point-in-Time Data Explorer"), layout="wide")
        st.session_state.page_config_set = True
    
    st.markdown( 
        """
        <style>
        .stApp { background-color: #E6E6FA; min-height: 100vh; }
        .stApp > header { background-color: transparent; }
        </style>
        """,
        unsafe_allow_html=True
    )

    if st.session_state.logged_in:
        Ceic.set_server("https://api.ceicdata.com/v2") 
        main_app()
    else:
        login_page()

if __name__ == '__main__':
    main()