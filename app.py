import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import firebase_admin
from firebase_admin import credentials, db
import pandas as pd
import json
import requests
import random
import re
import math
from streamlit_autorefresh import st_autorefresh

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="North Bay Live Attendee Map", layout="wide", initial_sidebar_state="auto")

# --- SESSION STATES ---
if 'has_submitted' not in st.session_state:
    st.session_state.has_submitted = False
if 'new_user_loc' not in st.session_state:
    st.session_state.new_user_loc = None

# --- DEV EKRAN MODU (GİZLİ LİNK) KONTROLÜ ---
is_live_mode = st.query_params.get("mode") == "live"
if is_live_mode:
    st_autorefresh(interval=30 * 1000, key="datarefresh")

# --- CSS HACKS (NORTH BAY GREEN THEME) ---
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;} 
            footer {visibility: hidden;}    
            .stApp { background-color: white !important; color: black !important; }
            [data-testid="stMetricValue"], [data-testid="stMetricLabel"] { color: black !important; }
            div.stButton > button { background-color: #2E5A34 !important; color: white !important; border: none; }
            div.stButton > button:hover { background-color: #1E3A24 !important; color: white !important; }
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# --- FIREBASE SETUP ---
if not firebase_admin._apps:
    if 'firebase' in st.secrets:
        key_dict = json.loads(st.secrets["firebase"]["my_project_settings"])
        db_url = st.secrets["firebase"].get("database_url", "")
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred, {'databaseURL': db_url})
    else:
        cred = credentials.Certificate("firebase_key.json")
        firebase_admin.initialize_app(cred, {'databaseURL': 'https://eventmapdb-b59f9-default-rtdb.firebaseio.com/'})

# North Bay Etkinlik Koordinatları
DEFAULT_COORDS = [46.3091, -79.4608]

# --- SIDEBAR: ADMIN PANEL ---
with st.sidebar:
    st.header("🔒 Admin Access")
    admin_pass = st.text_input("Enter Password:", type="password")
    
    if admin_pass == "NorthBay2026":
        st.success("Unlocked!")
        st.divider()
        st.subheader("🏢 Add Exhibitor")
        ex_company = st.text_input("Company Name:")
        ex_city = st.text_input("Exhibitor City:")
        
        if st.button("Drop Exhibitor Pin"):
            query_ex = ex_city.strip()
            if len(query_ex) >= 2 and ex_company:
                try:
                    api_key = st.secrets["GOOGLE_MAPS_API_KEY"]
                    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={query_ex},+ON,+Canada&key={api_key}"
                    response = requests.get(url).json()
                    
                    if response['status'] == 'OK':
                        loc = response['results'][0]['geometry']['location']
                        city_n = query_ex
                        components = response['results'][0]['address_components']
                        
                        for comp in components:
                            if "locality" in comp["types"] or "postal_town" in comp["types"]:
                                city_n = comp["long_name"]
                                break
                                
                        db.reference('attendees').push({
                            "lat": loc['lat'], "lon": loc['lng'], "city": city_n, "type": "exhibitor", "company": ex_company
                        })
                        st.success(f"Added {ex_company} in {city_n}!")
                        st.rerun()
                    else:
                        st.error("City not found. Please try again.")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.error("Please enter a valid Company Name and City.")

        st.divider()
        st.subheader("📊 Data Management")
        ref_admin = db.reference('attendees')
        data_dict_admin = ref_admin.get()
        data_list_admin = list(data_dict_admin.values()) if data_dict_admin else []
        
        if data_list_admin:
            att_count = sum(1 for d in data_list_admin if d.get("type", "attendee") == "attendee")
            exh_count = sum(1 for d in data_list_admin if d.get("type") == "exhibitor")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"""
                    <div style="text-align: center; padding: 10px; background-color: #E8F5E9; border-radius: 8px; border: 1px solid #C8E6C9;">
                        <p style="margin:0; font-size: 14px; color: #2E7D32; font-weight: bold;">📍 Attendees</p>
                        <p style="margin:0; font-size: 26px; color: #1B5E20; font-weight: bold;">{att_count}</p>
                    </div>
                """, unsafe_allow_html=True)
            with col2:
                st.markdown(f"""
                    <div style="text-align: center; padding: 10px; background-color: #FFF3E0; border-radius: 8px; border: 1px solid #FFE0B2;">
                        <p style="margin:0; font-size: 14px; color: #E65100; font-weight: bold;">⭐ Exhibitors</p>
                        <p style="margin:0; font-size: 26px; color: #E65100; font-weight: bold;">{exh_count}</p>
                    </div>
                """, unsafe_allow_html=True)
            st.write("")
            df = pd.DataFrame(data_list_admin)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Data (CSV)", data=csv, file_name='northbay_event_data.csv', mime='text/csv')
            st.divider() 
            
            if st.button("🗑️ Wipe Attendees (Keep Exhibitors)"):
                if data_dict_admin:
                    for key, val in data_dict_admin.items():
                        if val.get("type") != "exhibitor":
                            db.reference(f'attendees/{key}').delete()
                st.cache_data.clear()
                st.rerun()
        else:
            st.info("No data yet.")

# --- MAIN PAGE UI ---
col_l, col_m, col_r = st.columns([1, 1.5, 1])
with col_m:
    try: st.image("logo.png", use_container_width=True)
    except: pass 

st.markdown("<h1 style='text-align: center;'>✨ Light Up The North!</h1>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align: center; color: #2E5A34; margin-top: -15px;'>Add your town to the live map</h3>", unsafe_allow_html=True)

if not st.session_state.has_submitted:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        city_input = st.text_input("Enter your town or city:", placeholder="Enter your town or city. e.g. North Bay", label_visibility="collapsed")
        submit_button = st.button("Submit", use_container_width=True)
        st.markdown("<p style='text-align: center; color: #555; font-size: 16px; margin-top: 10px;'>See how far people have travelled to be here</p>", unsafe_allow_html=True)

    if submit_button and city_input:
        query = city_input.strip()
        if len(query) >= 2:
            try:
                api_key = st.secrets["GOOGLE_MAPS_API_KEY"]
                
                places_url = f"https://maps.googleapis.com/maps/api/place/autocomplete/json?input={query},+ON,+Canada&types=(regions)&key={api_key}"
                places_response = requests.get(places_url).json()

                if places_response['status'] == 'OK' and places_response['predictions']:
                    first_prediction = places_response['predictions'][0]
                    place_id = first_prediction['place_id']
                    suggested_desc = first_prediction['description']
                    micro_city = suggested_desc.split(',')[0] 

                    geocode_url = f"https://maps.googleapis.com/maps/api/geocode/json?place_id={place_id}&key={api_key}"
                    geocode_response = requests.get(geocode_url).json()

                    if geocode_response['status'] == 'OK':
                        result = geocode_response['results'][0]
                        lat = result['geometry']['location']['lat']
                        lon = result['geometry']['location']['lng']
                        components = result['address_components']

                        macro_city = micro_city 

                        for comp in components:
                            types = comp['types']
                            if 'locality' in types:
                                macro_city = comp['long_name']
                                break
                            elif 'administrative_area_level_3' in types and macro_city == micro_city:
                                macro_city = comp['long_name']

                        if macro_city != micro_city:
                            macro_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={macro_city},+ON,+Canada&key={api_key}"
                            macro_response = requests.get(macro_url).json()
                            if macro_response['status'] == 'OK':
                                lat = macro_response['results'][0]['geometry']['location']['lat']
                                lon = macro_response['results'][0]['geometry']['location']['lng']

                        db.reference('attendees').push({
                            "lat": lat, "lon": lon, "city": macro_city, "micro_city": micro_city, "type": "attendee" 
                        })
                        
                        st.session_state.new_user_loc = {"lat": lat, "lon": lon, "city": macro_city}
                        st.session_state.has_submitted = True
                        st.cache_data.clear()
                        st.rerun() 
                    else:
                        st.error("Could not fetch location details. Please try again.")
                else:
                    st.error("City not found. Please try typing it differently.")
            except Exception as e:
                st.error(f"Service error: {e}")
        else:
            st.error("Please enter a valid city or borough name.")
else:
    st.success("🎉 Thank you! Your location has been added to the map.")

# --- FETCH & RENDER MAP ---
st.divider()

@st.cache_data(ttl=30)
def get_cached_data():
    ref = db.reference('attendees')
    d_dict = ref.get()
    return list(d_dict.values()) if d_dict else []

data_list = get_cached_data()

# --- SUNUCU TARAFINDA VERİ GRUPLAMASI ---
attendee_summary = {}
exhibitors = []

for data in data_list:
    if data.get("type") == "exhibitor":
        exhibitors.append(data)
    else:
        city = data.get("city", "Unknown")
        if city not in attendee_summary:
            attendee_summary[city] = {"lat": data.get("lat"), "lon": data.get("lon"), "count": 0}
        attendee_summary[city]["count"] += 1

st.markdown("<p style='text-align: center; font-size: 18px;'><b>Legend:</b> ⭐ Exhibitors &nbsp; | &nbsp; 📍 Attendees</p>", unsafe_allow_html=True)

m = folium.Map(location=DEFAULT_COORDS, zoom_start=6, tiles="cartodbpositron")
marker_cluster = MarkerCluster(maxClusterRadius=35).add_to(m)

# YENİ SİSTEM: DOĞADAKİ AYÇİÇEĞİ (FERMAT SARMALI) DİZİLİMİ İLE HOMOJEN DAĞILIM
exh_by_city = {}
for ex in exhibitors:
    city = ex.get("city", "Unknown")
    if city not in exh_by_city:
        exh_by_city[city] = []
    exh_by_city[city].append(ex)

# Altın Açı (Golden Angle) radyan cinsinden
GOLDEN_ANGLE = math.pi * (3 - math.sqrt(5))

for city, ex_list in exh_by_city.items():
    for i, ex in enumerate(ex_list):
        comp_name = ex.get("company", "Exhibitor")
        
        # Merkezdeki mavi ziyaretçi iğnesiyle üst üste binmesin diye i+3 kullanıyoruz
        # 0.007 değeri iğneler arası genel yayılma mesafesidir. Artırırsan şehir içine daha geniş yayılırlar.
        radius = 0.007 * math.sqrt(i + 3) 
        angle = i * GOLDEN_ANGLE
        
        offset_lat = radius * math.cos(angle)
        offset_lon = radius * math.sin(angle) * 1.5 # Harita projeksiyonu için X ekseni telafisi
        
        folium.Marker(
            location=[ex["lat"] + offset_lat, ex["lon"] + offset_lon], 
            tooltip=comp_name, 
            icon=folium.Icon(color="red", icon="star", prefix="fa")
        ).add_to(m)

# Ziyaretçileri çizmeye devam ediyoruz
for city, info in attendee_summary.items():
    count = info["count"]
    is_newest = False
    
    if st.session_state.new_user_loc and st.session_state.new_user_loc["city"] == city:
        is_newest = True

    popup_text = f"<div style='text-align:center;'><b>{city}</b><br>Attendees: {count}</div>"
    tooltip_text = f"{city} ({count} Attendees)"

    if is_newest:
        folium.Marker(
            location=[info["lat"], info["lon"]], popup=popup_text, tooltip="📍 You are here!", icon=folium.Icon(color="orange", icon="star")
        ).add_to(m)
    else:
        folium.Marker(
            location=[info["lat"], info["lon"]], popup=popup_text, tooltip=tooltip_text, icon=folium.Icon(color="blue", icon="users", prefix="fa")
        ).add_to(marker_cluster)

st_folium(m, use_container_width=True, height=500, returned_objects=[])
