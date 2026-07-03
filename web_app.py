import streamlit as st
import requests
from io import BytesIO
from PIL import Image
from google import genai
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
import pandas as pd

# ==========================================
# PAGE CONFIG & SETUP
# ==========================================
st.set_page_config(page_title="Geo-Business Feasibility Tool", layout="wide")
st.title("🗺️ AI-Powered Business Feasibility Analyzer")
st.write("Determine the business potential of any location using live data and satellite imagery.")

# Sidebar for API Keys and Settings
st.sidebar.header("🔑 API Credentials")
google_maps_key = st.sidebar.text_input("Google Maps API Key", type="password")
gemini_key = st.sidebar.text_input("Gemini API Key", type="password")

st.sidebar.header("⚙️ Parameters")
business_type = st.sidebar.selectbox("Business Type", ["cafe", "restaurant", "grocery store", "gym", "laundry"])
radius = st.sidebar.slider("Search Radius (Meters)", min_value=100, max_value=2000, value=500, step=100)

# Map Visualization Layers Control Panel
st.sidebar.header("🎨 Map Layers")
map_view_type = st.sidebar.radio("Competitor Overlay Style", ["Glowing Heatmap Cluster", "Individual Pin Markers", "Hide Overlays"])

# Initialize Essential Session States
if "lat" not in st.session_state:
    st.session_state.lat = 40.7128
if "lng" not in st.session_state:
    st.session_state.lng = -74.0060
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None
if "benchmarked_sites" not in st.session_state:
    st.session_state.benchmarked_sites = []

# NEW: Keep competitor geometry points cached to render live overlays dynamically
if "cached_competitor_coords" not in st.session_state:
    st.session_state.cached_competitor_coords = []

# ==========================================
# EXTRACTION HELPER FUNCTIONS
# ==========================================
def get_competitor_details(lat, lng, biz_type, radius, key):
    """Fetches up to 20 competitors including names and exact geographic coordinates."""
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {"location": f"{lat},{lng}", "radius": radius, "keyword": biz_type, "key": key}
    try:
        response = requests.get(url, params=params).json()
        if "error_message" in response:
            st.error(f"Google Places Error: {response['error_message']}")
            return 0, [], []
        
        results = response.get("results", [])
        
        names = [r.get("name") for r in results[:5]]
        coords = []
        for r in results:
            loc = r.get("geometry", {}).get("location", {})
            if loc.get("lat") and loc.get("lng"):
                coords.append([loc["lat"], loc["lng"]])
                
        return len(results), names, coords
    except Exception as e:
        st.error(f"Error fetching Places data: {e}")
        return 0, [], []

def get_satellite_image(lat, lng, key):
    url = "https://maps.googleapis.com/maps/api/staticmap"
    params = {
        "center": f"{lat},{lng}",
        "zoom": "17",
        "size": "640x640",
        "maptype": "satellite",
        "markers": f"color:red|{lat},{lng}",
        "key": key
    }
    try:
        response = requests.get(url, params=params)
        if "image" not in response.headers.get("Content-Type", ""):
            st.error(f"Failed to fetch image. API returned: {response.text}")
            return None
        return Image.open(BytesIO(response.content))
    except Exception as e:
        st.error(f"Error fetching satellite imagery: {e}")
        return None

def analyze_feasibility(image, comp_count, comp_names, biz_type, rad, g_key):
    try:
        client = genai.Client(api_key=g_key)
        prompt = f"""
        You are an expert GIS and commercial real estate analyst evaluating a location for a new {biz_type}.
        
        DATA PROVIDED:
        - Competitor count within {rad} meters: {comp_count}
        - Sample of nearby competitors: {', '.join(comp_names) if comp_names else 'None found'}
        
        VISUAL ANALYSIS REQUEST:
        Look at the provided satellite image. The proposed site is marked with a RED pin in the center.
        Evaluate the neighborhood layout for:
        1. Infrastructure & Connectivity (roads, pedestrian paths, parking).
        2. Environmental Factors (red flags like massive industrial areas, dumpyards, open drains, or blockages).
        3. Foot Traffic Anchors (malls, colleges, offices).
        
        CRITICAL FORMATTING INSTRUCTIONS:
        At the very beginning of your response, provide two hidden metric lines formatted exactly like this for extraction:
        [RATING]: High/Medium/Low
        [FLAG]: Your one-sentence primary constraint or red flag
        
        Then continue with a concise, bulleted explanation of your reasoning using Markdown formatting.
        """
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[image, prompt]
        )
        return response.text
    except Exception as e:
        st.error(f"Gemini API Error: {e}")
        return None

# ==========================================
# INTERACTIVE MAP INPUT SECTION
# ==========================================
st.subheader("🗺️ 1. Select Your Target Location")
st.write("Click anywhere on the map below to drop a pin. Competitor maps update dynamically when you run the feasibility analysis.")

# Build the map object dynamically from current session state
m = folium.Map(location=[st.session_state.lat, st.session_state.lng], zoom_start=14)

# Draw radius boundary circle layout helper
folium.Circle(
    radius=radius,
    location=[st.session_state.lat, st.session_state.lng],
    color="blue",
    fill=True,
    fill_opacity=0.08,
    weight=1
).add_to(m)

# Target pinpoint marker layout configuration
folium.Marker(
    [st.session_state.lat, st.session_state.lng], 
    tooltip="Target Site Selection", 
    icon=folium.Icon(color="red", icon="info-sign")
).add_to(m)

# ------------------------------------------
# PROCESS DYNAMIC ADVANCED MAP LAYERS
# ------------------------------------------
if st.session_state.cached_competitor_coords and map_view_type != "Hide Overlays":
    if map_view_type == "Glowing Heatmap Cluster":
        # Generate the dynamic competition overlay density heatmap
        HeatMap(st.session_state.cached_competitor_coords, radius=25, blur=15, min_opacity=0.4).add_to(m)
    elif map_view_type == "Individual Pin Markers":
        # Draw detailed separate markers
        for coord in st.session_state.cached_competitor_coords:
            folium.CircleMarker(
                location=coord,
                radius=6,
                color="orange",
                fill=True,
                fill_color="yellow",
                fill_opacity=0.7,
                tooltip=f"Nearby {business_type.capitalize()}"
            ).add_to(m)

# Render core interactive canvas
map_data = st_folium(
    m,
    height=450,
    width=None,
    use_container_width=True,
    returned_objects=["last_clicked"],
    key="interactive_map_final"
)

if map_data and map_data.get("last_clicked"):
    click_lat = round(map_data["last_clicked"]["lat"], 6)
    click_lng = round(map_data["last_clicked"]["lng"], 6)
    
    if click_lat != st.session_state.lat or click_lng != st.session_state.lng:
        st.session_state.lat = click_lat
        st.session_state.lng = click_lng
        # Clear old geometry points when target moves to prevent invalid overlay rendering
        st.session_state.cached_competitor_coords = [] 
        st.rerun()

# Text layout coordinate data entry blocks
col1, col2 = st.columns(2)
with col1:
    st.number_input("Selected Latitude", format="%.6f", key="lat")
with col2:
    st.number_input("Selected Longitude", format="%.6f", key="lng")

# ==========================================
# TRIGGER RUN
# ==========================================
st.write("---")
if st.button("🚀 Run Feasibility Analysis", type="primary", use_container_width=True):
    if not google_maps_key or not gemini_key:
        st.warning("Please enter both API keys in the sidebar to proceed.")
    else:
        with st.spinner("Fetching map layers and running AI model analysis..."):
            
            # Upgraded call pulls down positional arrays alongside metric targets
            comp_count, comp_names, comp_coords = get_competitor_details(
                st.session_state.lat, st.session_state.lng, business_type, radius, google_maps_key
            )
            
            # Cache coordinate parameters into state vault for folium layer redraw access
            st.session_state.cached_competitor_coords = comp_coords
            
            sat_img = get_satellite_image(st.session_state.lat, st.session_state.lng, google_maps_key)
            
            if sat_img:
                report = analyze_feasibility(sat_img, comp_count, comp_names, business_type, radius, gemini_key)
                
                rating = "Unknown"
                flag = "None highlighted"
                for line in report.split("\n"):
                    if line.startswith("[RATING]:"):
                        rating = line.replace("[RATING]:", "").strip()
                    if line.startswith("[FLAG]:"):
                        flag = line.replace("[FLAG]:", "").strip()

                st.session_state.analysis_results = {
                    "lat": st.session_state.lat,
                    "lng": st.session_state.lng,
                    "biz_type": business_type,
                    "sat_img": sat_img,
                    "comp_count": comp_count,
                    "comp_names": comp_names,
                    "report": report,
                    "rating": rating,
                    "flag": flag
                }
                st.rerun()
            else:
                st.error("Could not generate AI report because the satellite imagery failed to load.")

# ==========================================
# RENDER CURRENT ANALYSIS & SAVE INTERACTION
# ==========================================
if st.session_state.analysis_results:
    res = st.session_state.analysis_results
    
    save_col1, save_col2 = st.columns([3, 1])
    with save_col1:
        site_name_input = st.text_input("🏷️ Give this site a name to save it:", value=f"Site ({res['lat']}, {res['lng']})")
    with save_col2:
        st.write("##") 
        if st.button("📥 Save to Benchmarks", use_container_width=True):
            if any(site['name'] == site_name_input for site in st.session_state.benchmarked_sites):
                st.warning("A site with this name already exists in your benchmarking deck.")
            else:
                st.session_state.benchmarked_sites.append({
                    "name": site_name_input,
                    "lat_lng": f"{res['lat']}, {res['lng']}",
                    "biz_type": res["biz_type"],
                    "comp_count": f"{res['comp_count']} stores",
                    "rating": res["rating"],
                    "flag": res["flag"]
                })
                st.success(f"Saved '{site_name_input}' to Dashboard!")
                st.rerun()

    st.write("---")
    layout_col1, layout_col2 = st.columns([1, 1])
    
    with layout_col1:
        st.subheader("📍 Visual Data Capture")
        if res["sat_img"]:
            st.image(res["sat_img"], caption="Google Earth Satellite View (Analyzed Image)", use_container_width=True)
        
        st.metric(label="Competitor Density", value=f"{res['comp_count']} {res['biz_type']}(s)")
        if res["comp_names"]:
            st.write("**Nearby Competitors:**", ", ".join(res["comp_names"]))
    
    with layout_col2:
        st.subheader("🤖 AI Feasibility Report")
        if res["report"]:
            clean_report = res["report"].replace(f"[RATING]: {res['rating']}", "").replace(f"[FLAG]: {res['flag']}", "").strip()
            st.markdown(clean_report)

# ==========================================
# BENCHMARKING DASHBOARD SECTION
# ==========================================
if st.session_state.benchmarked_sites:
    st.write("---")
    st.header("📊 A/B Testing & Comparison Dashboard")
    
    df_compare = pd.DataFrame(st.session_state.benchmarked_sites)
    df_compare = df_compare.set_index("name").T
    st.dataframe(df_compare, use_container_width=True)
    
    if st.button("🗑️ Clear Dashboard Deck", type="secondary"):
        st.session_state.benchmarked_sites = []
        st.session_state.cached_competitor_coords = []
        st.rerun()