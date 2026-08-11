import os
import requests
import tinytuya

# Környezeti változók beolvasása (GitHub Secrets-ből)
TUYA_ACCESS_ID = os.environ.get("TUYA_ACCESS_ID")
TUYA_ACCESS_SECRET = os.environ.get("TUYA_ACCESS_SECRET")
TUYA_DEVICE_ID = os.environ.get("TUYA_DEVICE_ID")
WU_STATION_ID = os.environ.get("WU_STATION_ID")
WU_STATION_KEY = os.environ.get("WU_STATION_KEY")

def get_tuya_weather_data():
    """Lekéri az adatokat a Tuya Cloud eszközlistájából (getdevices)."""
    print("Kapcsolódás a Tuya Cloud API-hoz tinytuya-val...")
    
    cloud = tinytuya.Cloud(
        apiRegion="eu",
        apiKey=TUYA_ACCESS_ID,
        apiSecret=TUYA_ACCESS_SECRET
    )
    
    data = {}
    
    try:
        # Helyes metódusnév: getdevices() aláhúzás nélkül
        devices = cloud.getdevices()
        print(f"Lekért eszközök száma: {len(devices) if isinstance(devices, list) else 'Nem lista'}")
        
        if isinstance(devices, list):
            for dev in devices:
                if isinstance(dev, dict) and dev.get("id") == TUYA_DEVICE_ID:
                    print(f"Megtalált céleszköz a listában: {dev.get('name')}")
                    dev_status = dev.get("status", [])
                    print(f"Eszköz státusz tömb a getdevices()-ből: {dev_status}")
                    
                    if isinstance(dev_status, list):
                        for item in dev_status:
                            if isinstance(item, dict):
                                code = item.get("code")
                                value = item.get("value")
                                if code:
                                    data[code] = value
                    elif isinstance(dev_status, dict):
                        for k, v in dev_status.items():
                            data[k] = v
    except Exception as e:
        print(f"Hiba a getdevices() lekérdezésekor: {e}")

    return data

def parse_sensor_data(raw_data):
    """Feldolgozza és a Weather Underground által elvárt formátumra alakítja az adatokat."""
    print(f"Összes gyűjtött kulcs-érték: {raw_data}")
    
    temp_raw = (
        raw_data.get("va_temperature") or 
        raw_data.get("temp_current") or 
        raw_data.get("temperature") or 
        raw_data.get("solar_temperature") or 
        raw_data.get("outdoor_temp") or 0
    )
    
    humidity = (
        raw_data.get("humidity") or 
        raw_data.get("va_humidity") or 
        raw_data.get("outdoor_humidity") or 50
    )
    
    pressure_raw = (
        raw_data.get("pressure") or 
        raw_data.get("va_pressure") or 
        raw_data.get("barometer") or 101325
    )
    
    try:
        temp_raw = float(temp_raw)
    except:
        temp_raw = 0.0

    try:
        humidity = int(humidity)
    except:
        humidity = 50

    # Hőmérséklet skálázás kezelése
    temperature_c = temp_raw / 10.0 if temp_raw > 100 else temp_raw
    temperature_f = (temperature_c * 9/5) + 32
    
    # Légnyomás konverzió hPa-ról inHg-re
    pressure_hpa = pressure_raw / 100.0 if pressure_raw > 2000 else pressure_raw
    pressure_inhg = pressure_hpa * 0.02953
    
    parsed = {
        'tempf': f"{temperature_f:.1f}",
        'humidity': humidity,
        'barom': f"{pressure_inhg:.2f}",
        'software': 'PythonTinyTuyaWeatherScript 1.7'
    }
    return parsed

def upload_to_wunderground(weather_data):
    """Feltölti az adatokat a Weather Underground platformra."""
    url = "https://weatherstation.wunderground.com/weatherstation/updateweatherstation.php"
    
    params = {
        'ID': WU_STATION_ID,
        'PASSWORD': WU_STATION_KEY,
        'dateutc': 'now',
        'action': 'updaterupdate'
    }
    params.update(weather_data)
    
    print("Feltöltés a Weather Undergroundra...")
    response = requests.get(url, params=params)
    print(f"WU válasz: {response.status_code} - {response.text}")

if __name__ == "__main__":
    try:
        raw_data = get_tuya_weather_data()
        weather_payload = parse_sensor_data(raw_data)
        print(f"Feldolgozott adatok: {weather_payload}")
        
        upload_to_wunderground(weather_payload)
        print("Sikeres futtatás!")
    except Exception as e:
        print(f"Hiba történt a szkript futtatása során: {e}")
        exit(1)
