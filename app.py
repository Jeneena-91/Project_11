import pandas as pd
import re
from geopy.distance import geodesic
import plotly.graph_objects as go
import streamlit as st

# Load and Clean Data

df =  pd.read_csv("Tourist destinations.xls")

df.columns = [re.sub(r'(?<!^)(?=[A-Z])', '_', col).replace(" ", "_").lower() for col in df.columns]
df.drop(columns=["unnamed:_0", "zipcode"], inplace=True, errors='ignore')
df.dropna(subset=['latitude', 'longitude'], inplace=True)
df.info()
st.header('Sightseeing USA, Tourist Destinations')
st.write("""
         #### Filter the data below based on tourist spots
         # """)

# ----------------------------
# Sidebar - Step 1: State Selection
# ----------------------------
st.sidebar.title("Tour Planner Filters")

states = df['state'].dropna().unique()
selected_state = st.sidebar.selectbox("Choose a State", sorted(states))

# ----------------------------
# Filter State Data
# ----------------------------
state_df = df[df['state'] == selected_state].copy()

# ----------------------------
# Sidebar  Select Categories in That State
# ----------------------------
if 'category' in state_df.columns:
    categories = sorted(state_df['categories'].dropna().unique())
    selected_categories = st.sidebar.multiselect("Select Categories", categories, default=categories[:2])
else:
    selected_categories = None

# ----------------------------
# Apply Category Filter
# ----------------------------
if selected_categories:
    state_df = state_df[state_df['categories'].isin(selected_categories)]

# ----------------------------
#  Display and Let User Select Start Point
# ----------------------------
top_destinations = (
    state_df
    .sort_values(by='weighted__score', ascending=False)
    .reset_index(drop=True)
)

st.title("Tourist Route Optimizer")
st.markdown(f"### Top Tourist Spots in **{selected_state}**")
if selected_categories:
    st.markdown(f"**Categories:** {', '.join(selected_categories)}")

st.dataframe(top_destinations[['name', 'city', 'categories', 'rating']].head(20))

start_point_name = st.selectbox("Select Your Starting Point", top_destinations['name'].unique())

# ----------------------------
# Sidebar : Set Route Size Limits
# ----------------------------
max_locations = st.sidebar.slider("Specify the number of locations to visit.", min_value=2, max_value=10, value=9)
num_stops = st.sidebar.slider("Number of Route Stops", min_value=2, max_value=max_locations, value=6)

# ----------------------------
# Build Route Starting From User Selection
# ----------------------------
def build_route(df, start_name, num_stops):
    start = df[df['name'] == start_name].iloc[0]
    remaining_df = df[df['name'] != start_name].copy()

    # Sort remaining by score and take top N-1 to fill rest of route
    selected = remaining_df.sort_values(by='weighted__score', ascending=False).head(num_stops - 1)
    selected = pd.concat([pd.DataFrame([start]), selected]).reset_index(drop=True)
    return selected

selected_stops = build_route(top_destinations.head(max_locations), start_point_name, num_stops)

# ----------------------------
# Step 5: Optimize Route with Nearest Neighbor (from chosen start)
# ----------------------------
def nearest_neighbor_route(df, start_name):
    visited = []
    unvisited = df.copy()
    current_location = unvisited[unvisited['name'] == start_name].iloc[0]
    visited.append(current_location)
    unvisited = unvisited[unvisited['name'] != start_name]

    while not unvisited.empty:
        current_coords = (current_location['latitude'], current_location['longitude'])
        distances = unvisited.apply(lambda row: geodesic(current_coords, (row['latitude'], row['longitude'])).km, axis=1)
        nearest_idx = distances.idxmin()
        current_location = unvisited.loc[nearest_idx]
        visited.append(current_location)
        unvisited = unvisited.drop(nearest_idx)

    return pd.DataFrame(visited)

optimized_route = nearest_neighbor_route(selected_stops, start_point_name)

# ----------------------------
# Distance and Time Calculation
# ----------------------------
def calculate_total_distance_and_time(route_df, avg_speed_kmh=80):
    total_distance = 0
    total_time = 0
    for i in range(len(route_df) - 1):
        start = (route_df.iloc[i]['latitude'], route_df.iloc[i]['longitude'])
        end = (route_df.iloc[i + 1]['latitude'], route_df.iloc[i + 1]['longitude'])
        dist = geodesic(start, end).km
        total_distance += dist
        total_time += dist / avg_speed_kmh
    return total_distance, total_time

total_km, total_hr = calculate_total_distance_and_time(optimized_route)

# ----------------------------
# Plot Route
# ----------------------------
def plot_route(df, title):
    fig = go.Figure()
    fig.add_trace(go.Scattermapbox(
        mode="markers+lines+text",
        lon=df['longitude'],
        lat=df['latitude'],
        text=df['name'],
        marker=dict(size=10, color='blue'),
        line=dict(width=3, color='red'),
        name="Route"
    ))
    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(
                lon=df['longitude'].mean(),
                lat=df['latitude'].mean()
            ),
            zoom=6
        ),
        title=title,
        margin=dict(l=0, r=0, b=0, t=30),
        height=600
    )
    return fig

# ----------------------------
#  Display Output
# ----------------------------
st.markdown("### Optimized Route Map")
st.plotly_chart(plot_route(optimized_route, f"Optimized Route in {selected_state}"), use_container_width=True)

st.markdown(f"**Total Distance:** {total_km:.2f} km")
st.markdown(f"**Estimated Driving Time:** {total_hr:.2f} hours")

st.markdown("### Route Details")
st.dataframe(optimized_route[['name', 'city','address', 'categories', 'rating']])
