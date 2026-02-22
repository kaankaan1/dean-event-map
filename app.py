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