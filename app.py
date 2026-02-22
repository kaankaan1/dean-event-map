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

# --- FIREBASE SETUP (BULUT UYUMLU GUVENLI BAGLANTI) ---
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

# --- SIDEBAR: GIZLI ADMIN PANELİ ---
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
            
            # 1. ADIM: Önce tam 6 haneli kodu dene (Yüksek hassasiyet)
            location_data = nomi.query_postal_code(clean_code)
            
            # 2. ADIM: Eğer 6 haneli kod kütüphanede yoksa, ilk 3 haneyi (FSA) dene
            if str(location_data.latitude) == 'nan':
                location_data = nomi.query_postal_code(fsa_code)
            
            if str(location_data.latitude) != 'nan':
                lat = float(location_data.latitude)
                lon = float(location_data.longitude)
                city_name = str(location_data.place_name)
                
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
    st.success("🎉 Thank you! Your location has been added to the map.")
    st.info("Look at the screen to see your dot appear!")

# --- MAP RENDERING ---
m = folium.Map(location=DEFAULT_COORDS, zoom_start=7)

# GÜNCELLEME: Kümeleme yarıçapını daralttık (maxClusterRadius=35)
marker_cluster = MarkerCluster(maxClusterRadius=35).add_to(m)

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