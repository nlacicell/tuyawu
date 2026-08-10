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

BASE_URL = "https://tuyaeu.com"

# --- 2. TUYA HITELESÍTÉS (TOKEN LEKÉRÉS) ---
def get_tuya_token():
    t = str(int(time.time() * 1000))
    url_path = "/v1.0/token?grant_type=1"
    string_to_sign = f"{ACCESS_ID}{t}GET\n{hashlib.sha256(b'').hexdigest()}\n\n{url_path}"
    sign = hmac.new(ACCESS_SECRET.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest().upper()
    
    headers = {
        "client_id": ACCESS_ID,
        "sign": sign,
        "t": t,
        "sign_method": "HMAC-SHA256"
    }
    
    res = requests.get(f"{BASE_URL}{url_path}", headers=headers)
    if res.status_code == 200 and res.json().get("success"):
        return res.json()["result"]["access_token"]
    raise Exception(f"Token hiba: {res.text}")

# --- 3. KÉTUTAS ADATLEKÉRÉS A TUYA-BÓL ---
def get_all_device_data(token):
    t = str(int(time.time() * 1000))
    
    # 1. út: Status API (ezt használtuk eddig)
    path_status = f"/v1.0/devices/{DEVICE_ID}/status"
    sign_status = hmac.new(ACCESS_SECRET.encode('utf-8'), f"{ACCESS_ID}{token}{t}GET\n{hashlib.sha256(b'').hexdigest()}\n\n{path_status}".encode('utf-8'), hashlib.sha256).hexdigest().upper()
    res_status = requests.get(f"{BASE_URL}{path_status}", headers={"client_id": ACCESS_ID, "access_token": token, "sign": sign_status, "t": t, "sign_method": "HMAC-SHA256"})
    
    # 2. út: Specifications/Properties API (itt laknak az időjárás számos DP értékei)
    path_spec = f"/v1.0/devices/{DEVICE_ID}/specifications"
    sign_spec = hmac.new(ACCESS_SECRET.encode('utf-8'), f"{ACCESS_ID}{token}{t}GET\n{hashlib.sha256(b'').hexdigest()}\n\n{path_spec}".encode('utf-8'), hashlib.sha256).hexdigest().upper()
    res_spec = requests.get(f"{BASE_URL}{path_spec}", headers={"client_id": ACCESS_ID, "access_token": token, "sign": sign_spec, "t": t, "sign_method": "HMAC-SHA256"})
    
    combined_data = {}
    
    if res_status.status_code == 200 and res_status.json().get("success"):
        for item in res_status.json().get("result", []):
            combined_data[str(item["code"])] = item["value"]
            
    if res_spec.status_code == 200 and res_spec.json().get("success"):
        properties = res_spec.json().get("result", {}).get("properties", [])
        for item in properties:
            combined_data[str(item["code"])] = item["value"]
            
    return combined_data

try:
    token = get_tuya_token()
    data = get_all_device_data(token)
    print("Sikeres lekérés! Egyesített Tuya adatbázis:\n", data)
    
    # --- 4. SZÁMÍTÁSOK ÉS ANALÍZIS (Vevor Numerikus sémák és nevek alapján) ---
    # Külső Hőmérséklet (Keresi a '1', '101', 'temp_current', 'va_temperature' kódokat)
    raw_temp = data.get("1", data.get("101", data.get("temp_current", data.get("va_temperature", 0))))
    temp_c = raw_temp / 10.0 if raw_temp > 60 or raw_temp < -40 else raw_temp
    temp_f = (temp_c * 9/5) + 32
    
    # Külső Páratartalom ('2', '102', 'humidity_current')
    humidity = data.get("2", data.get("102", data.get("humidity_current", data.get("va_humidity", 0))))
    
    # Szélsebesség ('4', '105', 'wind_speed')
    raw_wind = data.get("4", data.get("105", data.get("wind_speed", 0)))
    wind_kmh = raw_wind / 10.0 if raw_wind > 150 else raw_wind
    wind_mph = wind_kmh * 0.621371
    
    # Széllökés ('5', '106', 'gust_speed')
    raw_gust = data.get("5", data.get("106", data.get("gust_speed", 0)))
    gust_kmh = raw_gust / 10.0 if raw_gust > 150 else raw_gust
    gust_mph = gust_kmh * 0.621371
    
    # Szélirány ('7', '107', 'wind_direction')
    wind_dir = data.get("7", data.get("107", data.get("wind_direction", 0)))
    
    # Légnyomás ('10', '111', 'pressure_current')
    raw_baro = data.get("10", data.get("111", data.get("pressure_current", data.get("pressure", 1013))))
    baro_hpa = raw_baro / 10.0 if raw_baro > 1200 else raw_baro
    baro_in = baro_hpa * 0.02953
    
    # Csapadék ('13', '113', 'rain_current')
    raw_rain = data.get("13", data.get("113", data.get("rain_current", data.get("rain_24h", 0))))
    rain_mm = raw_rain / 10.0 if raw_rain > 500 else raw_rain
    rain_in = rain_mm * 0.0393701

    # --- 5. FELTÖLTÉS WEATHER UNDERGROUND-RA ---
    wu_url = "https://wunderground.com"
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
