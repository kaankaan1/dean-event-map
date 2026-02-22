import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import pgeocode
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import json

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Live Attendee Map", layout="wide")

# --- FIREBASE SETUP (CLOUD-COMPATIBLE SECURE CONNECTION) ---
# Checks if the app is running on Streamlit Cloud (uses secrets) or locally (uses json file)
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

# Initialize session state to prevent multiple submissions from the same user
if 'has_submitted' not in st.session_state:
    st.session_state.has_submitted = False

# --- SIDEBAR: HIDDEN ADMIN PANEL ---
with st.sidebar:
    st.header("🔒 Admin Access")
    st.write("For event staff only.")
    admin_pass = st.text_input("Enter Password:", type="password")
    
    if admin_pass == "NorthBay2026":
        st.success("Unlocked!")
        
        # Fetch all data from Firestore
        attendees_ref = db.collection('attendees')
        docs = attendees_ref.stream()
        data_list = []
        for doc in docs:
            data_list.append(doc.to_dict())
        
        # Display download button if data exists
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
            
            # Wipe data functionality for resetting the map
            if st.button("🗑️ Wipe All Data (Reset Map)"):
                docs_to_delete = db.collection('attendees').stream()
                for doc in docs_to_delete:
                    doc.reference.delete()
                st.warning("All data has been deleted. Refreshing...")
                st.rerun()
        else:
            st.info("No attendees data yet.")

# --- MAIN PAGE UI ---
st.title("📍 Live Event Map")

if not st.session_state.has_submitted:
    st.markdown("Welcome! Please enter your postal code to see your region on the map.")
    col1, col2 = st.columns([3, 1])
    with col1:
        postal_code_input = st.text_input("Enter Canadian Postal Code (e.g., P1B 8G6):", max_chars=7)
    with col2:
        st.write("") 
        st.write("") 
        submit_button = st.button("Submit", use_container_width=True)

    if submit_button and postal_code_input:
        clean_code = postal_code_input.replace(" ", "").upper()
        if len(clean_code) >= 3:
            fsa_code = clean_code[:3]
            nomi = pgeocode.Nominatim('ca')
            
            # STEP 1: Smart Lookup - Try the full 6-digit code first for high precision (Crucial for rural P0H codes)
            location_data = nomi.query_postal_code(clean_code)
            
            # STEP 2: Fallback - If the full 6-digit code is not found, try the first 3 digits (FSA)
            if str(location_data.latitude) == 'nan':
                location_data = nomi.query_postal_code(fsa_code)
            
            if str(location_data.latitude) != 'nan':
                lat = float(location_data.latitude)
                lon = float(location_data.longitude)
                city_name = str(location_data.place_name)
                
                # Save the validated data to Firestore
                db.collection('attendees').document().set({
                    "lat": lat, "lon": lon, "city": city_name,
                    "fsa": fsa_code, "full_code": clean_code 
                })
                
                st.session_state.has_submitted = True
                st.rerun() 
            else:
                st.error("Postal code not found. Please check and try again.")
        else:
            st.error("Please enter a valid postal code (at least 3 characters).")
else:
    # Success message after submission
    st.success("🎉 Thank you! Your location has been added to the map.")
    st.info("Look at the screen to see your dot appear!")

# --- MAP RENDERING ---
m = folium.Map(location=DEFAULT_COORDS, zoom_start=7)

# Smart Clustering: Radius reduced to 35 to prevent distant cities from merging
marker_cluster = MarkerCluster(maxClusterRadius=35).add_to(m)

# Retrieve and plot all attendee markers
attendees_ref = db.collection('attendees')
docs = attendees_ref.stream()

for doc in docs:
    data = doc.to_dict()
    folium.Marker(
        location=[data["lat"], data["lon"]],
        popup=data["city"],
        tooltip="Attendee"
    ).add_to(marker_cluster)

st_folium(m, width=1000, height=600)