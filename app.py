import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import json
import requests

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Live Attendee Map", layout="wide")

# --- CSS HACKS: HIDE STREAMLIT BRANDING ---
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;} /* Hides the top-right hamburger menu */
            footer {visibility: hidden;}    /* Hides the 'Hosted with Streamlit' footer */
            header {visibility: hidden;}    /* Hides the top header padding */
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# --- FIREBASE SETUP ---
if not firebase_admin._apps:
    if 'firebase' in st.secrets:
        key_dict = json.loads(st.secrets["firebase"]["my_project_settings"])
        cred = credentials.Certificate(key_dict)
    else:
        cred = credentials.Certificate("firebase_key.json")
    
    firebase_admin.initialize_app(cred)

db = firestore.client()

# Default map center (North Bay, ON)
DEFAULT_COORDS = [46.3091, -79.4608]

if 'has_submitted' not in st.session_state:
    st.session_state.has_submitted = False

# --- SIDEBAR: HIDDEN ADMIN PANEL ---
with st.sidebar:
    st.header("🔒 Admin Access")
    st.write("For event staff only.")
    admin_pass = st.text_input("Enter Password:", type="password")
    
    if admin_pass == "NorthBay2026":
        st.success("Unlocked!")
        
        attendees_ref = db.collection('attendees')
        docs = attendees_ref.stream()
        data_list = []
        for doc in docs:
            data_list.append(doc.to_dict())
        
        if data_list:
            df = pd.DataFrame(data_list)
            df = df[['full_code', 'fsa', 'city', 'lat', 'lon']] 
            csv = df.to_csv(index=False).encode('utf-8')
            
            st.download_button(
                label="📥 Download Analytics (CSV)",
                data=csv,
                file_name='event_attendees.csv',
                mime='text/csv',
            )
            
            st.divider() 
            
            if st.button("🗑️ Wipe All Data (Reset Map)"):
                docs_to_delete = db.collection('attendees').stream()
                for doc in docs_to_delete:
                    doc.reference.delete()
                st.warning("All data has been deleted. Refreshing...")
                st.rerun()
        else:
            st.info("No attendees data yet.")

# --- MAIN PAGE UI ---
st.title("📍 What area are you coming in from?")

if not st.session_state.has_submitted:
    st.markdown("Enter your postal code and see how far our outdoor community reaches:")
    col1, col2 = st.columns([3, 1])
    with col1:
        postal_code_input = st.text_input("Canadian Postal Code (e.g., P1B 8G6):", max_chars=7)
    with col2:
        st.write("") 
        st.write("") 
        submit_button = st.button("Submit", use_container_width=True)

    if submit_button and postal_code_input:
        clean_code = postal_code_input.replace(" ", "").upper()
        if len(clean_code) >= 3:
            fsa_code = clean_code[:3]
            
            # --- GOOGLE MAPS API INTEGRATION ---
            try:
                api_key = st.secrets["GOOGLE_MAPS_API_KEY"]
                url = f"https://maps.googleapis.com/maps/api/geocode/json?address={clean_code},+Canada&key={api_key}"
                
                response = requests.get(url).json()
                
                if response['status'] == 'OK':
                    # Extract latitude and longitude from Google response
                    location = response['results'][0]['geometry']['location']
                    lat = location['lat']
                    lon = location['lng']
                    
                    # Extract city name from Google response
                    city_name = clean_code 
                    address_components = response['results'][0]['address_components']
                    for comp in address_components:
                        if "locality" in comp["types"] or "postal_town" in comp["types"]:
                            city_name = comp["long_name"]
                            break
                    
                    # Save attendee location to Firestore
                    db.collection('attendees').document().set({
                        "lat": lat, "lon": lon, "city": city_name,
                        "fsa": fsa_code, "full_code": clean_code 
                    })
                    
                    st.session_state.has_submitted = True
                    st.rerun() 
                else:
                    error_msg = response.get('error_message', 'No details provided by Google.')
                    st.error(f"Google API Error: {response['status']} - {error_msg}")
                    
            except Exception as e:
                st.error(f"There was an error connecting to the mapping service: {e}")
                
        else:
            st.error("Please enter a valid postal code (at least 3 characters).")
else:
    st.success("🎉 Thank you! Your location has been added to the map.")
    st.info("Look at the screen to see your dot appear!")

# --- MAP RENDERING ---
m = folium.Map(location=DEFAULT_COORDS, zoom_start=7)

marker_cluster = MarkerCluster(maxClusterRadius=35).add_to(m)

attendees_ref = db.collection('attendees')
docs = attendees_ref.stream()

for doc in docs:
    data = doc.to_dict()
    folium.Marker(
        location=[data["lat"], data["lon"]],
        popup=data["city"],
        tooltip="Attendee",
        icon=folium.Icon(color="blue", icon="map-pin", prefix="fa")
    ).add_to(marker_cluster)

st_folium(m, width=1000, height=600)