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

# --- 3. ADATLEKÉRÉS A TUYA-BÓL ---
def get_tuya_status(token):
    t = str(int(time.time() * 1000))
    url_path = f"/v1.0/devices/{DEVICE_ID}/specifications"
    string_to_sign = f"{ACCESS_ID}{token}{t}GET\n{hashlib.sha256(b'').hexdigest()}\n\n{url_path}"
    sign = hmac.new(ACCESS_SECRET.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest().upper()
    
    headers = {
        "client_id": ACCESS_ID,
        "access_token": token,
        "sign": sign,
        "t": t,
        "sign_method": "HMAC-SHA256"
    }
    
    res = requests.get(f"{BASE_URL}{url_path}", headers={"client_id": ACCESS_ID, "access_token": token, "sign": sign, "t": t, "sign_method": "HMAC-SHA256"})
    if res.status_code == 200 and res.json().get("success"):
        return res.json()["result"]
    raise Exception(f"Státusz hiba: {res.text}")

try:
    token = get_tuya_token()
    status_list = get_tuya_status(token)
    
    data = {item["code"]: item["value"] for item in status_list}
    print("Sikeres lekérés! Nyers Tuya adatok:\n", data)
    
    # Alapértelmezett értékek biztonsági mentésként
    temp_f, humidity, wind_mph, gust_mph, wind_dir, baro_in, rain_in = 0, 0, 0, 0, 0, 30.0, 0
    
    # --- 4. A SPECIÁLIS BASE64 IDŐJÁRÁS-TÖMB DEKÓDOLÁSA ---
    encoded_stream = data.get("outdoor_alert_display")
    
    if encoded_stream:
        # Dekódoljuk a szöveget nyers bájtokká
        raw_bytes = base64.b64decode(encoded_stream)
        print(f"Dekódolt bájtok hossza: {len(raw_bytes)} bytes. Nyers bájtok: {list(raw_bytes)}")
        
        # A Vevor / Tuya PWS szabványos bájthelyeinek (offset) feldolgozása
        if len(raw_bytes) >= 15:
            # Külső hőmérséklet (2 bájtos előjeles egész a 3-4. bájton)
            raw_temp = int.from_bytes(raw_bytes[3:5], byteorder='big', signed=True)
            temp_c = raw_temp / 10.0
            temp_f = (temp_c * 9/5) + 32
            
            # Külső páratartalom (1 bájt az 5. bájton)
            humidity = raw_bytes[5]
            
            # Szélsebesség (2 bájt a 6-7. bájton, km/h * 10)
            raw_wind = int.from_bytes(raw_bytes[6:8], byteorder='big')
            wind_kmh = raw_wind / 10.0
            wind_mph = wind_kmh * 0.621371
            
            # Széllökés (2 bájt a 8-9. bájton, km/h * 10)
            raw_gust = int.from_bytes(raw_bytes[8:10], byteorder='big')
            gust_kmh = raw_gust / 10.0
            gust_mph = gust_kmh * 0.621371
            
            # Szélirány fokban (2 bájt a 10-11. bájton)
            wind_dir = int.from_bytes(raw_bytes[10:12], byteorder='big')
            
            # Légnyomás (2 bájt a 12-13. bájton, hPa * 10)
            raw_baro = int.from_bytes(raw_bytes[12:14], byteorder='big')
            baro_hpa = raw_baro / 10.0 if raw_baro > 5000 else raw_baro
            if baro_hpa < 500: baro_hpa = 1013.2 # Biztonsági alapértelmezés ha üres
            baro_in = baro_hpa * 0.02953
            
            # Csapadék (2 bájt a 14-15. bájton, mm * 10)
            if len(raw_bytes) >= 16:
                raw_rain = int.from_bytes(raw_bytes[14:16], byteorder='big')
                rain_mm = raw_rain / 10.0
                rain_in = rain_mm * 0.0393701

            print(f"Kicsomagolt adatok -> Temp: {round(temp_c,1)}C, Pára: {humidity}%, Szél: {round(wind_kmh,1)}km/h, Irány: {wind_dir}fok, Nyomás: {round(baro_hpa,1)}hPa")
    else:
        print("FIGYELEM: Nem található 'outdoor_alert_display' adatpont a Tuya válaszában!")
        # Ha nincs tömb, megpróbáljuk a meglévő alap nyers adatokból kiszedni a légnyomást
        raw_baro = data.get("pressure", data.get("pressure_current", 10132))
        baro_hpa = raw_baro / 10.0 if raw_baro > 5000 else raw_baro
        baro_in = baro_hpa * 0.02953

    # --- 5. FELTÖLTÉS WEATHER UNDERGROUND-RA ---
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
        "action": "updateraw"
    }
    
    wu_response = requests.get(wu_url, params=params)
    print(f"\nWU Válaszkód: {wu_response.status_code} - Üzenet: {wu_response.text}")

except Exception as e:
    print("Hiba történt a futtatás során:", e)
    exit(1)
