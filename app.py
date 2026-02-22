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

# --- FIREBASE SETUP ---
if not firebase_admin._apps:
    if 'firebase' in st.secrets:
        key_dict = json.loads(st.secrets["firebase"]["my_project_settings"])
        cred = credentials.Certificate(key_dict)
    else:
        cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()
DEFAULT_COORDS = [46.3091, -79.4608]

if 'has_submitted' not in st.session_state:
    st.session_state.has_submitted = False

# --- SIDEBAR: ADMIN PANEL ---
with st.sidebar:
    st.header("🔒 Admin Access")
    admin_pass = st.text_input("Enter Password:", type="password")
    if admin_pass == "NorthBay2026":
        st.success("Unlocked!")
        attendees_ref = db.collection('attendees')
        docs = attendees_ref.stream()
        data_list = [doc.to_dict() for doc in docs]
        
        if data_list:
            df = pd.DataFrame(data_list)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Analytics (CSV)", data=csv, file_name='attendees.csv', mime='text/csv')
            if st.button("🗑️ Wipe All Data"):
                for doc in attendees_ref.stream(): doc.reference.delete()
                st.rerun()

# --- MAIN PAGE UI ---
st.title("📍 Live Event Map")

if not st.session_state.has_submitted:
    st.markdown("Welcome! Please enter your postal code to see your region on the map.")
    col1, col2 = st.columns([3, 1])
    with col1:
        postal_code_input = st.text_input("Enter Canadian Postal Code (e.g., P1B 8G6):", max_chars=7)
    with col2:
        st.write(""); st.write("")
        submit_button = st.button("Submit", use_container_width=True)

    if submit_button and postal_code_input:
        clean_code = postal_code_input.replace(" ", "").upper()
        if len(clean_code) >= 3:
            # KRITIK GUNCELLEME: Koordinat sorgusu için tam kodu (6 hane) kullanıyoruz
            nomi = pgeocode.Nominatim('ca')
            location_data = nomi.query_postal_code(clean_code)
            
            if str(location_data.latitude) != 'nan':
                lat, lon = float(location_data.latitude), float(location_data.longitude)
                city_name = str(location_data.place_name)
                fsa_code = clean_code[:3]
                
                # Firebase'e kaydetme
                db.collection('attendees').document().set({
                    "lat": lat, "lon": lon, "city": city_name,
                    "fsa": fsa_code, "full_code": clean_code 
                })
                st.session_state.has_submitted = True
                st.rerun()
            else:
                st.error("Invalid Postal Code. Please try again.")
        else:
            st.error("Please enter a valid postal code.")
else:
    st.success("🎉 Thank you! Your location has been added.")

# --- MAP RENDERING ---
m = folium.Map(location=DEFAULT_COORDS, zoom_start=7)

# KRITIK GUNCELLEME: maxClusterRadius=30 ile kümeleri daha 'sıkı' hale getirdik
marker_cluster = MarkerCluster(maxClusterRadius=30).add_to(m)

attendees_ref = db.collection('attendees')
for doc in attendees_ref.stream():
    data = doc.to_dict()
    folium.Marker(location=[data["lat"], data["lon"]], popup=data["city"]).add_to(marker_cluster)

st_folium(m, width=1000, height=600)