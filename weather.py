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

# --- 3. TUYA ADATOK LEKÉRÉSE (ALESZKÖZÖK FELTÉRKÉPEZÉSÉVEL) ---
def get_weather_station_data(token):
    t = str(int(time.time() * 1000))
    combined_data = {}
    
    # Először lekérjük az összes aleszközt, ami ehhez a gateway-hez/konzolhoz tartozik
    sub_devices_path = f"/v1.0/devices/{DEVICE_ID}/sub-devices"
    string_to_sign = f"{ACCESS_ID}{token}{t}GET\n{hashlib.sha256(b'').hexdigest()}\n\n{sub_devices_path}"
    sign = hmac.new(ACCESS_SECRET.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest().upper()
    
    headers = {
        "client_id": ACCESS_ID,
        "access_token": token,
        "sign": sign,
        "t": t,
        "sign_method": "HMAC-SHA256"
    }
    
    target_ids = [DEVICE_ID] # Alapból a fő eszközt vizsgáljuk
    
    try:
        res = requests.get(f"{BASE_URL}{sub_devices_path}", headers=headers)
        if res.status_code == 200 and res.json().get("success"):
            sub_list = res.json().get("result", [])
            print(f"Talalt aleszozok listaja: {sub_list}")
            for sub in sub_list:
                if isinstance(sub, dict) and "id" in sub:
                    target_ids.append(sub["id"])
    except Exception as e:
        print(f"Nem sikerult az aleszkozok lekerdezese: {e}")

    # Végigmegyünk a fő eszközön és az összes talált aleszközön
    for current_id in target_ids:
        path = f"/v1.0/devices/{current_id}/status"
        t = str(int(time.time() * 1000))
        
        try:
            string_to_sign = f"{ACCESS_ID}{token}{t}GET\n{hashlib.sha256(b'').hexdigest()}\n\n{path}"
            sign = hmac.new(ACCESS_SECRET.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest().upper()
            
            headers["sign"] = sign
            headers["t"] = t
            
            res = requests.get(f"{BASE_URL}{path}", headers=headers)
            if res.status_code == 200 and res.json().get("success"):
                res_json = res.json()
                print(f"Sikeres valasz az eszkoztol [{current_id}]:", res_json)
                
                result_obj = res_json.get("result", [])
                if isinstance(result_obj, list):
                    for item in result_obj:
                        if isinstance(item, dict) and "code" in item and "value" in item:
                            combined_data[str(item["code"])] = item["value"]
        except Exception as e:
            print(f"Hiba a(z) {current_id} eszkoz statusz lekeresinel: {e}")

    return combined_data

# --- FŐ PROGRAMFUTTATÁS ---
try:
    token = get_tuya_token()
    data = get_weather_station_data(token)
    
    if not data:
        print("Nem erkezett adat az eszkozökbol.")
        exit(1)

    print("Egyesitett Tuya adatbazis sikeresen felepult.")

    # --- 4. ADATOK FELDOLGOZÁSA ---
    
    # 1. Hőmérséklet
    temp_c = data.get("va_temperature", data.get("temp_outdoor", data.get("outdoor_temp", 0)))
    try:
        temp_c = float(temp_c)
        if temp_c > 80 or temp_c < -40:
            temp_c = temp_c / 10.0
    except (ValueError, TypeError):
        temp_c = 0.0
    temp_f = (temp_c * 9/5) + 32
    
    # 2. Külső páratartalom
    humidity = data.get("humidity", data.get("va_humidity", data.get("humidity_outdoor", 0)))
    try:
        humidity = int(float(humidity))
    except (ValueError, TypeError):
        humidity = 0

    # 3. Szélsebesség
    wind_kmh = data.get("wind_speed", data.get("va_wind_speed", 0))
    try:
        wind_kmh = float(wind_kmh)
        if wind_kmh > 200: 
            wind_kmh = wind_kmh / 10.0
        wind_mph = wind_kmh * 0.621371
    except (ValueError, TypeError):
        wind_mph = 0.0

    # 4. Széllökés
    gust_kmh = data.get("wind_gust", data.get("va_gust", 0))
    try:
        gust_kmh = float(gust_kmh)
        if gust_kmh > 200:
            gust_kmh = gust_kmh / 10.0
        gust_mph = gust_kmh * 0.621371
    except (ValueError, TypeError):
        gust_mph = 0.0

    # 5. Szélirány
    wind_dir = data.get("va_direction", data.get("wind_direction", 0))
    try:
        wind_dir = int(float(wind_dir))
    except (ValueError, TypeError):
        wind_dir = 0

    # 6. Légnyomás
    baro_hpa = data.get("pressure_current", data.get("atmosphere", data.get("indoor_pressure", 1013.2)))
    try:
        baro_hpa = float(baro_hpa)
        if baro_hpa > 5000:
            baro_hpa = baro_hpa / 100.0
        elif baro_hpa > 2000:
            baro_hpa = baro_hpa / 10.0
    except (ValueError, TypeError):
        baro_hpa = 1013.2
    baro_in = baro_hpa * 0.02953

    # 7. Csapadék
    rain_mm = data.get("rain_24h", data.get("rainfall", data.get("va_rain", 0)))
    try:
        rain_mm = float(rain_mm)
        if rain_mm > 500:
            rain_mm = rain_mm / 10.0
        rain_in = rain_mm * 0.0393701
    except (ValueError, TypeError):
        rain_in = 0.0

    print(f"Feldolgozott ertekek -> Temp: {round(temp_c,1)}C, Para: {humidity}%, Szel: {round(wind_mph,1)} mph, Irany: {wind_dir}, Nyomas: {round(baro_in,2)} inHg")

    # --- 5. ADATFELTÖLTÉS A WEATHER UNDERGROUND-RA ---
    wu_url = "https://weatherstation.wunderground.com/weatherstation/updateweatherstation.php"
    
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
    print(f"WU Valaszkod: {wu_response.status_code} - Uzenet: {wu_response.text}")
    
    if "success" in wu_response.text.lower():
        print("Az adatfeltoltes sikeresen befejezodott!")
    else:
        print("Figyelem: A WU szervere valaszolt, de nem igazolta vissza a sikeres mentést.")

except Exception as e:
    print("Hiba tortent a futtatas soran:", e)
    exit(1)
