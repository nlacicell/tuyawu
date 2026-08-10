import os
import time
import requests
from tuya_connector import TuyaOpenAPI, TUYA_LOGGER

# --- 1. PROJEKT ÉS ESZKÖZ ADATOK (A GITHUB SECRETS-BŐL OLVASVA) ---
TUYA_ACCESS_ID = os.environ.get("TUYA_ACCESS_ID")
TUYA_ACCESS_SECRET = os.environ.get("TUYA_ACCESS_SECRET")
TUYA_DEVICE_ID = os.environ.get("TUYA_DEVICE_ID")

# JAVÍTÁS: A hivatalos Tuya API Endpoint és az Európai régió kód ('eu')
TUYA_API_ENDPOINT = "https://tuyaeu.com"
TUYA_REGION = "eu" 

# --- WEATHER UNDERGROUND REGISZTRÁCIÓS ADATOK ---
WU_STATION_ID = os.environ.get("WU_STATION_ID")
WU_STATION_KEY = os.environ.get("WU_STATION_KEY")

# --- 2. KAPCSOLÓDÁS A TUYA FELHŐHÖZ ---
# Itt már átadjuk a pontos régiókódot is, így nem fog eltévedni a szerver
openapi = TuyaOpenAPI(TUYA_API_ENDPOINT, TUYA_ACCESS_ID, TUYA_ACCESS_SECRET, TUYA_REGION)
openapi.connect()

# Az eszköz aktuális státuszának lekérése
response = openapi.get(f"/v1.0/devices/{TUYA_DEVICE_ID}/status")

if response.get("success"):
    stats = response.get("result", [])
    
    # Adatpontok kicsomagolása egy kulcs-érték szótárba
    data = {item["code"]: item["value"] for item in stats}
    print("Sikeres lekérés! Nyers Tuya adatok:\n", data)
    
    # --- 3. METRIKÁK KINYERÉSE (A VEVOR TUYA SÉMÁJA ALAPJÁN) ---
    raw_temp = data.get("temp_current", data.get("va_temperature", 0))
    temp_c = raw_temp / 10.0 if raw_temp > 60 or raw_temp < -40 else raw_temp
    temp_f = (temp_c * 9/5) + 32
    
    humidity = data.get("humidity_current", data.get("va_humidity", 0))
    
    raw_wind = data.get("wind_speed", 0)
    wind_kmh = raw_wind / 10.0 if raw_wind > 150 else raw_wind
    wind_mph = wind_kmh * 0.621371
    
    raw_gust = data.get("gust_speed", 0)
    gust_kmh = raw_gust / 10.0 if raw_gust > 150 else raw_gust
    gust_mph = gust_kmh * 0.621371
    
    wind_dir = data.get("wind_direction", 0)
    
    raw_baro = data.get("pressure_current", data.get("pressure", 1013))
    baro_hpa = raw_baro / 10.0 if raw_baro > 1200 else raw_baro
    baro_in = baro_hpa * 0.02953
    
    raw_rain = data.get("rain_current", data.get("rain_24h", 0))
    rain_mm = raw_rain / 10.0 if raw_rain > 500 else raw_rain
    rain_in = rain_mm * 0.0393701

    # --- 4. HTTP GET KÉRÉS INDÍTÁSA A WEATHER UNDERGROUND FELÉ ---
    wu_url = "http://wunderground.com"
    
    params = {
        "ID": WU_STATION_ID,
        "PASSWORD": WU_STATION_KEY,
        "dateutc": "now",
        "tempf": round(temp_f, 1),
        "humidity": int(humidity),
        "windspeedmph": round(wind_mph, 1),
        "windgustmph": round(gust_mph, 1),
        "winddir": int(wind_dir),
        "baromin": round(baro_in, 2),
        "rainin": round(rain_in, 2),
        "action": "updateraw"
    }
    
    wu_response = requests.get(wu_url, params=params)
    print(f"\nWU Válaszkód: {wu_response.status_code} - Üzenet: {wu_response.text}")

else:
    print("Hiba történt a Tuya API lekérés során:", response)
