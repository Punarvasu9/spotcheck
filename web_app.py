import streamlit as st
import requests
from io import BytesIO
from PIL import Image
from google import genai
import folium
from streamlit_folium import st_folium

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

# Initialize Session States with Default NYC values safely
if "lat" not in st.session_state:
    st.session_state.lat = 40.7128
if "lng" not in st.session_state:
    st.session_state.lng = -74.0060
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None

# ==========================================
# INTERACTIVE MAP INPUT SECTION
# ==========================================
st.subheader("🗺️ 1. Select Your Target Location")
st.write("Click anywhere on the map below to drop a pin on your target business location.")

# Build the map object dynamically from current session state
m = folium.Map(location=[st.session_state.lat, st.session_state.lng], zoom_start=14)
folium.Marker(
    [st.session_state.lat, st.session_state.lng], 
    tooltip="Target Site", 
    icon=folium.Icon(color="red", icon="info-sign")
).add_to(m)

# Render map layout, returning only the specific user data we need
map_data = st_folium(
    m,
    height=400,
    width=None,
    use_container_width=True,
    returned_objects=["last_clicked"],
    key="interactive_map_v4"
)

# Trap click event data changes and immediately map them to state
if map_data and map_data.get("last_clicked"):
    click_lat = round(map_data["last_clicked"]["lat"], 6)
    click_lng = round(map_data["last_clicked"]["lng"], 6)
    
    if click_lat != st.session_state.lat or click_lng != st.session_state.lng:
        st.session_state.lat = click_lat
        st.session_state.lng = click_lng
        st.rerun()

# Text layout fields are directly locked into state storage keys
col1, col2 = st.columns(2)
with col1:
    st.number_input("Selected Latitude", format="%.6f", key="lat")
with col2:
    st.number_input("Selected Longitude", format="%.6f", key="lng")


# ==========================================
# HELPER FUNCTIONS
# ==========================================
def get_competitor_count(lat, lng, biz_type, radius, key):
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {"location": f"{lat},{lng}", "radius": radius, "keyword": biz_type, "key": key}
    try:
        response = requests.get(url, params=params).json()
        if "error_message" in response:
            st.error(f"Google Places Error: {response['error_message']}")
            return 0, []
        results = response.get("results", [])
        return len(results), [r.get("name") for r in results[:5]]
    except Exception as e:
        st.error(f"Error fetching Places data: {e}")
        return 0, []

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
        
        Provide a final "Feasibility Rating" (High, Medium, or Low) with a concise, bulleted explanation of your reasoning. Use Markdown formatting.
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
# TRIGGER RUN
# ==========================================
st.write("---")
if st.button("🚀 Run Feasibility Analysis", type="primary", use_container_width=True):
    if not google_maps_key or not gemini_key:
        st.warning("Please enter both API keys in the sidebar to proceed.")
    else:
        with st.spinner("Fetching map data and running AI analysis..."):
            comp_count, comp_names = get_competitor_count(st.session_state.lat, st.session_state.lng, business_type, radius, google_maps_key)
            sat_img = get_satellite_image(st.session_state.lat, st.session_state.lng, google_maps_key)
            
            if sat_img:
                report = analyze_feasibility(sat_img, comp_count, comp_names, business_type, radius, gemini_key)
                st.session_state.analysis_results = {
                    "sat_img": sat_img,
                    "comp_count": comp_count,
                    "comp_names": comp_names,
                    "report": report
                }
            else:
                st.error("Could not generate AI report because the satellite imagery failed to load.")

# ==========================================
# RENDER LAYOUT FROM STATE
# ==========================================
if st.session_state.analysis_results:
    res = st.session_state.analysis_results
    
    st.write("---")
    layout_col1, layout_col2 = st.columns([1, 1])
    
    with layout_col1:
        st.subheader("📍 Visual Data Capture")
        if res["sat_img"]:
            st.image(res["sat_img"], caption="Google Earth Satellite View (Analyzed Image)", use_container_width=True)
        
        st.metric(label="Competitor Density", value=f"{res['comp_count']} {business_type}(s)")
        if res["comp_names"]:
            st.write("**Nearby Competitors:**", ", ".join(res["comp_names"]))
    
    with layout_col2:
        st.subheader("🤖 AI Feasibility Report")
        if res["report"]:
            st.markdown(res["report"])
        else:
            st.error("AI report compilation failed.")