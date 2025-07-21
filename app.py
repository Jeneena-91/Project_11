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
df= df.drop_duplicates(subset='address')

st.header('Route Optimizer')
st.write("""
         #### Once you choose a state and how many places you’d like to visit, the app will find the most popular destinations in that area. You'll then pick a starting point from that list. Based on your choices, the app will calculate the best travel route, including the total distance, estimated travel time, and the order in which to visit each stop.
         #""")

states = df['state'].unique()
categories = sorted(df['category'].dropna().unique()) if 'category' in df.columns else []

# Sidebar Filters

st.sidebar.title("Tour Planner Filters")

selected_state = st.sidebar.selectbox("Choose a State", sorted(states))

if categories:
    selected_categories = st.sidebar.multiselect("Select Categories", categories, default=categories)
else:
    selected_categories = None

max_locations = st.sidebar.slider("How many destinations would you like to visit?", min_value=2, max_value=10, value=9)
num_stops = st.sidebar.slider("Number of Route Stops", min_value=2, max_value=max_locations, value=6)


# Filter Data Based on Selections

filtered_df = df[df['state'] == selected_state]

if selected_categories:
    filtered_df = filtered_df[filtered_df['category'].isin(selected_categories)]

top_n_destinations = (
    filtered_df
    .sort_values('weighted__score', ascending=False)
    .head(max_locations)
    .reset_index(drop=True)
)

if len(top_n_destinations) < num_stops:
    st.warning("Not enough locations available for the number of stops selected.")
    st.stop()

selected_stops = top_n_destinations.iloc[:num_stops]
# Select the starting destination
start_point_name = st.sidebar.selectbox("Choose your starting point", top_n_destinations['name'])

## Build Route Starting From User Selection

def build_route(df, start_name, num_stops):
    start = df[df['name'] == start_name].iloc[0]
    remaining_df = df[df['name'] != start_name].copy()

    # Sort remaining by score and take top N-1 to fill rest of route
    selected = remaining_df.sort_values(by='weighted__score', ascending=False).head(num_stops - 1)
    selected = pd.concat([pd.DataFrame([start]), selected]).reset_index(drop=True)
    return selected

selected_stops = build_route(top_n_destinations.head(max_locations), start_point_name, num_stops)


#  Optimize Route with Nearest Neighbor (from chosen start)

def nearest_neighbor_route(df, start_name):
    visited = []
    unvisited = df.copy()
    current_location = unvisited[unvisited['name'] == start_name].iloc[0]
    visited.append(current_location)
    unvisited = unvisited[unvisited['name'] != start_name]

    while not unvisited.empty:
        current_coords = (current_location['latitude'], current_location['longitude'])
        distances = unvisited.apply(lambda row: geodesic(current_coords, (row['latitude'], row['longitude'])).km, axis=1)
        nearest_location= distances.idxmin()
        current_location = unvisited.loc[nearest_location]
        visited.append(current_location)
        unvisited = unvisited.drop(nearest_location)

    return pd.DataFrame(visited)

optimized_route = nearest_neighbor_route(selected_stops, start_point_name)


# Total Distance and Time Calculation

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

# Plot the optimized route

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


#  Display the Output

st.markdown("### Optimized Route Map")
st.plotly_chart(plot_route(optimized_route, f"Optimized Route in {selected_state}"), use_container_width=True)

st.markdown(f"**Total Distance:** {total_km:.2f} km")
st.markdown(f"**Estimated Driving Time:** {total_hr:.2f} hours")

st.markdown("### Route Details")
st.dataframe(optimized_route[['name', 'city','address', 'categories', 'rating']].reset_index(drop=True))
