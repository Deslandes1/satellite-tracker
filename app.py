import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime
import time

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

@st.cache_data(ttl=60, show_spinner=False)
def fetch_all_satellites(api_key, satellite_dict):
    """
    Fetch current position for all satellites in the dictionary.
    Returns a DataFrame with columns: ID, Name, Latitude, Longitude, Altitude, Speed, LastUpdate
    """
    results = []
    for sat_id, sat_name in satellite_dict.items():
        try:
            url = f"https://api.n2yo.com/rest/v1/satellite/positions/{sat_id}/0/0/0/1/&apiKey={api_key}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if 'positions' in data and data['positions']:
                    pos = data['positions'][0]
                    results.append({
                        "ID": sat_id,
                        "Name": sat_name,
                        "Latitude": pos['satlatitude'],
                        "Longitude": pos['satlongitude'],
                        "Altitude (km)": pos['sataltitude'],
                        "Speed (km/s)": pos['satvelocity'],
                        "Last Update": datetime.fromtimestamp(pos['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                    })
                else:
                    results.append({"ID": sat_id, "Name": sat_name, "Error": "No position data"})
            else:
                results.append({"ID": sat_id, "Name": sat_name, "Error": f"HTTP {resp.status_code}"})
        except Exception as e:
            results.append({"ID": sat_id, "Name": sat_name, "Error": str(e)})
        # Sleep to respect rate limit (10 requests/min)
        time.sleep(1.5)
    return pd.DataFrame(results)

def fetch_satellite_details(sat_id, api_key, seconds=7200):
    """Fetch current position and predicted track for a single satellite."""
    url = f"https://api.n2yo.com/rest/v1/satellite/positions/{sat_id}/0/0/0/{seconds}/&apiKey={api_key}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if 'info' in data and 'positions' in data:
                positions = data['positions']
                if positions:
                    return {
                        'current': positions[0],
                        'track': positions,
                        'satname': data['info']['satname']
                    }
    except Exception as e:
        st.error(f"Error fetching details: {e}")
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
st.markdown("Real‑time positions and ground tracks | Powered by N2YO")

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

    auto_refresh = st.checkbox("Auto‑refresh", value=False)
    if auto_refresh:
        refresh_sec = st.number_input("Refresh interval (seconds)", min_value=10, max_value=300, value=60, step=10)

    st.divider()
    st.subheader("Predict passes over:")
    user_lat = st.number_input("Latitude", value=40.7128, format="%.5f")
    user_lon = st.number_input("Longitude", value=-74.0060, format="%.5f")

    if st.button("Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# -------------------------------------------------------------------
# Main content
# -------------------------------------------------------------------
if api_key:
    satellites_dict = get_satellite_list()

    # Fetch all satellites with a spinner
    with st.spinner("Fetching satellite positions (this may take 30 seconds)..."):
        df_satellites = fetch_all_satellites(api_key, satellites_dict)

    # Remove rows with errors
    if 'Error' in df_satellites.columns:
        error_rows = df_satellites[df_satellites['Error'].notna()]
        if not error_rows.empty:
            st.warning(f"Could not fetch data for: {', '.join(error_rows['Name'])}")
        df_satellites = df_satellites[df_satellites['Error'].isna()].drop(columns=['Error'], errors='ignore')

    if df_satellites.empty:
        st.error("No satellite data available. Check your API key or try again later.")
        st.stop()

    # Display table of satellites
    st.subheader("📋 Satellite Positions")
    st.dataframe(df_satellites, use_container_width=True)

    # Download full table as CSV
    csv = df_satellites.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download All Satellite Data (CSV)",
        data=csv,
        file_name=f"satellites_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        use_container_width=True
    )

    # Satellite selection
    selected_name = st.selectbox("Select satellite for detailed view", df_satellites['Name'].tolist())
    selected_row = df_satellites[df_satellites['Name'] == selected_name].iloc[0]
    selected_id = selected_row['ID']

    # -------------------------------------------------------------------
    # Detailed view for selected satellite
    # -------------------------------------------------------------------
    with st.spinner(f"Fetching detailed track and passes for {selected_name}..."):
        details = fetch_satellite_details(selected_id, api_key, seconds=7200)

    if details:
        current = details['current']
        track = details['track']
        sat_name = details['satname']

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

        # Map with ground track
        st.subheader("🗺️ Current Position & Predicted Ground Track (next 2 hours)")
        track_lons = [p['satlongitude'] for p in track]
        track_lats = [p['satlatitude'] for p in track]

        fig = go.Figure()
        fig.add_trace(go.Scattergeo(
            lon=track_lons,
            lat=track_lats,
            mode='lines',
            line=dict(width=1, color='rgba(100, 200, 255, 0.7)'),
            name='Predicted Track'
        ))
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
        passes = fetch_passes(selected_id, user_lat, user_lon, api_key, days=2)
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

        # Download report for selected satellite
        report_text = f"""
SATELLITE REPORT
================
Name: {sat_name}
ID: {selected_id}
Current position:
  Latitude: {lat:.5f}°
  Longitude: {lon:.5f}°
  Altitude: {alt:.1f} km
  Speed: {vel:.2f} km/s
  Last update: {timestamp}

Ground track: {len(track)} predicted positions over the next 2 hours.
Pass predictions over ({user_lat}, {user_lon}): {'See table above' if passes else 'None in next 2 days.'}
"""
        st.download_button(
            label="📥 Download Report (TXT)",
            data=report_text,
            file_name=f"{sat_name}_report.txt",
            mime="text/plain",
            use_container_width=True
        )
    else:
        st.error(f"Could not retrieve detailed data for {selected_name}.")

# Auto‑refresh script
if auto_refresh:
    st.markdown(
        f"""
        <meta http-equiv="refresh" content="{refresh_sec}">
        """,
        unsafe_allow_html=True
    )
