import os
import requests
import tinytuya

# --- 1. PROJEKT ÉS ESZKÖZ ADATOK (GITHUB SECRETS) ---
ACCESS_ID = os.environ.get("TUYA_ACCESS_ID")
ACCESS_SECRET = os.environ.get("TUYA_ACCESS_SECRET")
DEVICE_ID = os.environ.get("TUYA_DEVICE_ID")

WU_STATION_ID = os.environ.get("WU_STATION_ID")
WU_STATION_KEY = os.environ.get("WU_STATION_KEY")

def get_vevor_data():
    # Csatlakozás a Tuya Cloudhoz az európai (eu) régióban tinytuya-val
    cloud = tinytuya.Cloud(
        apiRegion="eu",
        apiKey=ACCESS_ID,
        apiSecret=ACCESS_SECRET,
        nodeId=DEVICE_ID
    )

    data = {}

    # 1. Lépés: Fiókhoz tartozó eszközök lekérdezése (fiók szintű DP adatok)
    try:
        devices = cloud.getdevices()
        print("\n--- Fiókhoz tartozó eszközök lekérdezése ---")
        if isinstance(devices, list):
            for dev in devices:
                if dev.get("id") == DEVICE_ID or dev.get("node_id") == DEVICE_ID:
                    print(f"Eszköz megtalálva: {dev.get('name')}")
                    if "dps" in dev and isinstance(dev["dps"], dict):
                        data.update(dev["dps"])
                    if "status" in dev and isinstance(dev["status"], list):
                        for item in dev["status"]:
                            if isinstance(item, dict) and "code" in item and "value" in item:
                                data[str(item["code"])] = item["value"]
    except Exception as e:
        print(f"Hiba a getdevices() során: {e}")

    # 2. Lépés: Közvetlen eszköz státusz lekérése
    try:
        status = cloud.getstatus(DEVICE_ID)
        print("\n--- Közvetlen eszköz státusz (getstatus) ---")
        print(status)
        if isinstance(status, dict) and status.get("success"):
            result = status.get("result", [])
            if isinstance(result, list):
                for item in result:
                    if isinstance(item, dict) and "code" in item and "value" in item:
                        data[str(item["code"])] = item["value"]
            elif isinstance(result, dict) and "dps" in result:
                data.update(result["dps"])
    except Exception as e:
        print(f"Hiba a getstatus() során: {e}")

    # 3. Lépés: Tulajdonságok lekérése (Properties)
    try:
        props = cloud.getproperties(DEVICE_ID)
        print("\n--- Eszköz tulajdonságok (getproperties) ---")
        print(props)
        if isinstance(props, dict) and props.get("success"):
            result = props.get("result", {})
            if isinstance(result, dict):
                properties = result.get("properties", [])
                for p in properties:
                    if isinstance(p, dict) and "code" in p and "value" in p:
                        data[str(p["code"])] = p["value"]
    except Exception as e:
        print(f"Hiba a getproperties() során: {e}")

    return data

# --- FŐ PROGRAMFUTTATÁS ---
try:
    data = get_vevor_data()
    print("\nÖsszegyűjtött szenzor adatok:", data)

    if not data:
        print("Nem sikerült adatokat lekérni a Tuya Cloud-ból.")
        exit(1)

    # --- ADATOK FELDOLGOZÁSA ÉS ÁTALAKÍTÁSA ---
    # Hőmérséklet (°C -> °F)
    temp_c = data.get("va_temperature", data.get("temp_outdoor", data.get("outdoor_temp", data.get("101", 0))))
    try:
        temp_c = float(temp_c) if temp_c is not None else 0.0
        if temp_c > 80 or temp_c < -40:
            temp_c = temp_c / 10.0
    except (ValueError, TypeError):
        temp_c = 0.0
    temp_f = (temp_c * 9/5) + 32

    # Páratartalom (%)
    humidity = data.get("humidity", data.get("va_humidity", data.get("humidity_outdoor", data.get("102", 0))))
    try:
        humidity = int(float(humidity)) if humidity is not None else 0
    except (ValueError, TypeError):
        humidity = 0

    # Szélsebesség (km/h -> mph)
    wind_kmh = data.get("wind_speed", data.get("va_wind_speed", data.get("103", 0)))
    try:
        wind_kmh = float(wind_kmh) if wind_kmh is not None else 0.0
        if wind_kmh > 200:
            wind_kmh = wind_kmh / 10.0
        wind_mph = wind_kmh * 0.621371
    except (ValueError, TypeError):
        wind_mph = 0.0

    # Széllökés (km/h -> mph)
    gust_kmh = data.get("wind_gust", data.get("va_gust", data.get("104", 0)))
    try:
        gust_kmh = float(gust_kmh) if gust_kmh is not None else 0.0
        if gust_kmh > 200:
            gust_kmh = gust_kmh / 10.0
        gust_mph = gust_kmh * 0.621371
    except (ValueError, TypeError):
        gust_mph = 0.0

    # Szélirány (fok 0-360)
    wind_dir = data.get("va_direction", data.get("wind_direction", data.get("105", 0)))
    try:
        wind_dir = int(float(wind_dir)) if wind_dir is not None else 0
    except (ValueError, TypeError):
        wind_dir = 0

    # Légnyomás (hPa -> inHg)
    baro_hpa = data.get("pressure_current", data.get("atmosphere", data.get("indoor_pressure", data.get("106", 1013.2))))
    try:
        baro_hpa = float(baro_hpa) if baro_hpa is not None else 1013.2
        if baro_hpa > 5000:
            baro_hpa = baro_hpa / 100.0
        elif baro_hpa > 2000:
            baro_hpa = baro_hpa / 10.0
    except (ValueError, TypeError):
        baro_hpa = 1013.2
    baro_in = baro_hpa * 0.02953

    # Csapadék (mm -> hüvelyk)
    rain_mm = data.get("rain_24h", data.get("rainfall", data.get("va_rain", data.get("107", 0))))
    try:
        rain_mm = float(rain_mm) if rain_mm is not None else 0.0
        if rain_mm > 500:
            rain_mm = rain_mm / 10.0
        rain_in = rain_mm * 0.0393701
    except (ValueError, TypeError):
        rain_in = 0.0

    print(f"\nKiszámított értékek:")
    print(f"Hőmérséklet: {round(temp_c, 1)}°C ({round(temp_f, 1)}°F)")
    print(f"Páratartalom: {humidity}%")
    print(f"Szélsebesség: {round(wind_kmh, 1)} km/h ({round(wind_mph, 1)} mph)")
    print(f"Szélirány: {wind_dir}°")
    print(f"Légnyomás: {round(baro_hpa, 1)} hPa ({round(baro_in, 2)} inHg)")
    print(f"Csapadék: {round(rain_mm, 1)} mm ({round(rain_in, 2)} in)")

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
        "softwaretype": "VevorYT60311Gateway",
        "action": "updateraw"
    }
    
    wu_response = requests.get(wu_url, params=params)
    print(f"\nWU Válaszkód: {wu_response.status_code} - Üzenet: {wu_response.text}")

except Exception as e:
    print("Hiba történt a futtatás során:", e)
    exit(1)
