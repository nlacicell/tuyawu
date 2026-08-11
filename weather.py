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

# --- 3. TUYA ADATOK LEKÉRÉSE (TÖBB VÉGPONT PRÓBÁLÁSA) ---
def get_weather_station_data(token):
    t = str(int(time.time() * 1000))
    combined_data = {}

    # 1. Megpróbáljuk a Shadow (eszköz reális állapota) végpontot, 2. A Properties-t, 3. A Status-t
    endpoints = [
        f"/v2.0/cloud/thing/{DEVICE_ID}/shadow",
        f"/v1.0/devices/{DEVICE_ID}/properties",
        f"/v1.0/devices/{DEVICE_ID}/status"
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
                print(f"Sikeres válasz a végpontról [{path}]:", res_json)
                
                result_obj = res_json.get("result", {})
                
                # Ha Shadow struktúrát kapunk vissza (v2.0 API)
                if isinstance(result_obj, dict) and "properties" in result_obj:
                    props = result_obj.get("properties", [])
                    if isinstance(props, list):
                        for item in props:
                            if isinstance(item, dict) and "code" in item and "value" in item:
                                combined_data[str(item["code"])] = item["value"]
                                
                # Ha sima tömböt kapunk (v1.0 status/properties)
                elif isinstance(result_obj, list):
                    for item in result_obj:
                        if isinstance(item, dict) and "code" in item and "value" in item:
                            combined_data[str(item["code"])] = item["value"]
                            
                # Ha más szótár struktúrát kapunk
                elif isinstance(result_obj, dict):
                    for sub_key in ["properties", "status"]:
                        sub_list = result_obj.get(sub_key, [])
                        if isinstance(sub_list, list):
                            for item in sub_list:
                                if isinstance(item, dict) and "code" in item and "value" in item:
                                    combined_data[str(item["code"])] = item["value"]
        except Exception as e:
            print(f"Hiba a végpontnál [{path}]:", e)

    return combined_data

    # --- 4. ADATOK FELDOLGOZÁSA (SZABVÁNYOS TUYA KÓDOKRA JAVÍTVA) ---
    
    # 1. Hőmérséklet (va_temperature, temp_outdoor vagy outdoor_temp)
    temp_c = data.get("va_temperature", data.get("temp_outdoor", data.get("outdoor_temp", 0)))
    try:
        temp_c = float(temp_c)
        # Ha a Tuya tizedesjegy nélkül küldi (pl. 235 a 23.5 helyett)
        if temp_c > 80 or temp_c < -40:
            temp_c = temp_c / 10.0
    except (ValueError, TypeError):
        temp_c = 0.0
    temp_f = (temp_c * 9/5) + 32
    
    # 2. Külső páratartalom (humidity, va_humidity vagy humidity_outdoor)
    humidity = data.get("humidity", data.get("va_humidity", data.get("humidity_outdoor", 0)))
    try:
        humidity = int(float(humidity))
    except (ValueError, TypeError):
        humidity = 0

    # 3. Szélsebesség (wind_speed vagy va_wind_speed)
    wind_kmh = data.get("wind_speed", data.get("va_wind_speed", 0))
    try:
        # Ha a Tuya itt is 10-es szorzót használ (pl. 15 km/h-t 150-nek küld)
        wind_kmh = float(wind_kmh)
        if wind_kmh > 200: 
            wind_kmh = wind_kmh / 10.0
        wind_mph = wind_kmh * 0.621371
    except (ValueError, TypeError):
        wind_mph = 0.0

    # 4. Széllökés (wind_gust vagy va_gust)
    gust_kmh = data.get("wind_gust", data.get("va_gust", 0))
    try:
        gust_kmh = float(gust_kmh)
        if gust_kmh > 200:
            gust_kmh = gust_kmh / 10.0
        gust_mph = gust_kmh * 0.621371
    except (ValueError, TypeError):
        gust_mph = 0.0

    # 5. Szélirány (va_direction vagy wind_direction)
    wind_dir = data.get("va_direction", data.get("wind_direction", 0))
    try:
        wind_dir = int(float(wind_dir))
    except (ValueError, TypeError):
        wind_dir = 0

    # 6. Légnyomás (pressure_current vagy atmosphere)
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

    # 7. Csapadék (rain_24h, rainfall vagy va_rain)
    rain_mm = data.get("rain_24h", data.get("rainfall", data.get("va_rain", 0)))
    try:
        rain_mm = float(rain_mm)
        if rain_mm > 500:
            rain_mm = rain_mm / 10.0
        rain_in = rain_mm * 0.0393701
    except (ValueError, TypeError):
        rain_in = 0.0

    print(f"Feldolgozott értékek -> Temp: {round(temp_c,1)}°C, Pára: {humidity}%, Szél: {round(wind_mph,1)} mph, Irány: {wind_dir}°, Nyomás: {round(baro_in,2)} inHg")

    # --- 5. ADATFELTÖLTÉS A WEATHER UNDERGROUND-RA ---
    # JAVÍTÁS: A bázis URL-nek a valós feltöltési végpontot kell megadni!
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
    print(f"WU Válaszkód: {wu_response.status_code} - Üzenet: {wu_response.text}")
    
    if "success" in wu_response.text.lower():
        print("Az adatfeltöltés sikeresen befejeződött!")
    else:
        print("Figyelem: A WU szervere válaszolt, de nem igazolta vissza a sikeres mentést.")

except Exception as e:
    print("Hiba történt a futtatás során:", e)
    exit(1)

except Exception as e:
    print("Hiba történt a futtatás során:", e)
    exit(1)
