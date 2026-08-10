import os
import time
import hmac
import hashlib
import requests

# --- 1. PROJEKT ÉS ESZKÖZ ADATOK (GITHUB SECRETS) ---
ACCESS_ID = os.environ.get("TUYA_ACCESS_ID")
ACCESS_SECRET = os.environ.get("TUYA_ACCESS_SECRET")
DEVICE_ID = os.environ.get("TUYA_DEVICE_ID")

WU_STATION_ID = os.environ.get("WU_STATION_ID")
WU_STATION_KEY = os.environ.get("WU_STATION_KEY")

BASE_URL = "https://openapi.tuyaeu.com"

# --- 2. TUYA CLOUD API HITELESÍTÉS (TOKEN LEKÉRÉS) ---
def get_tuya_token():
    t = str(int(time.time() * 1000))
    url_path = "/v1.0/token?grant_type=1"
    
    # Hivatalos Tuya v2 Aláírás számítás
    string_to_sign = f"{ACCESS_ID}{t}GET\n{hashlib.sha256(b'').hexdigest()}\n\n{url_path}"
    sign = hmac.new(ACCESS_SECRET.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest().upper()
    
    headers = {
        "client_id": ACCESS_ID,
        "sign": sign,
        "t": t,
        "sign_method": "HMAC-SHA256",
        "Content-Type": "application/json"
    }
    
    res = requests.get(f"{BASE_URL}{url_path}", headers=headers)
    if res.status_code == 200 and res.json().get("success"):
        return res.json()["result"]["access_token"]
    else:
        raise Exception(f"Token hiba: {res.text}")

# --- 3. ESZKÖZ STÁTUSZ LEKÉRÉSE ---
def get_device_status(token):
    t = str(int(time.time() * 1000))
    url_path = f"/v1.0/devices/{DEVICE_ID}/status"
    
    # Hivatalos Tuya v2 Aláírás számítás tokennel együtt
    string_to_sign = f"{ACCESS_ID}{token}{t}GET\n{hashlib.sha256(b'').hexdigest()}\n\n{url_path}"
    sign = hmac.new(ACCESS_SECRET.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest().upper()
    
    headers = {
        "client_id": ACCESS_ID,
        "access_token": token,
        "sign": sign,
        "t": t,
        "sign_method": "HMAC-SHA256",
        "Content-Type": "application/json"
    }
    
    res = requests.get(f"{BASE_URL}{url_path}", headers=headers)
    if res.status_code == 200 and res.json().get("success"):
        return res.json()["result"]
    else:
        raise Exception(f"Eszköz lekérési hiba: {res.text}")

try:
    token = get_tuya_token()
    stats = get_device_status(token)
    
    data = {item["code"]: item["value"] for item in stats}
    print("Sikeres lekérés! Nyers Tuya adatok:\n", data)
    
    # --- 4. METRIKÁK KINYERÉSE ÉS ÁTVÁLTÁSA ---
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

    # --- 5. FELTÖLTÉS WEATHER UNDERGROUND-RA ---
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

except Exception as e:
    print("Hiba történt a futtatás során:", e)
    exit(1)
