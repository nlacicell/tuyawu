import os
import time
import hmac
import hashlib
import requests
import base64

# --- 1. PROJEKT ÉS ESZKÖZ ADATOK (GITHUB SECRETS) ---
ACCESS_ID = os.environ.get("TUYA_ACCESS_ID")
ACCESS_SECRET = os.environ.get("TUYA_ACCESS_SECRET")
DEVICE_ID = os.environ.get("TUYA_DEVICE_ID")

WU_STATION_ID = os.environ.get("WU_STATION_ID")
WU_STATION_KEY = os.environ.get("WU_STATION_KEY")

# 1. JÓ CÍM: A működő európai Tuya OpenAPI szervercím
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

# --- 3. SPECIÁLIS IDŐJÁRÁS-ADAT LEKÉRÉS A NAPLÓKBÓL IS ---
def get_weather_station_data(token):
    t = str(int(time.time() * 1000))
    combined_data = {}

    # 3 különböző Tuya API végpontot kérdezünk le, beleértve a valós idejű logokat is!
    endpoints = [
        f"/v1.0/devices/{DEVICE_ID}/status",
        f"/v1.0/devices/{DEVICE_ID}/specifications",
        f"/v1.0/devices/{DEVICE_ID}/logs?codes=outdoor_alert_display"
    ]

    for path in endpoints:
        try:
            string_to_sign = f"{ACCESS_ID}{token}{t}GET\n{hashlib.sha256(b'').hexdigest()}\n\n{path}"
            sign = hmac.new(ACCESS_SECRET.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest().upper()
            
            headers = {
                "client_id": ACCESS_ID,
                "access_token": token,
                "sign": sign,
                "t": t,
                "sign_method": "HMAC-SHA256"
            }
            
            res = requests.get(f"{BASE_URL}{path}", headers=headers)
            if res.status_code == 200 and res.json().get("success"):
                res_json = res.json()
                result_obj = res_json.get("result", {})
                
                if isinstance(result_obj, list):
                    for item in result_obj:
                        if isinstance(item, dict) and "code" in item and "value" in item:
                            combined_data[str(item["code"])] = item["value"]
                elif isinstance(result_obj, dict):
                    if "logs" in result_obj:
                        for log_item in result_obj.get("logs", []):
                            if isinstance(log_item, dict) and "code" in log_item and "value" in log_item:
                                combined_data[str(log_item["code"])] = log_item["value"]
                    
                    for sub_key in ["properties", "status", "functions"]:
                        sub_list = result_obj.get(sub_key, [])
                        if isinstance(sub_list, list):
                            for item in sub_list:
                                if isinstance(item, dict) and "code" in item and "value" in item:
                                    combined_data[str(item["code"])] = item["value"]
        except Exception:
            pass
            
    return combined_data

try:
    token = get_tuya_token()
    data = get_weather_station_data(token)
    print("Sikeres lekérés! Egyesített Tuya adatbázis:\n", data)
    
    temp_f, humidity, wind_mph, gust_mph, wind_dir, baro_in, rain_in = 0, 0, 0, 0, 0, 30.0, 0
    
    # --- 4. A BASE64 IDŐJÁRÁS-TÖMB DEKÓDOLÁSA ---
    encoded_stream = data.get("outdoor_alert_display")
    
    if encoded_stream:
        raw_bytes = base64.b64decode(encoded_stream)
        print(f"Dekódolt bájtok: {list(raw_bytes)}")
        
        if len(raw_bytes) >= 15:
            # Külső hőmérséklet (3-4. bájt)
            raw_temp = int.from_bytes(raw_bytes[3:5], byteorder='big', signed=True)
            temp_c = raw_temp / 10.0
            temp_f = (temp_c * 9/5) + 32
            
            # Külső páratartalom (5. bájt)
            if len(raw_bytes) > 5:
                humidity = int(raw_bytes[5])
            
            # Szélsebesség (6-7. bájt)
            raw_wind = int.from_bytes(raw_bytes[6:8], byteorder='big')
            wind_kmh = raw_wind / 10.0
            wind_mph = wind_kmh * 0.621371
            
            # Széllökés (8-9. bájt)
            raw_gust = int.from_bytes(raw_bytes[8:10], byteorder='big')
            gust_kmh = raw_gust / 10.0
            gust_mph = gust_kmh * 0.621371
            
            # Szélirány (10-11. bájt)
            wind_dir = int.from_bytes(raw_bytes[10:12], byteorder='big')
            
            # Légnyomás (12-13. bájt)
            raw_baro = int.from_bytes(raw_bytes[12:14], byteorder='big')
            baro_hpa = raw_baro / 10.0 if raw_baro > 5000 else raw_baro
            if baro_hpa < 500: baro_hpa = 1013.2
            baro_in = baro_hpa * 0.02953
            
            # Csapadék (14-15. bájt)
            if len(raw_bytes) >= 16:
                raw_rain = int.from_bytes(raw_bytes[14:16], byteorder='big')
                rain_mm = raw_rain / 10.0
                rain_in = rain_mm * 0.0393701

            print(f"Szenzorértékek -> Temp: {round(temp_c,1)}C, Pára: {humidity}%, Szél: {round(wind_kmh,1)}km/h, Irány: {wind_dir}fok, Nyomás: {round(baro_hpa,1)}hPa")
    else:
        print("Nem található 'outdoor_alert_display', alapértelmezett értékeket használunk.")
        raw_baro = data.get("pressure", data.get("pressure_current", 10132))
        baro_hpa = raw_baro / 10.0 if raw_baro > 5000 else raw_baro
        baro_in = baro_hpa * 0.02953

    # 2. JÓ CÍM: A Weather Underground hivatalos, hosszú, működő HTTPS címe
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
    print(f"WU Válaszkód: {wu_response.status_code} - Üzenet: {wu_response.text}")

except Exception as e:
    print("Hiba történt a futtatás során:", e)
    exit(1)
