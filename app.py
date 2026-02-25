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

# --- CSS HACKS: FORCE LIGHT MODE, CUSTOM BUTTON & HIDE BRANDING ---
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;} 
            footer {visibility: hidden;}    
            .viewerBadge_container {display: none !important;}
            .viewerBadge_link {display: none !important;}
            [data-testid="stToolbar"] {display: none !important;}
            
            .stApp {
                background-color: white !important;
                color: black !important;
            }
            
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
        
        # --- EXHIBITOR INPUT (YENI: Company Name eklendi) ---
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
                            "company": ex_company # YENI VERI
                        })
                        st.success(f"{ex_company} added at {city_n}!")
                        st.rerun()
                    else:
                        st.error("Google API Error. Check code.")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Please enter both Company Name and a valid Postal Code.")

        # --- DATA EXPORT & WIPE ---
        st.divider()
        st.subheader("📊 Data Management")
        attendees_ref = db.collection('attendees')
        docs_admin = attendees_ref.stream()
        data_list_admin = [doc.to_dict() for doc in docs_admin]
        
        if data_list_admin:
            df = pd.DataFrame(data_list_admin)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Data (CSV)", data=csv, file_name='event_data.csv', mime='text/csv')
            
            st.divider() 
            if st.button("🗑️ Wipe All Data"):
                for doc in db.collection('attendees').stream():
                    doc.reference.delete()
                st.rerun()
        else:
            st.info("No data yet.")

# --- MAIN PAGE UI ---
col_l, col_m, col_r = st.columns([1, 1.5, 1])
with col_m:
    try:
        st.image("logo.png", use_container_width=True)
    except:
        pass 

st.markdown("<h1 style='text-align: center;'>📍 What area are you coming in from?</h1>", unsafe_allow_html=True)

if not st.session_state.has_submitted:
    st.markdown("<p style='text-align: center;'>Enter your postal code and see how far our outdoor community reaches:</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        postal_code_input = st.text_input("Canadian Postal Code (e.g., P1B 8G6):", max_chars=7, label_visibility="collapsed", placeholder="Canadian Postal Code (e.g., P1B 8G6)")
        st.write("")
        submit_button = st.button("Submit", use_container_width=True)

    if submit_button and postal_code_input:
        clean_code = postal_code_input.replace(" ", "").upper()
        if len(clean_code) >= 3:
            fsa_code = clean_code[:3]
            try:
                api_key = st.secrets["GOOGLE_MAPS_API_KEY"]
                url = f"https://maps.googleapis.com/maps/api/geocode/json?address={clean_code},+Canada&key={api_key}"
                response = requests.get(url).json()
                
                if response['status'] == 'OK':
                    location = response['results'][0]['geometry']['location']
                    city_name = clean_code 
                    for comp in response['results'][0]['address_components']:
                        if "locality" in comp["types"] or "postal_town" in comp["types"]:
                            city_name = comp["long_name"]
                            break
                    
                    db.collection('attendees').document().set({
                        "lat": location['lat'], "lon": location['lng'], "city": city_name,
                        "fsa": fsa_code, "full_code": clean_code,
                        "type": "attendee" 
                    })
                    st.session_state.has_submitted = True
                    st.rerun() 
                else:
                    st.error("Postal code not found. Please try again.")
            except Exception as e:
                st.error("Service error.")
        else:
            st.error("Please enter a valid code.")
else:
    st.success("🎉 Thank you! Your location has been added to the map.")


# --- FETCH DATA & RENDER METRICS ---
attendees_ref = db.collection('attendees')
docs = attendees_ref.stream()
data_list = [doc.to_dict() for doc in docs]

# Sayaclari hesapla
attendee_count = sum(1 for d in data_list if d.get("type", "attendee") == "attendee")
exhibitor_count = sum(1 for d in data_list if d.get("type") == "exhibitor")

st.divider()

# Sayaclari Ekrana Bas (Ortalayarak)
met1, met2, met3, met4 = st.columns(4)
with met2:
    st.metric(label="🏕️ Total Attendees", value=attendee_count)
with met3:
    st.metric(label="⭐ Featured Exhibitors", value=exhibitor_count)

st.write("") # Harita oncesi kucuk bir bosluk

# --- MAP RENDERING ---
m = folium.Map(location=DEFAULT_COORDS, zoom_start=6)

# SADECE Ziyaretciler (Attendees) icin gruplama (Cluster)
marker_cluster = MarkerCluster(maxClusterRadius=35).add_to(m)

for data in data_list:
    is_ex = data.get("type") == "exhibitor"
    
    if is_ex:
        # EXHIBITORS (Kirmizi Yildiz) - Gruplanmaz, dogrudan 'm' haritasina eklenir
        comp_name = data.get("company", "Exhibitor")
        p_text = f"⭐ {comp_name} ({data.get('city', '')})"
        
        folium.Marker(
            location=[data["lat"], data["lon"]],
            popup=p_text,
            tooltip=comp_name,
            icon=folium.Icon(color="red", icon="star", prefix="fa")
        ).add_to(m) # marker_cluster yerine m'e ekliyoruz!
        
    else:
        # ATTENDEES (Mavi Igne) - Gruplanir
        p_text = data.get("city", "")
        
        folium.Marker(
            location=[data["lat"], data["lon"]],
            popup=p_text,
            tooltip="Attendee",
            icon=folium.Icon(color="blue", icon="map-pin", prefix="fa")
        ).add_to(marker_cluster) # marker_cluster'a ekliyoruz!

st_folium(m, use_container_width=True, height=500)