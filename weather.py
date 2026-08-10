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

# A hivatalos európai Tuya OpenAPI szervercím
BASE_URL = "https://openapi.tuyaeu.com"

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

# --- 3. TUYA ADATOK LEKÉRÉSE ---
def get_weather_station_data(token):
    t = str(int(time.time() * 1000))
    
    # Időbélyegek a log lekéréshez (elmúlt 10 perc adatait nézzük vissza)
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (10 * 60 * 1000)
    
    combined_data = {}

    # Az utolsó végpont tartalmazza a konkrét időbélyeges log lekérést
    endpoints = [
        f"/v1.0/devices/{DEVICE_ID}/status",
        f"/v1.0/devices/{DEVICE_ID}/specifications",
        f"/v1.0/devices/{DEVICE_ID}/logs?start_time={start_ms}&end_time={now_ms}&size=50"
    ]

    for path in endpoints:
        try:
            # Tuya v1 aláírás generálása
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
                
                # Ha listát kapunk vissza (status végpont)
                if isinstance(result_obj, list):
                    for item in result_obj:
                        if isinstance(item, dict) and "code" in item and "value" in item:
                            combined_data[str(item["code"])] = item["value"]
                # Ha szótárat kapunk vissza (logs vagy specifications végpont)
                elif isinstance(result_obj, dict):
                    if "logs" in result_obj:
                        for log_item in result_obj.get("logs", []):
                            if isinstance(log_item, dict) and "code" in log_item and "value" in log_item:
                                # A legfrissebb log érték felülírja a régit
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
    
    # --- 4. ADATOK FELDOLGOZÁSA ---
    
    # Külső hőmérséklet (Ha a logban outdoor_temp vagy va_temperature van)
    temp_c = data.get("outdoor_temp", data.get("temp_outdoor", data.get("va_temperature", 0)))
    try:
        temp_c = float(temp_c)
        if temp_c > 80 or temp_c < -40:
            temp_c = temp_c / 10.0
    except (ValueError, TypeError):
        temp_c = 0.0
    temp_f = (temp_c * 9/5) + 32
    
    # Külső páratartalom
    humidity = data.get("outdoor humidity", data.get("humidity_outdoor", 0))
    try:
        humidity = int(float(humidity))
    except (ValueError, TypeError):
        humidity = 0

    # Szélsebesség (km/h -> mph)
    wind_kmh = data.get("wind_speed", 0)
    try:
        wind_mph = float(wind_kmh) * 0.621371
    except (ValueError, TypeError):
        wind_mph = 0.0

    # Széllökés (km/h -> mph)
    gust_kmh = data.get("Wind Gust", 0)
    try:
        gust_mph = float(gust_kmh) * 0.621371
    except (ValueError, TypeError):
        gust_mph = 0.0

    # Szélirány (0-360 fok)
    wind_dir = data.get("wind_dir", data.get("Wind Direction", data.get("va_direction", 0)))
    try:
        wind_dir = int(float(wind_dir))
    except (ValueError, TypeError):
        wind_dir = 0

    # Légnyomás (hPa -> inHg)
    baro_hpa = data.get("indoor_pressure", data.get("pressure_current", 1013.2))
    try:
        baro_hpa = float(baro_hpa)
        if baro_hpa > 5000:
            baro_hpa = baro_hpa / 100.0
        elif baro_hpa > 2000:
            baro_hpa = baro_hpa / 10.0
    except (ValueError, TypeError):
        baro_hpa = 1013.2
    baro_in = baro_hpa * 0.02953

    # Csapadék (mm -> inch)
    rain_mm = data.get("rainfall", 0)
    try:
        rain_in = float(rain_mm) * 0.0393701
    except (ValueError, TypeError):
        rain_in = 0.0

    print(f"Feldolgozott értékek -> Temp: {round(temp_c,1)}°C ({round(temp_f,1)}°F), Pára: {humidity}%, Szél: {round(wind_mph,1)} mph, Nyomás: {round(baro_in,2)} inHg")

    # --- 5. ADATFELTÖLTÉS A WEATHER UNDERGROUND-RA ---
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
        "softwaretype": "TuyaWeatherGateway",
        "action": "updateraw"
    }
    
    wu_response = requests.get(wu_url, params=params)
    print(f"WU Válaszkód: {wu_response.status_code} - Üzenet: {wu_response.text}")
    
    if "success" in wu_response.text.lower():
        print("Az adatfeltöltés sikeresen befejeződött!")
    else:
        print("Figyelem: A WU szervere válaszolt, de nem igazolta vissza a sikeres mentést.")

except Exception as e:
    print("Hiba történt a futtatás során:", e)
    exit(1)
