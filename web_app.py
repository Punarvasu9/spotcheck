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
    initial_sidebar_state="collapsed" # Collapsed by default to maximize mobile mapping viewport area
)

# Responsive Theme Layout CSS Grid Injection
st.markdown("""
    <style>
        /* Base Fluid Containers */
        .stApp { background-color: #0b111e !important; }
        .block-container { 
            padding-top: 1.5rem !important; 
            padding-bottom: 1.5rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        
        /* Unified Mobile Flex-Grid Layout Overrides */
        .responsive-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 1.5rem;
            width: 100%;
        }
        .grid-item-half { flex: 1 1 45%; min-width: 300px; }
        .grid-item-60 { flex: 1.2 1 55%; min-width: 320px; }
        .grid-item-40 { flex: 0.8 1 40%; min-width: 280px; }

        /* Metric Cards Touch optimizations */
        .stMetric { 
            background-color: #162238 !important; 
            padding: 16px !important; 
            border-radius: 12px !important; 
            border: 1px solid #223454 !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .stMetric label { color: #8da2fb !important; font-weight: 600 !important; }
        div[data-testid="stMetricValue"] { color: #00f2fe !important; font-weight: 700 !important; font-size: calc(1.5rem + 0.5vw) !important; }
        
        /* Expanders and Inputs */
        div[data-testid="stExpander"] { 
            background-color: #131d31 !important; 
            border-radius: 10px !important; 
            border: 1px solid #1e2d4a !important;
        }
        div[data-testid="stExpander"] summary { font-weight: 600 !important; color: #ffffff !important; }
        
        /* Typography Scalers */
        h1 { font-size: calc(1.8rem + 1vw) !important; color: #ffffff !important; }
        h2 { font-size: calc(1.4rem + 0.6vw) !important; color: #ffffff !important; }
        h3 { font-size: calc(1.1rem + 0.4vw) !important; color: #ffffff !important; }
        p, span, li, label { color: #cbd5e1 !important; }
        
        /* Mobile-Friendly Full-Width Action Buttons */
        div.stButton > button {
            width: 100% !important;
            padding: 0.6rem 1rem !important;
            font-size: 1rem !important;
        }
    </style>
""", unsafe_allow_html=True)

# Main Dashboard Header Block
st.title("🗺️ AI Business Feasibility Analyzer")
st.markdown("##### *Transforming spatial geographic data into executive site-selection decisions.*")

# ==========================================
# SIDEBAR CONTROL RIG
# ==========================================
st.sidebar.image("https://img.icons8.com/fluent/96/000000/map-marker.png", width=50)
st.sidebar.markdown("### **Control Console**")

with st.sidebar.expander("🎯 Target Configuration", expanded=True):
    business_type = st.selectbox("Target Business Type", ["cafe", "restaurant", "grocery store", "gym", "laundry"])
    radius = st.sidebar.slider("Search Boundary Radius (M)", min_value=100, max_value=2000, value=500, step=100)

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
        
        Look at the provided satellite image and evaluate neighborhood layout.
        Provide hidden metrics: [RATING]: High/Medium/Low and [FLAG]: text. Followed by concise markdown reasoning bullets.
        """
        response = client.models.generate_content(model='gemini-2.5-flash', contents=[image, prompt])
        return response.text
    except Exception as e:
        st.error(f"Gemini API Error: {e}")
        return None

# ==========================================
# INTERACTIVE MAP CANVAS SECTION
# ==========================================
st.markdown("### 📍 Geographic Pinpoint")
st.write("Tap/Click the map to place your target site marker.")

m = folium.Map(location=[st.session_state.lat, st.session_state.lng], zoom_start=14)

folium.Circle(
    radius=radius, location=[st.session_state.lat, st.session_state.lng],
    color="#1E88E5", fill=True, fill_opacity=0.08, weight=1.5
).add_to(m)

folium.Marker(
    [st.session_state.lat, st.session_state.lng], 
    icon=folium.Icon(color="red", icon="screenshot", prefix="fa")
).add_to(m)

if st.session_state.cached_competitor_coords and map_view_type != "Hide Overlays":
    if map_view_type == "Glowing Heatmap Cluster":
        HeatMap(st.session_state.cached_competitor_coords, radius=25, blur=15, min_opacity=0.4).add_to(m)
    elif map_view_type == "Individual Pin Markers":
        for coord in st.session_state.cached_competitor_coords:
            folium.CircleMarker(location=coord, radius=6, color="#FB8C00", fill=True, fill_color="#FFB300", fill_opacity=0.8).add_to(m)

# Interactive dynamic viewport mapping logic (Auto-scales layout height based on device category)
map_data = st_folium(
    m,
    height=380,
    width=None,
    use_container_width=True,
    center=[st.session_state.lat, st.session_state.lng],
    returned_objects=["last_clicked"],
    key="interactive_map_final"
)

if map_data and map_data.get("last_clicked"):
    click_lat = round(map_data["last_clicked"]["lat"], 6)
    click_lng = round(map_data["last_clicked"]["lng"], 6)
    if click_lat != st.session_state.lat or click_lng != st.session_state.lng:
        st.session_state.lat = click_lat
        st.session_state.lng = click_lng
        st.session_state.cached_competitor_coords = [] 
        st.session_state.analysis_results = None 
        st.rerun()

# Coordinates Input - Mobile stacked columns layout implementation
col_coord1, col_coord2 = st.columns([1, 1])
with col_coord1:
    st.number_input("Selected Site Latitude", format="%.6f", key="lat")
with col_coord2:
    st.number_input("Selected Site Longitude", format="%.6f", key="lng")

st.write(" ")
if st.button("🚀 Run Comprehensive Feasibility Analysis", type="primary", use_container_width=True):
    with st.spinner("Processing structural GIS analytics..."):
        comp_count, comp_names, comp_coords = get_competitor_details(st.session_state.lat, st.session_state.lng, business_type, radius, google_maps_key)
        st.session_state.cached_competitor_coords = comp_coords
        sat_img = get_satellite_image(st.session_state.lat, st.session_state.lng, google_maps_key)
        
        if sat_img:
            report = analyze_feasibility(sat_img, comp_count, comp_names, business_type, radius, gemini_key)
            rating, flag = "Unknown", "None highlighted"
            for line in report.split("\n"):
                if line.startswith("[RATING]:"): rating = line.replace("[RATING]:", "").strip()
                if line.startswith("[FLAG]:"): flag = line.replace("[FLAG]:", "").strip()

            st.session_state.analysis_results = {
                "lat": st.session_state.lat, "lng": st.session_state.lng, "biz_type": business_type,
                "sat_img": sat_img, "comp_count": comp_count, "comp_names": comp_names,
                "report": report, "rating": rating, "flag": flag
            }
            st.rerun()

# ==========================================
# RENDER REPORT ENGINE CARDS (RESPONSIVE)
# ==========================================
if st.session_state.analysis_results:
    res = st.session_state.analysis_results
    st.write("---")
    
    save_col1, save_col2 = st.columns([2, 1])
    with save_col1:
        site_name_input = st.text_input("🏷️ Benchmarking Tag", value=f"Site ({res['lat']}, {res['lng']})")
    with save_col2:
        st.write("##")
        if st.button("📥 Save Site to Dashboard", use_container_width=True):
            if not any(site['name'] == site_name_input for site in st.session_state.benchmarked_sites):
                st.session_state.benchmarked_sites.append({
                    "name": site_name_input, "lat_lng": f"{res['lat']}, {res['lng']}",
                    "biz_type": res["biz_type"].capitalize(), "comp_count": f"{res['comp_count']} Units",
                    "rating": res["rating"], "flag": res["flag"]
                })
                st.rerun()

    st.write(" ")
    
    # Adaptive Flex Container Injection for Side-by-Side (Desktop) or Stacked (Mobile) matching
    st.markdown('<div class="responsive-grid">', unsafe_allow_html=True)
    
    # Column Left Block Wrapper
    st.markdown('<div class="grid-item-40">', unsafe_allow_html=True)
    st.markdown("### 📊 Local Environment Captures")
    if res["sat_img"]:
        st.image(res["sat_img"], caption="Earth Observation Matrix", use_container_width=True)
    
    sub_m1, sub_m2 = st.columns(2)
    with sub_m1: st.metric(label="Competitor Count", value=res['comp_count'])
    with sub_m2: st.metric(label="Feasibility Status", value=res['rating'])
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Column Right Block Wrapper
    st.markdown('<div class="grid-item-60">', unsafe_allow_html=True)
    st.markdown("### 🤖 Feasibility Insights")
    if res["report"]:
        clean_report = res["report"].replace(f"[RATING]: {res['rating']}", "").replace(f"[FLAG]: {res['flag']}", "").strip()
        with st.container(border=True):
            st.markdown(clean_report)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# EXECUTIVE CROSS-BENCHMARK DECK SECTION
# ==========================================
if st.session_state.benchmarked_sites:
    st.write("---")
    st.markdown("### 📊 Side-by-Side Executive Benchmarking")
    df_compare = pd.DataFrame(st.session_state.benchmarked_sites).set_index("name").T
    st.dataframe(df_compare, use_container_width=True)
    
    if st.button("🗑️ Clear Benchmarking Dashboard", type="secondary", use_container_width=True):
        st.session_state.benchmarked_sites = []
        st.session_state.cached_competitor_coords = []
        st.rerun()