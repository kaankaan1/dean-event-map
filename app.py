import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import json
import requests
import random
import re

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Live Attendee Map", layout="wide", initial_sidebar_state="auto")

# --- CSS HACKS: STABLE AND SECURE VERSION ---
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;} 
            footer {visibility: hidden;}    
            
            .stApp {
                background-color: white !important;
                color: black !important;
            }
            
            [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
                color: black !important;
            }
            
            [data-testid="collapsedControl"] svg {
                fill: black !important;
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

# --- SESSION STATES ---
if 'has_submitted' not in st.session_state:
    st.session_state.has_submitted = False
if 'new_user_loc' not in st.session_state:
    st.session_state.new_user_loc = None

# ==========================================
# 🚀 YENİ EKLENEN KISIM: CACHE (ÖNBELLEK) SİSTEMİ
# ==========================================
@st.cache_data(ttl=60) # 60 saniyede bir otomatik yenilenir (güvenlik için)
def get_all_attendees():
    """Veritabanındaki tüm pinleri çeker ve hafızada tutar."""
    docs = db.collection('attendees').stream()
    return [doc.to_dict() for doc in docs]
# ==========================================


# --- SIDEBAR: HIDDEN ADMIN PANEL ---
with st.sidebar:
    st.header("🔒 Admin Access")
    admin_pass = st.text_input("Enter Password:", type="password")
    
    if admin_pass == "NorthBay2026":
        st.success("Unlocked!")
        
        st.divider()
        st.subheader("🏢 Add Exhibitor (Red Star)")
        ex_company = st.text_input("Company Name (e.g., Shimano):")
        ex_code = st.text_input("Vendor Postal Code:", max_chars=7)
        
        if st.button("Drop Exhibitor Pin"):
            clean_ex = re.sub(r'[^A-Z0-9]', '', ex_code.upper())
            if len(clean_ex) >= 3 and ex_company:
                try:
                    api_key = st.secrets["GOOGLE_MAPS_API_KEY"]
                    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={clean_ex},+Canada&key={api_key}"
                    response = requests.get(url).json()
                    if response['status'] == 'OK':
                        loc = response['results'][0]['geometry']['location']
                        city_n = clean_ex
                        components = response['results'][0]['address_components']
                        
                        for comp in components:
                            if "locality" in comp["types"] or "postal_town" in comp["types"]:
                                city_n = comp["long_name"]
                                break
                        if city_n == clean_ex:
                            for comp in components:
                                if "administrative_area_level_3" in comp["types"] or "sublocality" in comp["types"] or "neighborhood" in comp["types"]:
                                    city_n = comp["long_name"]
                                    break
                                    
                        formatted_code = f"{clean_ex[:3]} {clean_ex[3:]}".strip() if len(clean_ex) == 6 else clean_ex
                        
                        db.collection('attendees').document().set({
                            "lat": loc['lat'], "lon": loc['lng'], "city": city_n,
                            "fsa": clean_ex[:3], "full_code": formatted_code,
                            "type": "exhibitor",
                            "company": ex_company
                        })
                        
                        # CACHE'İ TEMİZLE Kİ YENİ EKLENEN HEMEN GÖRÜNSÜN
                        get_all_attendees.clear()
                        
                        st.success(f"{ex_company} added at {city_n}!")
                        st.rerun()
                    else:
                        st.error("Google API Error. Check code.")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Enter both Company Name and Code.")

        st.divider()
        st.subheader("📊 Data Management")
        
        # CACHE KULLANARAK VERİYİ ÇEK (Eski stream kodları silindi)
        data_list_admin = get_all_attendees()
        
        if data_list_admin:
            # --- NEW: COLORFUL AND STYLISH ADMIN COUNTERS ---
            att_count = sum(1 for d in data_list_admin if d.get("type", "attendee") == "attendee")
            exh_count = sum(1 for d in data_list_admin if d.get("type") == "exhibitor")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"""
                    <div style="text-align: center; padding: 10px; background-color: #E6F2FF; border-radius: 8px; border: 1px solid #B3D7FF;">
                        <p style="margin:0; font-size: 14px; color: #0056B3; font-weight: bold;">📍 Attendees</p>
                        <p style="margin:0; font-size: 26px; color: #007BFF; font-weight: bold;">{att_count}</p>
                    </div>
                """, unsafe_allow_html=True)
            with col2:
                st.markdown(f"""
                    <div style="text-align: center; padding: 10px; background-color: #FFEBEE; border-radius: 8px; border: 1px solid #FFCDD2;">
                        <p style="margin:0; font-size: 14px; color: #C62828; font-weight: bold;">⭐ Exhibitors</p>
                        <p style="margin:0; font-size: 26px; color: #F44336; font-weight: bold;">{exh_count}</p>
                    </div>
                """, unsafe_allow_html=True)
            st.write("")
            # -------------------------------------------
            
            df = pd.DataFrame(data_list_admin)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Data (CSV)", data=csv, file_name='event_data.csv', mime='text/csv')
            
            st.divider() 
            if st.button("🗑️ Wipe All Data"):
                for doc in db.collection('attendees').stream():
                    doc.reference.delete()
                # TÜM VERİ SİLİNDİ, CACHE'İ DE TEMİZLE!
                get_all_attendees.clear()
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
        clean_code = re.sub(r'[^A-Z0-9]', '', postal_code_input.upper())
        
        if len(clean_code) >= 3:
            fsa_code = clean_code[:3]
            try:
                api_key = st.secrets["GOOGLE_MAPS_API_KEY"]
                url = f"https://maps.googleapis.com/maps/api/geocode/json?address={clean_code},+Canada&key={api_key}"
                response = requests.get(url).json()
                
                if response['status'] == 'OK':
                    location = response['results'][0]['geometry']['location']
                    city_name = clean_code 
                    components = response['results'][0]['address_components']
                    
                    for comp in components:
                        if "locality" in comp["types"] or "postal_town" in comp["types"]:
                            city_name = comp["long_name"]
                            break
                    if city_name == clean_code:
                        for comp in components:
                            if "administrative_area_level_3" in comp["types"] or "sublocality" in comp["types"] or "neighborhood" in comp["types"]:
                                city_name = comp["long_name"]
                                break
                    
                    formatted_code = f"{clean_code[:3]} {clean_code[3:]}".strip() if len(clean_code) == 6 else clean_code
                    
                    db.collection('attendees').document().set({
                        "lat": location['lat'], "lon": location['lng'], "city": city_name,
                        "fsa": fsa_code, "full_code": formatted_code,
                        "type": "attendee" 
                    })
                    
                    # YENİ KİŞİ GİRDİ, CACHE'İ TEMİZLE Kİ HEMEN HARİTAYA DÜŞSÜN
                    get_all_attendees.clear()
                    
                    st.session_state.new_user_loc = {"lat": location['lat'], "lon": location['lng'], "city": city_name}
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


# --- FETCH DATA & RENDER LEGEND ---
st.divider()

# CACHE KULLANARAK VERİYİ ÇEK (Her seferinde Firebase'e sormayacak!)
data_list = get_all_attendees()

# Privacy friendly legend replacing the old counters
st.markdown("<p style='text-align: center; font-size: 18px;'><b>Legend:</b> ⭐ Exhibitors (Red Stars) &nbsp; | &nbsp; 📍 Attendees (Blue Pins)</p>", unsafe_allow_html=True)
st.write("") 

# --- MAP RENDERING ---
m = folium.Map(location=DEFAULT_COORDS, zoom_start=6)

marker_cluster = MarkerCluster(maxClusterRadius=35).add_to(m)

for data in data_list:
    is_ex = data.get("type") == "exhibitor"
    
    is_newest = False
    if st.session_state.new_user_loc and data["lat"] == st.session_state.new_user_loc["lat"] and data["lon"] == st.session_state.new_user_loc["lon"]:
        is_newest = True
    
    if is_ex:
        comp_name = data.get("company", "Exhibitor")
        
        # Jitter reverted to original smaller value (0.003) to prevent landing in the water
        random.seed(comp_name) 
        jitter_lat = random.uniform(-0.003, 0.003)
        jitter_lon = random.uniform(-0.003, 0.003)
        random.seed() 
        
        final_lat = data["lat"] + jitter_lat
        final_lon = data["lon"] + jitter_lon
        
        p_text = f"⭐ {comp_name} ({data.get('city', '')})"
        
        folium.Marker(
            location=[final_lat, final_lon],
            popup=p_text,
            tooltip=comp_name,
            icon=folium.Icon(color="red", icon="star", prefix="fa")
        ).add_to(m) 
        
    else:
        p_text = data.get("city", "")
        
        if is_newest:
            # Silent Gold Pin: No text, no popup, no tooltip.
            folium.Marker(
                location=[data["lat"], data["lon"]],
                icon=folium.Icon(color="orange", icon="star")
            ).add_to(m) 
        else:
            folium.Marker(
                location=[data["lat"], data["lon"]],
                popup=p_text,
                tooltip="Attendee",
                icon=folium.Icon(color="blue", icon="map-pin", prefix="fa")
            ).add_to(marker_cluster) 

st_folium(m, use_container_width=True, height=500, returned_objects=[])