import streamlit as st
import requests
from io import BytesIO
from PIL import Image
from google import genai
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
import pandas as pd
import os

# ==========================================
# SECRETS LOADING (HYBRID PATTERN)
# ==========================================
if "GOOGLE_MAPS_KEY" in os.environ and "GEMINI_KEY" in os.environ:
    google_maps_key = os.environ.get("GOOGLE_MAPS_KEY")
    gemini_key = os.environ.get("GEMINI_KEY")
elif "GOOGLE_MAPS_KEY" in st.secrets and "GEMINI_KEY" in st.secrets:
    google_maps_key = st.secrets["GOOGLE_MAPS_KEY"]
    gemini_key = st.secrets["GEMINI_KEY"]
else:
    st.error("🔒 Security Error: API credentials could not be loaded from the environment.")
    st.stop()

# ==========================================
# PAGE CONFIG & BRANDING SETUP
# ==========================================
st.set_page_config(
    page_title="Geo-Business Feasibility Tool", 
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Elegant CSS Injection for Styling (Optimized for Dark Theme Contrast)
# Custom Elegant CSS Injection (Midnight Blue & Vibrant Teal Aesthetic)
st.markdown("""
    <style>
        /* Main Application Base Foundation Overrides */
        .stApp {
            background-color: #0b111e !important;
        }
        .block-container { 
            padding-top: 2rem; 
            padding-bottom: 2rem; 
        }
        
        /* Sidebar Restyling Container */
        section[data-testid="stSidebar"] {
            background-color: #0d1527 !important;
            border-right: 1px solid #1e2d4a;
        }

        /* Metric Cards: Crisp Slate Grey with High-Contrast Text Layout */
        .stMetric { 
            background-color: #162238 !important; 
            padding: 18px !important; 
            border-radius: 12px !important; 
            border: 1px solid #223454 !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .stMetric label {
            color: #8da2fb !important;
            font-weight: 600 !important;
            letter-spacing: 0.5px;
        }
        div[data-testid="stMetricValue"] {
            color: #00f2fe !important;
            font-weight: 700 !important;
        }
        
        /* Expander Containers: Seamless Indigo-Blue Structural Cards */
        div[data-testid="stExpander"] { 
            background-color: #131d31 !important; 
            border-radius: 10px !important; 
            border: 1px solid #1e2d4a !important;
            box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        }
        div[data-testid="stExpander"] summary {
            font-weight: 600 !important;
            color: #ffffff !important;
        }
        div[data-testid="stExpander"] p, div[data-testid="stExpander"] label {
            color: #e2e8f0 !important;
        }

        /* Typography Global Structural Controls */
        h1, h2, h3, h4, h5, h6 {
            color: #ffffff !important;
        }
        p, span, li {
            color: #cbd5e1 !important;
        }

        /* Native Streamlit Container Visual Blocks */
        div[data-testid="element-container"] div[data-theme="light"] {
            background-color: #131d31 !important;
            border: 1px solid #1e2d4a !important;
        }
    </style>
""", unsafe_allow_html=True)

# Main Dashboard Header Block
st.title("🗺️ AI-Powered Business Feasibility Analyzer")
st.markdown("##### *Transforming spatial geographic data into executive site-selection decisions.*")
st.write("Drop a target pin anywhere on the world map to dynamically calculate competitor cluster densities, extract environmental context via satellite intelligence, and receive structured AI risk reports.")

# ==========================================
# SIDEBAR CONTROL RIG
# ==========================================
st.sidebar.image("https://img.icons8.com/fluent/96/000000/map-marker.png", width=60)
st.sidebar.markdown("### **Control Console**")
st.sidebar.write("Configure your dynamic simulation rules below.")

with st.sidebar.expander("🎯 Target Configuration", expanded=True):
    business_type = st.selectbox("Target Business Type", ["cafe", "restaurant", "grocery store", "gym", "laundry"])
    radius = st.slider("Search Boundary Radius (M)", min_value=100, max_value=2000, value=500, step=100)

with st.sidebar.expander("🎨 Map Visualization Layers", expanded=True):
    map_view_type = st.radio("Competitor Overlay Style", ["Glowing Heatmap Cluster", "Individual Pin Markers", "Hide Overlays"])

st.sidebar.markdown("---")
st.sidebar.caption("⚡ Powered by Google Maps & Gemini 2.5 Flash")

# Initialize Essential Session States
if "lat" not in st.session_state:
    st.session_state.lat = 40.7128
if "lng" not in st.session_state:
    st.session_state.lng = -74.0060
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None
if "benchmarked_sites" not in st.session_state:
    st.session_state.benchmarked_sites = []
if "cached_competitor_coords" not in st.session_state:
    st.session_state.cached_competitor_coords = []

# ==========================================
# EXTRACTION HELPER FUNCTIONS
# ==========================================
def get_competitor_details(lat, lng, biz_type, radius, key):
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
# INTERACTIVE MAP CANVAS SECTION
# ==========================================
st.markdown("### 📍 Geographic Pinpoint")
st.write("Navigate the map canvas below and drop your target site marker. The framework handles dynamic state redraws automatically.")

m = folium.Map(location=[st.session_state.lat, st.session_state.lng], zoom_start=14)

folium.Circle(
    radius=radius,
    location=[st.session_state.lat, st.session_state.lng],
    color="#1E88E5",
    fill=True,
    fill_opacity=0.08,
    weight=1.5
).add_to(m)

folium.Marker(
    [st.session_state.lat, st.session_state.lng], 
    tooltip="Target Location Center", 
    icon=folium.Icon(color="red", icon="screenshot", prefix="fa")
).add_to(m)

# Process Dynamic Overlay Generation
if st.session_state.cached_competitor_coords and map_view_type != "Hide Overlays":
    if map_view_type == "Glowing Heatmap Cluster":
        HeatMap(st.session_state.cached_competitor_coords, radius=25, blur=15, min_opacity=0.4).add_to(m)
    elif map_view_type == "Individual Pin Markers":
        for coord in st.session_state.cached_competitor_coords:
            folium.CircleMarker(
                location=coord,
                radius=6,
                color="#FB8C00",
                fill=True,
                fill_color="#FFB300",
                fill_opacity=0.8,
                tooltip=f"Competitor Area Location"
            ).add_to(m)

# Render main canvas element
map_data = st_folium(
    m,
    height=480,
    width=None,
    use_container_width=True,
    center=[st.session_state.lat, st.session_state.lng],
    returned_objects=["last_clicked"],
    key="interactive_map_final"
)

# Intercept and synchronize new target selection positions
if map_data and map_data.get("last_clicked"):
    click_lat = round(map_data["last_clicked"]["lat"], 6)
    click_lng = round(map_data["last_clicked"]["lng"], 6)
    
    if click_lat != st.session_state.lat or click_lng != st.session_state.lng:
        st.session_state.lat = click_lat
        st.session_state.lng = click_lng
        st.session_state.cached_competitor_coords = [] 
        st.session_state.analysis_results = None 
        st.rerun()

# Refined Coordination Entry Panel Layout
col_coord1, col_coord2 = st.columns(2)
with col_coord1:
    st.number_input("Selected Site Latitude", format="%.6f", key="lat")
with col_coord2:
    st.number_input("Selected Site Longitude", format="%.6f", key="lng")

# Execution Anchor System Action Button
st.write(" ")
if st.button("🚀 Run Comprehensive Feasibility Analysis", type="primary", use_container_width=True):
    with st.spinner("Compiling structural GIS analytics and generating AI context report..."):
        comp_count, comp_names, comp_coords = get_competitor_details(
            st.session_state.lat, st.session_state.lng, business_type, radius, google_maps_key
        )
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
            st.error("Engine Timeout: Satellite matrix acquisition failed.")

# ==========================================
# RENDER REPORT ENGINE CARDS
# ==========================================
if st.session_state.analysis_results:
    res = st.session_state.analysis_results
    st.write("---")
    
    # Save Action Sub-Header System Card
    save_box = st.container()
    save_col1, save_col2 = save_box.columns([3, 1])
    with save_col1:
        site_name_input = st.text_input("🏷️ Benchmarking Tag", value=f"Site ({res['lat']}, {res['lng']})", help="Give this site a custom name to review it inside the cross-comparison dashboard below.")
    with save_col2:
        st.write("##") 
        if st.button("📥 Save Site to Dashboard", use_container_width=True):
            if any(site['name'] == site_name_input for site in st.session_state.benchmarked_sites):
                st.warning("Tag Collision: A location already exists with that label name.")
            else:
                st.session_state.benchmarked_sites.append({
                    "name": site_name_input,
                    "lat_lng": f"{res['lat']}, {res['lng']}",
                    "biz_type": res["biz_type"].capitalize(),
                    "comp_count": f"{res['comp_count']} Units",
                    "rating": res["rating"],
                    "flag": res["flag"]
                })
                st.success(f"Site '{site_name_input}' added successfully!")
                st.rerun()

    st.write(" ")
    layout_col1, layout_col2 = st.columns([1, 1.2], gap="large")
    
    with layout_col1:
        st.markdown("### 📊 Local Environment Captures")
        if res["sat_img"]:
            st.image(res["sat_img"], caption="Processed high-res Earth Observation Matrix Center", use_container_width=True)
        
        # Micro Metric Grid Cards Layout
        m_col1, m_col2 = st.columns(2)
        with m_col1:
            st.metric(label="Competitor Count", value=res['comp_count'])
        with m_col2:
            st.metric(label="Feasibility Status", value=res['rating'])
            
        if res["comp_names"]:
            with st.expander("🔍 Identified Competitor Brands", expanded=True):
                st.write(", ".join(res["comp_names"]))
    
    with layout_col2:
        st.markdown("### 🤖 Computer-Vision Feasibility Insights")
        if res["report"]:
            clean_report = res["report"].replace(f"[RATING]: {res['rating']}", "").replace(f"[FLAG]: {res['flag']}", "").strip()
            # Clean native card container
            with st.container(border=True):
                st.markdown(clean_report)

# ==========================================
# EXECUTIVE CROSS-BENCHMARK DECK SECTION
# ==========================================
if st.session_state.benchmarked_sites:
    st.write("---")
    st.markdown("### 📊 Side-by-Side Executive Benchmarking")
    st.write("Compare saved geographic options side-by-side to optimize site prioritization and deployment strategies.")
    
    df_compare = pd.DataFrame(st.session_state.benchmarked_sites)
    df_compare = df_compare.set_index("name").T
    
    # Styled matrix layout display block configuration
    st.dataframe(
        df_compare, 
        use_container_width=True,
        column_config={"name": st.column_config.Column(width="medium")}
    )
    
    if st.button("🗑️ Clear Benchmarking Dashboard", type="secondary", use_container_width=True):
        st.session_state.benchmarked_sites = []
        st.session_state.cached_competitor_coords = []
        st.rerun()