import os

# Get the directory where script_generator.py is located
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
# Construct the path to series.py relative to this script's location
_SERIES_PY_PATH = os.path.join(_MODULE_DIR, "series.py")


def generate_python_script(series_id_for_script: str = None) -> str: # Made series_id_for_script optional
    """
    Generates a self-contained Python script that can reproduce visualizations
    for a CEIC series ID. The SeriesVisualizer class from 'series.py'
    is embedded into the script.

    Args:
        series_id_for_script: The CEIC series ID for which to generate the script.
                              If None or empty, a placeholder will be used.

    Returns:
        A string containing the complete Python script.
    """
    try:
        with open(_SERIES_PY_PATH, "r", encoding="utf-8") as f_series_py:
            series_visualizer_class_code = f_series_py.read()
    except FileNotFoundError:
        error_msg = (
            f"# ERROR: The file 'series.py' was not found at the expected location: {_SERIES_PY_PATH}\n"
            "# This script generator relies on 'series.py' to embed the SeriesVisualizer class.\n"
            "# Please ensure 'series.py' is in the same directory as 'script_generator.py' "
            "and 'app.py'."
        )
        return error_msg

    script_instructions = ""
    if series_id_for_script:
        series_id_placeholder = f'"{series_id_for_script}"'
        generated_for_id_comment = f"# Generated for Series ID: {series_id_for_script}"
        filename_suggestion = f"visualize_ceic_series_{series_id_for_script}.py"
        script_instructions = f"""# 1. Save this script as a Python file (e.g., {filename_suggestion}).
#
# 2. IMPORTANT: You MUST replace the placeholder values for
#    `CEIC_USERNAME` and `CEIC_PASSWORD` below with your actual CEIC credentials.
#
# 3. Ensure you have the necessary Python libraries installed. You can install them using pip:
#    pip install pandas numpy plotly matplotlib seaborn ceic_api_client
#
# 4. Run the script from your terminal:
#    python {filename_suggestion}"""
        series_id_output_dir_suffix = series_id_for_script
        script_behavior_series_id = f"Series ID: {series_id_for_script}"

    else:
        series_id_placeholder = '"YOUR_SERIES_ID_HERE"' # Placeholder if no ID is given
        generated_for_id_comment = "# Generated as a generic CEIC visualization script"
        filename_suggestion = "visualize_ceic_series_generic.py"
        script_instructions = f"""# 1. Save this script as a Python file (e.g., {filename_suggestion}).
#
# 2. IMPORTANT: You MUST replace the placeholder values for
#    `CEIC_USERNAME`, `CEIC_PASSWORD`, AND `SERIES_ID` below with your actual
#    CEIC credentials and the Series ID you want to visualize.
#
# 3. Ensure you have the necessary Python libraries installed. You can install them using pip:
#    pip install pandas numpy plotly matplotlib seaborn ceic_api_client
#
# 4. Run the script from your terminal:
#    python {filename_suggestion}"""
        series_id_output_dir_suffix = "generic"
        script_behavior_series_id = "the Series ID you provide in the `SERIES_ID` variable"


    script_template = f"""#!/usr/bin/env python3
# CEIC Data Visualization Script
{generated_for_id_comment}
#
# --- HOW TO USE THIS SCRIPT ---
{script_instructions}
#
# --- SCRIPT BEHAVIOR ---
# - It will attempt to log in to CEIC using the credentials you provide.
# - It will fetch data for {script_behavior_series_id}.
# - Plotly charts will typically open in your default web browser.
# - Matplotlib charts will be displayed in separate windows (or inline if using an IDE
#   like Spyder or VS Code with interactive plot support).
# - Some outputs (like styled tables or Matplotlib figures) will be saved to a
#   directory named 'ceic_series_{series_id_output_dir_suffix}_output'.

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import seaborn as sns
import threading
from ceic_api_client.pyceic import Ceic
import sys
import os # For creating output directory and joining paths

# --- START OF EMBEDDED SeriesVisualizer CLASS (from series.py) ---
# The following code is copied from 'series.py' to make this script self-contained.
# All necessary imports for the class are assumed to be covered by the imports above
# or are part of the class definition itself.

{series_visualizer_class_code}

# --- END OF EMBEDDED SeriesVisualizer CLASS ---

def run_visualization_script():
    # --- User Configuration ---
    # !!! IMPORTANT: REPLACE THESE WITH YOUR ACTUAL CEIC CREDENTIALS !!!
    CEIC_USERNAME = "YOUR_USERNAME_HERE"
    CEIC_PASSWORD = "YOUR_PASSWORD_HERE"
    # The Series ID for this script.
    # !!! If this is "YOUR_SERIES_ID_HERE", you MUST replace it with an actual Series ID. !!!
    SERIES_ID = {series_id_placeholder}

    # --- Output Directory Setup ---
    # Create a directory to save output files like images and HTML tables
    # Use a generic suffix if SERIES_ID is a placeholder, otherwise use the actual ID
    output_dir_id_part = SERIES_ID if SERIES_ID != "YOUR_SERIES_ID_HERE" else "{series_id_output_dir_suffix}"
    OUTPUT_DIR = f"ceic_series_{{output_dir_id_part}}_output"
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        print(f"Output files will be saved in the directory: '{{OUTPUT_DIR}}'")
    except OSError as e:
        print(f"Error creating output directory '{{OUTPUT_DIR}}': {{e}}. Files will be saved in the current directory.")
        OUTPUT_DIR = "." # Fallback to current directory

    # --- Credentials and Series ID Check ---
    if CEIC_USERNAME == "YOUR_USERNAME_HERE" or CEIC_PASSWORD == "YOUR_PASSWORD_HERE":
        print("\\n" + "="*80)
        print("ERROR: MISSING CREDENTIALS")
        print("Please open this script file and replace 'YOUR_USERNAME_HERE' and ")
        print("'YOUR_PASSWORD_HERE' with your actual CEIC username and password.")
        print("="*80 + "\\n")
        sys.exit(1)

    if SERIES_ID == "YOUR_SERIES_ID_HERE":
        print("\\n" + "="*80)
        print("ERROR: MISSING SERIES ID")
        print("Please open this script file and replace 'YOUR_SERIES_ID_HERE' ")
        print("with the actual CEIC Series ID you wish to visualize.")
        print("="*80 + "\\n")
        sys.exit(1)

    # --- CEIC API Login ---
    print(f"\\nAttempting to log in to CEIC with username: {{CEIC_USERNAME}}...")
    try:
        # Ensure the API server endpoint is set (if not default)
        # Ceic.set_server("YOUR_API_SERVER_URL") # Uncomment and set if using a non-default server
        Ceic.set_server("https://api.ceicdata.com/v2") # Default CEIC API v2 server
        
        ceic_client = Ceic.login(CEIC_USERNAME, CEIC_PASSWORD)
        print("Successfully logged in to CEIC.")
    except Exception as e:
        print(f"CEIC login failed: {{e}}")
        print("Please check your username, password, and CEIC API client configuration.")
        sys.exit(1)

    # --- Initialize SeriesVisualizer and Fetch Data ---
    print(f"\\nInitializing visualizer for Series ID: {{SERIES_ID}}")
    visualizer = SeriesVisualizer(ceic_client, SERIES_ID) 
    
    print("Fetching all required data for the series... This may take a moment.")
    visualizer.fetch_all_data() 

    if not visualizer.metadata:
        print(f"Could not fetch metadata for Series ID: {{SERIES_ID}}. Exiting.")
        sys.exit(1)
    
    print("\\n--- Series Metadata Overview ---")
    meta = visualizer.metadata
    print(f"  ID: {{getattr(meta, 'id', 'N/A')}}")
    print(f"  Name: {{getattr(meta, 'name', 'N/A')}}")
    country_obj = getattr(meta, 'country', None)
    print(f"  Country: {{getattr(country_obj, 'name', 'N/A')}}")
    frequency_obj = getattr(meta, 'frequency', None)
    print(f"  Frequency: {{getattr(frequency_obj, 'name', 'N/A')}}")
    source_obj = getattr(meta, 'source', None)
    print(f"  Source: {{getattr(source_obj, 'name', 'N/A')}}")
    print(f"  Last Update Time: {{getattr(meta, 'last_update_time', 'N/A')}}")
    print(f"  Last Value: {{getattr(meta, 'last_value', 'N/A')}}")
    print("----------------------------------")

    # --- Generate and Display/Save Visualizations ---
    
    if visualizer.series_data:
        print("\\n--- Generating: Plot of Latest Revised Time Series Data ---")
        df_series = visualizer.process_series_data()
        if df_series is not None and not df_series.empty:
            fig_series = visualizer.plot_series(df_series)
            if fig_series:
                print("Displaying Plotly chart for revised time series data (opens in browser)...")
                fig_series.show()
        elif df_series is not None and df_series.empty:
            print("No time series data points found for this series.")
        else:
            print("Failed to process or plot series data.")
    else:
        print("\\nInfo: Latest revision series data (series_data) not available or not fetched.")

    if visualizer.df_reversed is not None and not visualizer.df_reversed.empty:
        print("\\n--- Processing Vintages Data ---")

        print("\\n--- Generating: Styled Vintages Table ---")
        styled_table_df = visualizer.style_vintages_table() 
        if styled_table_df:
            try:
                html_table_filename = f"styled_vintages_table_{{output_dir_id_part}}.html"
                html_table_path = os.path.join(OUTPUT_DIR, html_table_filename)
                with open(html_table_path, "w", encoding="utf-8") as f:
                    f.write(styled_table_df.to_html())
                print(f"Styled vintages table saved to: {{html_table_path}}")
            except Exception as e_style:
                print(f"Could not save styled table to HTML: {{e_style}}")
                print("As a fallback, printing the first 10 rows/columns of the raw vintages DataFrame:")
                print(visualizer.df_reversed.head(10).iloc[:, :min(10, visualizer.df_reversed.shape[1])])
        else:
            print("Failed to generate or style the vintages table.")

        print("\\n--- Generating: Heatmap of Vintage Changes ---")
        fig_heatmap = visualizer.plot_vintages_heatmap() 
        if fig_heatmap:
            heatmap_filename = f"heatmap_vintage_changes_{{output_dir_id_part}}.png"
            heatmap_path = os.path.join(OUTPUT_DIR, heatmap_filename)
            try:
                fig_heatmap.savefig(heatmap_path, bbox_inches='tight')
                print(f"Heatmap of vintage changes saved to: {{heatmap_path}}")
                print("Displaying Matplotlib heatmap (may appear after script finishes or in a separate window)...")
            except Exception as e_save_heatmap:
                print(f"Could not save heatmap image: {{e_save_heatmap}}")
        else:
            print("Failed to generate heatmap of vintage changes.")
            
        print("\\n--- Generating: Animated Timeseries Vintages ---")
        fig_animated = visualizer.plot_animated_vintages()
        if fig_animated:
            print("Displaying Plotly chart for animated timeseries vintages (opens in browser)...")
            fig_animated.show()
        else:
            print("Failed to generate animated timeseries vintages plot.")

        print("\\n--- Generating: Vintage Comparison Plot ---")
        fig_comparison = visualizer.plot_vintage_comparison()
        if fig_comparison:
            print("Displaying Plotly chart for vintage comparison (opens in browser)...")
            fig_comparison.show()
        else:
            print("Failed to generate vintage comparison plot.")

        print("\\n--- Generating: Bar Chart of Vintage Differences ---")
        fig_bar_diff = visualizer.plot_vintage_differences() 
        if fig_bar_diff:
            bar_chart_filename = f"bar_chart_vintage_differences_{{output_dir_id_part}}.png"
            bar_chart_path = os.path.join(OUTPUT_DIR, bar_chart_filename)
            try:
                fig_bar_diff.savefig(bar_chart_path, bbox_inches='tight')
                print(f"Bar chart of vintage differences saved to: {{bar_chart_path}}")
                print("Displaying Matplotlib bar chart (may appear after script finishes or in a separate window)...")
            except Exception as e_save_bar:
                print(f"Could not save vintage differences bar chart: {{e_save_bar}}")
        else:
            print("Failed to generate bar chart of vintage differences.")
        
        if plt.get_fignums(): 
            print("\\nShowing all pending Matplotlib/Seaborn plots...")
            print("(These may open in separate windows. Close them to allow the script to fully terminate.)")
            plt.show()
        else:
            print("\\nNo Matplotlib/Seaborn plots were generated or available to show interactively.")

    elif visualizer.df_reversed is None:
         print("\\nInfo: Vintages data (df_reversed) not available or not fetched for this series.")
    elif visualizer.df_reversed.empty:
         print("\\nInfo: Vintages data (df_reversed) is empty for this series. Skipping vintage-specific plots.")

    print("\\n--- Data Visualization Script Finished ---")
    print(f"Please check the '{{OUTPUT_DIR}}' folder for any saved files (HTML tables, PNG images).")
    print("Plotly charts should have opened in your web browser.")

if __name__ == '__main__':
    run_visualization_script()
"""
    return script_template

# Example of how to use this generator (for testing purposes):
if __name__ == '__main__':
    print("Testing script_generator.py...")
    # Test with a specific series ID
    test_series_id = "5774401" 
    generated_script_content_specific = generate_python_script(test_series_id)
    output_filename_specific = f"generated_visualization_script_for_{test_series_id}.py"
    with open(output_filename_specific, "w", encoding="utf-8") as f:
        f.write(generated_script_content_specific)
    print(f"Generated script with specific ID saved as: {output_filename_specific}")

    # Test with no series ID (generic script)
    generated_script_content_generic = generate_python_script()
    output_filename_generic = "generated_visualization_script_generic.py"
    with open(output_filename_generic, "w", encoding="utf-8") as f:
        f.write(generated_script_content_generic)
    print(f"Generated generic script saved as: {output_filename_generic}")

    if "ERROR: The file 'series.py' was not found" in generated_script_content_generic:
         print(generated_script_content_generic)
    else:
        print("\nFirst few lines of the generic generated script:")
        print("\n".join(generated_script_content_generic.splitlines()[:30]))