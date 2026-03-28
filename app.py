import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime

# -------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------
def get_satellite_list():
    """Return a dictionary of popular satellite IDs and names."""
    return {
        25544: "International Space Station (ISS)",
        27424: "Hubble Space Telescope",
        28654: "NOAA 19 (weather)",
        33591: "NOAA 18 (weather)",
        33590: "NOAA 17 (weather)",
        27607: "FENGYUN 1C (weather)",
        43014: "NOAA 20 (weather)",
        43750: "RADARSAT Constellation",
        45338: "GPS IIF-12",
        42727: "Tiangong-1",
        37820: "GPS IIF-2",
        37765: "GLONASS",
        43072: "LARE",
        40967: "Cubesat",
    }

def fetch_satellite_data(sat_id, api_key, seconds=7200):
    """
    Fetch current position and predicted positions for the next `seconds` seconds.
    Returns a dict with 'current' (single position) and 'track' (list of positions).
    """
    url = f"https://api.n2yo.com/rest/v1/satellite/positions/{sat_id}/0/0/0/{seconds}/&apiKey={api_key}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if 'info' in data and 'positions' in data:
                positions = data['positions']
                if positions:
                    # The first position is the current one
                    current = positions[0]
                    # The rest (or all) can be used for the track
                    track = positions
                    return {'current': current, 'track': track, 'satname': data['info']['satname']}
        st.warning(f"API returned status {resp.status_code}")
        return None
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return None

def fetch_passes(sat_id, lat, lon, api_key, days=2):
    """Get next passes over given location."""
    url = f"https://api.n2yo.com/rest/v1/satellite/visualpasses/{sat_id}/{lat}/{lon}/{0}/{days}/&apiKey={api_key}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if 'passes' in data:
                return data['passes']
    except:
        pass
    return []

# -------------------------------------------------------------------
# Streamlit UI
# -------------------------------------------------------------------
st.set_page_config(page_title="Satellite Tracker", layout="wide")
st.title("🛰️ Satellite Tracker")
st.markdown("Real‑time positions and predicted ground tracks | Powered by N2YO")

# Sidebar for settings
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input(
        "N2YO API Key",
        type="password",
        value="8TGB9U-SLULC9-N5XN43-5P4U",
        help="Get your free key at n2yo.com"
    )
    if not api_key:
        st.warning("Please enter your N2YO API key to use the tracker.")
        st.stop()

    satellites = get_satellite_list()
    selected_sat_id = st.selectbox(
        "Select Satellite",
        options=list(satellites.keys()),
        format_func=lambda x: satellites[x]
    )

    # Auto‑refresh
    st.divider()
    auto_refresh = st.checkbox("Auto‑refresh", value=False)
    if auto_refresh:
        refresh_sec = st.number_input("Refresh interval (seconds)", min_value=10, max_value=300, value=60, step=10)

    # User location for passes
    st.divider()
    st.subheader("Predict passes over:")
    user_lat = st.number_input("Latitude", value=40.7128, format="%.5f")
    user_lon = st.number_input("Longitude", value=-74.0060, format="%.5f")

    if st.button("Refresh Data", use_container_width=True):
        st.rerun()

# Main content
if api_key:
    with st.spinner("Fetching satellite data..."):
        data = fetch_satellite_data(selected_sat_id, api_key, seconds=7200)

    if data and data['current']:
        current = data['current']
        track = data['track']
        sat_name = data['satname']

        # Current position info
        lat = current['satlatitude']
        lon = current['satlongitude']
        alt = current['sataltitude']
        vel = current['satvelocity']
        timestamp = datetime.fromtimestamp(current['timestamp']).strftime('%Y-%m-%d %H:%M:%S')

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Satellite", sat_name)
        col2.metric("Latitude", f"{lat:.4f}°")
        col3.metric("Longitude", f"{lon:.4f}°")
        col4.metric("Altitude", f"{alt:.1f} km")
        col1.metric("Speed", f"{vel:.2f} km/s")
        col2.metric("Last Updated", timestamp)

        # Map with current position and predicted ground track
        st.subheader("Current Position & Predicted Ground Track (next 2 hours)")
        # Prepare track coordinates
        track_lons = [p['satlongitude'] for p in track]
        track_lats = [p['satlatitude'] for p in track]

        fig = go.Figure()
        # Ground track (line)
        fig.add_trace(go.Scattergeo(
            lon=track_lons,
            lat=track_lats,
            mode='lines',
            line=dict(width=1, color='rgba(100, 200, 255, 0.7)'),
            name='Predicted Track'
        ))
        # Current position marker
        fig.add_trace(go.Scattergeo(
            lon=[lon],
            lat=[lat],
            mode='markers',
            marker=dict(size=10, color='red', symbol='circle'),
            name=sat_name,
            hovertext=f"{sat_name}<br>Lat: {lat:.4f}<br>Lon: {lon:.4f}<br>Alt: {alt:.0f} km"
        ))
        fig.update_layout(
            geo=dict(
                projection_type="natural earth",
                showland=True,
                landcolor="rgb(243, 243, 243)",
                countrycolor="rgb(204, 204, 204)",
            ),
            title=f"{sat_name} – Current Position and Predicted Track"
        )
        st.plotly_chart(fig, use_container_width=True)

        # Pass predictions
        st.subheader("🔭 Next Passes Over Your Location")
        passes = fetch_passes(selected_sat_id, user_lat, user_lon, api_key, days=2)
        if passes:
            df_passes = pd.DataFrame(passes)
            df_passes['startUTC'] = pd.to_datetime(df_passes['startUTC'], unit='s')
            df_passes['endUTC'] = pd.to_datetime(df_passes['endUTC'], unit='s')
            df_passes['duration'] = df_passes['duration'].apply(lambda x: f"{int(x//60)}m {int(x%60)}s")
            display_df = df_passes[['startUTC', 'endUTC', 'duration', 'maxEl']].rename(columns={
                'startUTC': 'Start (UTC)',
                'endUTC': 'End (UTC)',
                'duration': 'Duration',
                'maxEl': 'Max Elevation (°)'
            })
            st.dataframe(display_df, use_container_width=True)
        else:
            st.info("No passes predicted in the next 2 days.")
    else:
        st.error("Could not retrieve satellite data. Check your API key or satellite ID.")

# Auto‑refresh script
if auto_refresh:
    st.markdown(
        f"""
        <meta http-equiv="refresh" content="{refresh_sec}">
        """,
        unsafe_allow_html=True
    )
