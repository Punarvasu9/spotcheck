import streamlit as st
import requests
from io import BytesIO
from PIL import Image
from google import genai

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

# Main Form Inputs
col1, col2 = st.columns(2)
with col1:
    lat = st.number_input("Latitude", value=40.7128, format="%.6f")
with col2:
    lng = st.number_input("Longitude", value=-74.0060, format="%.6f")

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def get_competitor_count(lat, lng, biz_type, radius, key):
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {"location": f"{lat},{lng}", "radius": radius, "keyword": biz_type, "key": key}
    try:
        response = requests.get(url, params=params).json()
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
        return Image.open(BytesIO(response.content))
    except Exception as e:
        st.error(f"Error fetching satellite imagery: {e}")
        return None

def analyze_feasibility(image, comp_count, comp_names, biz_type, rad, g_key):
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
    response = client.models.generate_content(model='gemini-2.5-flash', contents=[image, prompt])
    return response.text

# ==========================================
# TRIGGER RUN
# ==========================================
if st.button("🚀 Run Feasibility Analysis", type="primary"):
    if not google_maps_key or not gemini_key:
        st.warning("Please enter both API keys in the sidebar to proceed.")
    else:
        with st.spinner("Fetching map data and running AI analysis..."):
            
            # Create columns for layout
            layout_col1, layout_col2 = st.columns([1, 1])
            
            # Step 1 & 2: Get Map Data
            comp_count, comp_names = get_competitor_count(lat, lng, business_type, radius, google_maps_key)
            sat_img = get_satellite_image(lat, lng, google_maps_key)
            
            with layout_col1:
                st.subheader("📍 Visual Data Capture")
                if sat_img:
                    st.image(sat_img, caption="Google Earth Satellite View (Analyzed Image)", use_container_width=True)
                
                st.metric(label="Competitor Density", value=f"{comp_count} {business_type}(s)")
                if comp_names:
                    st.write("**Nearby Competitors:**", ", ".join(comp_names))
            
            with layout_col2:
                st.subheader("🤖 AI Feasibility Report")
                if sat_img:
                    report = analyze_feasibility(sat_img, comp_count, comp_names, business_type, radius, gemini_key)
                    st.markdown(report)
                else:
                    st.error("Could not generate AI report without the satellite imagery.")