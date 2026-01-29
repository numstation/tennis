"""
Ultimate HK Tennis Court Sniper — Streamlit Cloud Compatible
Cascading filters + browser (Web) notifications. No plyer.
"""

import json
import time
import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="HK Tennis Sniper", layout="wide")

# Auto-refresh every 30 minutes so deployed app gets new data
st_autorefresh(interval=30 * 60 * 1000, key="data_refresh")

API_URL = "https://data.smartplay.lcsd.gov.hk/rest/cms/api/v1/publ/contents/open-data/tennis/file"
NOTIFICATION_ICON = "https://img.icons8.com/emoji/48/000000/tennis-icon.png"

DISPLAY_COLS = [
    "District_Name_EN",
    "Venue_Name_EN",
    "Available_Date",
    "Session_Start_Time",
    "Available_Courts",
]


def extract_records(raw):
    """Handle API response: may be a list or a dict with data/contents/result."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("data", "contents", "result", "items", "records"):
            if key in raw and isinstance(raw[key], list):
                return raw[key]
    return []


def html_notification_permission_button():
    """Step A: A real button — browser only shows 'Allow' popup when user clicks (user gesture)."""
    return """
    <div style="margin: 8px 0;">
        <button type="button" id="btn-allow-notifications" style="
            padding: 8px 14px; background: #ff4b4b; color: white; border: none; border-radius: 6px;
            font-size: 14px; cursor: pointer; font-weight: 500;
        ">🔔 Allow browser notifications</button>
    </div>
    <script>
    (function() {
        var btn = document.getElementById("btn-allow-notifications");
        if (!btn) return;
        btn.onclick = function() {
            if ("Notification" in window && Notification.permission === "default") {
                Notification.requestPermission();
            } else if (Notification.permission === "granted") {
                alert("Notifications already allowed.");
            } else {
                alert("Notifications were blocked. Enable them in your browser settings for this site.");
            }
        };
    })();
    </script>
    """


def js_show_notification(venue_name: str):
    """Step B: Show browser notification when court is found. Body/venue safely escaped."""
    body = f"Go book at {venue_name} now!"
    body_escaped = json.dumps(body)  # safe for embedding in JS string
    return f"""
    <script>
    (function() {{
        if ("Notification" in window && Notification.permission === "granted") {{
            new Notification("🎾 Court Found!", {{
                body: {body_escaped},
                icon: "{NOTIFICATION_ICON}"
            }});
        }}
    }})();
    </script>
    """


@st.cache_data(ttl=1800)
def fetch_data():
    """Fetch JSON from HK SmartPlay API."""
    try:
        r = requests.get(API_URL, timeout=15)
        r.raise_for_status()
        raw = r.json()
        return extract_records(raw)
    except requests.RequestException:
        return None
    except (ValueError, TypeError):
        return None


st.title("🎾 Ultimate HK Tennis Court Sniper")
st.caption(f"Last updated: **{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**")

# --- Refresh Data ---
if st.button("🔄 Refresh Data"):
    fetch_data.clear()
    st.rerun()

# --- Fetch and validate ---
raw_records = fetch_data()

if raw_records is None:
    st.error("Error fetching data from the API. Check your connection and try again.")
    st.stop()

if not raw_records:
    st.warning("No data loaded from the API.")
    st.stop()

# --- Load into DataFrame and clean ---
df = pd.DataFrame(raw_records)

# CRITICAL: Available_Courts is STRING from API → convert to int
df["Available_Courts"] = pd.to_numeric(df["Available_Courts"], errors="coerce").fillna(0).astype(int)

# Filter out rows where Available_Courts <= 0
available_df = df[df["Available_Courts"] > 0].copy()

if available_df.empty:
    st.info("No courts with availability at the moment. Try again later.")
    st.stop()

# ========== 🎯 Sniper Settings (Cascading Filters) ==========
st.sidebar.header("🎯 Sniper Settings")

# Step 1: District (one or multiple)
all_districts = sorted(available_df["District_Name_EN"].dropna().unique())
selected_districts = st.sidebar.multiselect(
    "Step 1: District",
    options=all_districts,
    default=all_districts[:1] if all_districts else [],
    key="snipe_district",
)

# Step 2: Venue — only from selected district(s)
if selected_districts:
    scope_df = available_df[available_df["District_Name_EN"].isin(selected_districts)]
else:
    scope_df = available_df
venue_options = sorted(scope_df["Venue_Name_EN"].dropna().unique())
selected_venues = st.sidebar.multiselect(
    "Step 2: Venue",
    options=venue_options,
    default=venue_options[:3] if len(venue_options) <= 5 else [],
    key="snipe_venue",
)

# Step 3: Date — based on district + venue filter
if selected_venues:
    scope_df = scope_df[scope_df["Venue_Name_EN"].isin(selected_venues)]
date_options = sorted(scope_df["Available_Date"].dropna().unique())
selected_dates = st.sidebar.multiselect(
    "Step 3: Date",
    options=date_options,
    default=date_options[:5] if len(date_options) <= 10 else [],
    key="snipe_date",
)

# Step 4: Time — based on previous filters
if selected_dates:
    scope_df = scope_df[scope_df["Available_Date"].isin(selected_dates)]
time_options = sorted(scope_df["Session_Start_Time"].dropna().unique())
selected_times = st.sidebar.multiselect(
    "Step 4: Time (e.g. 19:00, 20:00)",
    options=time_options,
    default=time_options,
    key="snipe_time",
)

# --- Build final filtered DataFrame from ALL selections ---
filtered_df = available_df.copy()
if selected_districts:
    filtered_df = filtered_df[filtered_df["District_Name_EN"].isin(selected_districts)]
if selected_venues:
    filtered_df = filtered_df[filtered_df["Venue_Name_EN"].isin(selected_venues)]
if selected_dates:
    filtered_df = filtered_df[filtered_df["Available_Date"].isin(selected_dates)]
if selected_times:
    filtered_df = filtered_df[filtered_df["Session_Start_Time"].isin(selected_times)]

# --- 🔴 Enable Live Monitor ---
st.sidebar.divider()
enable_live_monitor = st.sidebar.checkbox("🔴 Enable Live Monitor", value=False, key="live_monitor")

# --- Allow notifications: must be a real click (user gesture) for browser to show "Allow" popup ---
st.sidebar.caption("To get desktop alerts when a court is found:")
components.html(html_notification_permission_button(), height=70)

if "last_checked" not in st.session_state:
    st.session_state.last_checked = None
st.session_state.last_checked = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# --- Found logic & alerts (when Live Monitor ON and filtered table NOT empty) ---
target_found = not filtered_df.empty

if enable_live_monitor and target_found:
    st.balloons()
    st.toast("🎯 Target Acquired!")
    # Browser notification (only works if user previously clicked "Allow browser notifications")
    venue_names = filtered_df["Venue_Name_EN"].dropna().unique().tolist()
    msg_venue = venue_names[0] if venue_names else "Court"
    components.html(js_show_notification(msg_venue), height=0)

# --- Main area: filtered table ---
cols_present = [c for c in DISPLAY_COLS if c in filtered_df.columns]

if enable_live_monitor:
    st.caption(f"Last checked at **{st.session_state.last_checked}**")

if filtered_df.empty:
    st.info("No slots match your sniper settings. Widen filters or enable Live Monitor to re-check every 60s.")
    if enable_live_monitor:
        st.warning("Next check in 60 seconds...")
        time.sleep(60)
        st.rerun()
else:
    st.subheader(f"Found {len(filtered_df)} Available Slots!")
    st.dataframe(filtered_df[cols_present], use_container_width=True)
    st.success("✅ Go to SmartPlay to book now.")

st.sidebar.caption("💡 Click **Allow browser notifications** above, then choose **Allow** in the browser popup.")
