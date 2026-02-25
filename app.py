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
st.set_page_config(page_title="Live Attendee Map", layout="wide", initial_sidebar_state="auto")

# --- CSS HACKS: STABIL VE GUVENLI VERSIYON ---
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;} /* Sag ust menuyu gizle */
            footer {visibility: hidden;}    /* Alttaki Streamlit yazisini gizle */
            
            /* Temayi zorla beyaz yap, yazilari siyah yap */
            .stApp {
                background-color: white !important;
                color: black !important;
            }
            
            /* SADECE Sayac yazilarini siyah yap (Menuleri bozmaz!) */
            [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
                color: black !important;
            }
            
            /* Beyaz arka planda kaybolan menü okunu siyah yap */
            [data-testid="collapsedControl"] svg {
                fill: black !important;
            }
            
            /* OZEL BUTON RENGI (LOGODAKI KOYU YESIL) */
            div.stButton > button {
                background-color: #2E5A34 !important; 
                color: white !important; 
                border: none;
            }
            div.stButton > button:hover {
                background-color: #1E3A24 !important; 
                color: white !important;
            }
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

DEFAULT_COORDS = [46.3091, -79.4608]

if 'has_submitted' not in st.session_state:
    st.session_state.has_submitted = False

# --- SIDEBAR: HIDDEN ADMIN PANEL ---
with st.sidebar:
    st.header("🔒 Admin Access")
    admin_pass = st.text_input("Enter Password:", type="password")
    
    if admin_pass == "NorthBay2026":
        st.success("Unlocked!")
        
        # --- EXHIBITOR INPUT (Company Name Eklendi) ---
        st.divider()
        st.subheader("🏢 Add Exhibitor (Red Star)")
        ex_company = st.text_input("Company Name (e.g., Shimano):")
        ex_code = st.text_input("Vendor Postal Code:", max_chars=7)
        
        if st.button("Drop Exhibitor Pin"):
            clean_ex = ex_code.replace(" ", "").upper()
            if len(clean_ex) >= 3 and ex_company:
                try:
                    api_key = st.secrets["GOOGLE_MAPS_API_KEY"]
                    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={clean_ex},+Canada&key={api_key}"
                    response = requests.get(url).json()
                    if response['status'] == 'OK':
                        loc = response['results'][0]['geometry']['location']
                        city_n = clean_ex
                        for comp in response['results'][0]['address_components']:
                            if "locality" in comp["types"] or "postal_town" in comp["types"]:
                                city_n = comp["long_name"]
                                break
                        db.collection('attendees').document().set({
                            "lat": loc['lat'], "lon": loc['lng'], "city": city_n,
                            "fsa": clean_ex[:3], "full_code": clean_ex,
                            "type": "exhibitor",
                            "company": ex_company
                        })
                        st.success(f"{ex_company} added at {city_n}!")
                        st.rerun()
                    else:
                        st.error("Google API Error. Check code.")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Enter both Company Name and Code.")

        # --- DATA EXPORT & WIPE ---
        st.divider()
        st.subheader("📊 Data Management")