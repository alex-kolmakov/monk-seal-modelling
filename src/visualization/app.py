import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd
import numpy as np

# Initialize Dash App
app = dash.Dash(__name__, title="Monk Seal Dashboard")

import sys
import os

# 1. Load Data
def load_data():
    # Determine file from CLI args or default
    # Note: Dash uses argv for server config too, so we need to be careful.
    # A safer way relies on env var or looking for non-flag args, but for local dev:
    data_file = "real_data_results.csv"
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        candidate = sys.argv[1]
        if os.path.exists(candidate):
            data_file = candidate
            print(f"Loading data from: {data_file}")

    try:
        df = pd.read_csv(data_file)
        df['time'] = pd.to_datetime(df['time'])
        df['time_str'] = df['time'].dt.strftime('%Y-%m-%d %H:%M')
        # ... rest of processing ...
        if 'agent_id' in df.columns:
            df['agent_id_str'] = df['agent_id'].astype(str)
            df['prev_state'] = df.groupby('agent_id')['state'].shift()
            df['state_changed'] = (df['state'] != df['prev_state'])
            df.loc[df['prev_state'].isna(), 'state_changed'] = True
        
        return df
    except FileNotFoundError:
        print(f"Data file '{data_file}' not found.")
        return pd.DataFrame()

df = load_data()
if not df.empty:
    agent_ids = sorted(df['agent_id'].unique())
else:
    agent_ids = []

# 2. Layout
app.layout = html.Div([
    html.H1("Monk Seal ABM Dashboard 🦭", style={'textAlign': 'center', 'marginBottom': '10px'}),
    
    html.Div([
        # Row 1: Map and Controls
        html.Div([
            # Map (Left, 80%)
            html.Div([
                dcc.Graph(id='map-graph', style={'height': '65vh'})
            ], style={'width': '80%', 'display': 'inline-block', 'verticalAlign': 'top'}),
            
            # Controls (Right, 20%)
            html.Div([
                html.H3("Controls", style={'marginTop': '0'}),
                html.Label("Select Agents (Single for Path):"),
                dcc.Dropdown(
                    id='agent-selector',
                    options=[{'label': f"Seal {i}", 'value': i} for i in agent_ids],
                    value=agent_ids, # Default select all
                    multi=True,
                    style={'maxHeight': '400px', 'overflowY': 'scroll'}
                ),
                html.Div([
                    html.P("Use single selection to see full path details.", style={'color': '#666', 'fontSize': '0.9em'})
                ], style={'marginTop': '10px'})
            ], style={'width': '19%', 'display': 'inline-block', 'verticalAlign': 'top', 'paddingLeft': '10px'})
        ], style={'width': '100%', 'display': 'flex', 'marginBottom': '20px'}),
        
        # Row 2: Telemetry (Bottom, 100%)
        html.Div([
            html.H4("Telemetry & Population Analysis"),
            dcc.Graph(id='telemetry-graph', style={'height': '35vh'})
        ], style={'width': '100%'})
    ])
], style={'fontFamily': 'sans-serif', 'padding': '20px', 'maxWidth': '1600px', 'margin': '0 auto'})


# 3. Callbacks
@app.callback(
    [Output('map-graph', 'figure'),
     Output('telemetry-graph', 'figure')],
    [Input('agent-selector', 'value')]
)
def update_graphs(selected_agents):
    if not selected_agents:
        return px.scatter(title="No Agents Selected"), px.line(title="No Data")
    
    # Filter Data
    if not isinstance(selected_agents, list):
        selected_agents = [selected_agents]
    
    # Determine Mode
    single_mode = (len(selected_agents) == 1)
    
    filtered_df = df[df['agent_id'].isin(selected_agents)].copy()
    filtered_df = filtered_df.sort_values(by=['agent_id', 'time'])

    # --- MAP ---
    # Define Color Map for Consistency
    color_map = {
        "FORAGING": "#1f77b4", # Blue
        "RESTING": "#2ca02c",  # Green
        "HAULING_OUT": "#ff7f0e", # Orange
        "TRANSITING": "#7f7f7f", # Grey
        "NURSING": "#e377c2",   # Pink
        "SLEEPING": "#9467bd"   # Purple
    }

    # --- MAP ---
    if single_mode:
        # SINGLE AGENT: Show Path + State Point Markers
        # Fix: Use a single neutral trace for the path to avoid "teleporting" lines between disjoint state groups
        fig_map = px.line_mapbox(
            filtered_df,
            lat="lat", lon="lon",
            # color="state", # REMOVED: Causes disjoint traces
            color_discrete_sequence=["lightgrey"], # Neutral path
            zoom=9,
            title=f"Seal {selected_agents[0]} Activity Map"
        )
        
        # Add Markers for State (Colored by State)
        # We plot all points as markers on top
        scatter_fig = px.scatter_mapbox(
            filtered_df,
            lat="lat", lon="lon",
            color="state", # Color points by what they were doing
            color_discrete_map=color_map,
            size_max=15,
            hover_data=["time_str", "energy", "swh"]
        )
        # Add traces
        for trace in scatter_fig.data:
            # trace.marker.size = 8 # Adjust size if needed
            fig_map.add_trace(trace)
                
    else:
        # MULTI AGENT: Show ONLY State Changes (Decluttered)
        changes_df = filtered_df[filtered_df['state_changed']]
        
        if changes_df.empty:
             fig_map = px.scatter_mapbox(title="No state changes detected (Try selecting fewer agents)")
        else:
            fig_map = px.scatter_mapbox(
                changes_df,
                lat="lat", lon="lon",
                color="state", # Color by Activity (Foraging, Resting, etc)
                color_discrete_map=color_map,
                hover_name="agent_id_str",
                hover_data=["time_str", "energy"],
                zoom=9,
                title="Population Activity Distribution (State Changes Only)"
            )

    # Common Map Layout
    fig_map.update_layout(
        mapbox_style="open-street-map",
        mapbox_center={"lat": 32.6, "lon": -16.5},
        margin={"r": 0, "t": 30, "l": 0, "b": 0},
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=0.01, bgcolor="rgba(255,255,255,0.8)")
    )

    # --- TELEMETRY ---
    # For many agents, a line plot is chaotic.
    # If 100 agents, maybe show Population Count by State?
    if len(selected_agents) > 10:
        # Aggregate View: Stacked Area of States?
        # Counts of agents in each state over time
        # We need a time-aligned dataframe for this.
        # Resample logic might be heavy. 
        # Simpler: Scatter Energy of all agents? Or Average Energy?
        # Let's show Average Energy + Bounds?
        
        # Group by time and get mean energy
        stats = filtered_df.groupby('time')['energy'].agg(['mean', 'std']).reset_index()
        fig_telemetry = px.line(stats, x='time', y='mean', title=f"Average Population Energy (n={len(selected_agents)})")
        # Add error bands ideally, but keep simple for now
        fig_telemetry.update_traces(line_color='#17becf')

    else:
        # Detailed View (up to 10 agents)
        fig_telemetry = px.line(
            filtered_df,
            x="time",
            y="energy",
            color="agent_id_str",
            title="Individual Energy Levels",
            markers=True if single_mode else False # Markers only for single to reduce clutter
        )
    
    fig_telemetry.update_layout(margin={"r": 10, "t": 30, "l": 10, "b": 10}, height=300)

    return fig_map, fig_telemetry

if __name__ == '__main__':
    # Use 8050 or another port
    # Updated to app.run() for Dash 2.13+ compatibility (obsolete warning fix)
    app.run(debug=True, port=8050)
