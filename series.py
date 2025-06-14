import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import seaborn as sns
import threading

#Color Constants
TEALISH = "#00A88F"
LAVENDER = "#F2CEEF"
DEEP_PURPLE = "#792D82"

class SeriesVisualizer:
    def __init__(self, ceic_client, series_id, vintages_count=10000, vintages_start_date=None):
        self.ceic_client = ceic_client
        self.series_id = series_id
        self.metadata = None
        self.series_data = None
        self.df_reversed = None
        self.vintages_count = vintages_count
        self.vintages_start_date = vintages_start_date  

    def fetch_metadata(self):
        try:
            result = self.ceic_client.series_metadata(series_id=self.series_id)
            self.metadata = result.data[0].metadata
        except Exception as e:
            print(f"Error fetching metadata: {e}")
            self.metadata = None

    def fetch_series_data(self):
        try:
            result = self.ceic_client.series_data(series_id=self.series_id)
            self.series_data = result.data[0]
        except Exception as e:
            print(f"Error fetching series data: {e}")
            self.series_data = None

    def fetch_vintages_data(self):
        try:
            # Prepare parameters
            params = {"series_id": self.series_id}
            
            if self.vintages_start_date:
                # Add start date parameter if provided
                params["vintages_start_date"] = self.vintages_start_date
            else:
                # Only use vintages_count if no start date is provided
                params["vintages_count"] = self.vintages_count
            
            data = self.ceic_client.series_vintages_as_dict(**params)
            df = pd.DataFrame(data)
            df.index = pd.to_datetime(df.index)
            df.columns = pd.to_datetime(df.columns)
            self.df_reversed = df.sort_index(ascending=True).loc['2014-03-01':].copy()
        except Exception as e:
            print(f"Error fetching vintages data: {e}")
            self.df_reversed = None

    def fetch_all_data(self):
        threads = [
            threading.Thread(target=self.fetch_metadata),
            threading.Thread(target=self.fetch_series_data),
            threading.Thread(target=self.fetch_vintages_data)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def process_series_data(self):
        if not self.series_data:
            return None
        
        time_points = self.series_data.time_points
        if isinstance(time_points, dict):
            time_points = list(time_points.values())
        
        sorted_time_points = sorted(
            time_points, 
            key=lambda tp: tp.date if hasattr(tp, "date") else tp['date']
        )
        dates = [tp.date if hasattr(tp, "date") else tp['date'] for tp in sorted_time_points]
        values = [tp.value if hasattr(tp, "value") else tp['value'] for tp in sorted_time_points]
        return pd.DataFrame({'Date': pd.to_datetime(dates), 'Value': values})

    def plot_series(self, df):
        if df is None:
            return None
        fig = px.line(
            df, x='Date', y='Value', markers=True, 
            title=f"{getattr(self.metadata.country, 'name', 'N/A')}, {getattr(self.metadata, 'name', 'N/A')} Latest revised data",
            color_discrete_sequence=[TEALISH] 
        )
        fig.update_layout(xaxis_title="Date", yaxis_title="Value")
        fig.update_xaxes(tickformat="%Y-%m-%d")
        fig.update_traces(hovertemplate="Date: %{x|%Y-%m-%d}<br>Value: %{y}")
        return fig

    def style_vintages_table(self):
        if self.df_reversed is None:
            return None
        
        df_sorted = self.df_reversed.sort_index(ascending=True, axis=1).copy()
        df_sorted.columns = df_sorted.columns.strftime('%Y-%m-%d')
        df_sorted.index = df_sorted.index.strftime('%Y-%m-%d')
        
        def highlight_vintage_changes(row):
            styles = [''] * len(row)
            values = row.values
            for i in range(1, len(values)):
                if pd.notna(values[i]):
                    if pd.isna(values[i-1]) or (pd.notna(values[i-1]) and values[i] != values[i-1]):
                        styles[i] = f'background-color: {LAVENDER}' # Use Lavender color
            return styles
        
        return df_sorted.style.apply(highlight_vintage_changes, axis=1).format("{:.2f}")

    def plot_vintages_heatmap(self):
        if self.df_reversed is None:
            return None
        
        df_sorted = self.df_reversed.sort_index(axis=1, ascending=True)
        df_revision_diff = df_sorted.diff(axis=1)

        df_revision_diff.columns = df_revision_diff.columns.strftime('%Y-%m-%d')
        df_revision_diff.index = df_revision_diff.index.strftime('%Y-%m-%d')
        
        fig, ax = plt.subplots(figsize=(12, 8))
        sns.heatmap(df_revision_diff, cmap='coolwarm', center=0, cbar_kws={'label': 'Difference'}, ax=ax)
        ax.set_title('Heatmap of Differences Between Consecutive Vintage Updates')
        ax.set_xlabel('Vintage Update (YYYY-MM-DD)')
        ax.set_ylabel('Timepoint Date (YYYY-MM-DD)')
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
        fig.tight_layout()
        return fig 

    def plot_animated_vintages(self):
        if self.df_reversed is None:
            return None
        
        df_sorted = self.df_reversed.sort_index(axis=1, ascending=True)
        df_long = df_sorted.reset_index().melt(id_vars='index', var_name='vintage', value_name='value')
        df_long.rename(columns={'index': 'time'}, inplace=True)
        
        df_long['time'] = pd.to_datetime(df_long['time'])
        df_long['vintage'] = pd.to_datetime(df_long['vintage']).dt.strftime('%Y-%m-%d') 
        
        y_min = df_long['value'].min()
        y_max = df_long['value'].max()
        y_padding = (y_max - y_min) * 0.05 

        fig = px.line(
            df_long, x="time", y="value", animation_frame="vintage", 
            title="Animated Timeseries Vintages",
            range_y=[y_min - y_padding, y_max + y_padding],
            color_discrete_sequence=[DEEP_PURPLE] 
        )
        
        fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Value",
            xaxis=dict(tickformat="%Y-%m-%d"),
        )
        fig.update_traces(hovertemplate="Date: %{x|%Y-%m-%d}<br>Value: %{y}")
        return fig

    def plot_vintage_comparison(self, date1=None, date2=None):
        if self.df_reversed is None:
            return None
        
        df_str = self.df_reversed.copy()
        df_str.index = df_str.index.astype(str)
        df_str.columns = df_str.columns.astype(str)
        
        # Get available dates
        available_dates = df_str.columns.tolist()
        
        # Use first two dates if none provided
        if date1 is None or date2 is None:
            if len(available_dates) < 2:
                return None
            date1 = available_dates[0]
            date2 = available_dates[1]
        
        if date1 not in available_dates or date2 not in available_dates:
            return None
        
        trace0 = go.Scatter(x=df_str.index, y=df_str[date1], mode="lines+markers", 
                            name=date1, line=dict(color=TEALISH))
        trace1 = go.Scatter(x=df_str.index, y=df_str[date2], mode="lines+markers", 
                            name=date2, line=dict(color=DEEP_PURPLE))
        
        fig = go.Figure(data=[trace0, trace1])
        fig.update_layout(
            title=f"Vintage Comparison: {date1} vs {date2}",
            xaxis_title="Time",
            yaxis_title="Value"
        )
        return fig
    
    def plot_vintage_differences(self):
        if self.df_reversed is None:
            return None
        
        df_sorted = self.df_reversed.sort_index(axis=1, ascending=True)
        first_vals = df_sorted.apply(lambda row: row.dropna().iloc[0] if row.dropna().size > 0 else np.nan, axis=1)
        last_vals = df_sorted.apply(lambda row: row.dropna().iloc[-1] if row.dropna().size > 0 else np.nan, axis=1)
        diff = last_vals - first_vals
        diff.index = pd.to_datetime(diff.index)
        diff = diff.sort_index()
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        width = (diff.index[1] - diff.index[0]).days * 0.8 if len(diff.index) > 1 else 10
        colors = [DEEP_PURPLE if value >= 0 else LAVENDER for value in diff.values] 
        
        ax.bar(diff.index, diff.values, width=width, color=colors)
        ax.axhline(0, color='black', linewidth=1)
        ax.set_title("Difference Between Last and First Available Values per Vintage")
        ax.set_xlabel("Vintage Date")
        ax.set_ylabel("Difference (Last - First)")
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
        fig.tight_layout()
        return fig