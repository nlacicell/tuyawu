import os
import time
import requests
import tinytuya

# Környezeti változók beolvasása (GitHub Secrets-ből)
TUYA_ACCESS_ID = os.environ.get("TUYA_ACCESS_ID")
TUYA_ACCESS_SECRET = os.environ.get("TUYA_ACCESS_SECRET")
TUYA_DEVICE_ID = os.environ.get("TUYA_DEVICE_ID")
WU_STATION_ID = os.environ.get("WU_STATION_ID")
WU_STATION_KEY = os.environ.get("WU_STATION_KEY")

def get_tuya_weather_data():
    """Lekéri az adatokat a Tuya Cloud OpenAPI-n keresztül a tinytuya segítségével."""
    print("Kapcsolódás a Tuya Cloud API-hoz...")
    
    # OpenCloud kliens inicializálása
    openapi = tinytuya.OpenAPI(
        apiRegion="eu",
        apiKey=TUYA_ACCESS_ID,
        apiSecret=TUYA_ACCESS_SECRET,
        device_id=TUYA_DEVICE_ID
    )
    
    # Eszköz státuszának lekérdezése
    response = openapi.get_device_status(TUYA_DEVICE_ID)
    print(f"API válasz: {response}")
    
    if not response or "result" not in response:
        raise Exception("Nem sikerült lekérni az eszköz státuszát a Tuya Cloudból.")
    
    # Státuszkódok konvertálása szótárrá
    status_list = response.get("result", [])
    data = {}
    for item in status_list:
        code = item.get("code")
        value = item.get("value")
        data[code] = value
        
    return data

def parse_sensor_data(raw_data):
    """Feldolgozza és a Weather Underground által elvárt formátumra alakítja az adatokat."""
    # Vevor / Tuya specifikus kódok leképezése
    temp_raw = raw_data.get("va_temperature") or raw_data.get("temp_current") or raw_data.get("temperature") or 0
    humidity = raw_data.get("humidity") or raw_data.get("va_humidity") or 50
    pressure_raw = raw_data.get("pressure") or raw_data.get("va_pressure") or 101325
    
    # Hőmérséklet skálázás kezelése (ha ezer- vagy tizedesjegyű egész számként érkezik)
    temperature_c = temp_raw / 10.0 if temp_raw > 100 else temp_raw
    temperature_f = (temperature_c * 9/5) + 32
    
    # Légnyomás konverzió hPa-ról inHg-re
    pressure_hpa = pressure_raw / 100.0 if pressure_raw > 2000 else pressure_raw
    pressure_inhg = pressure_hpa * 0.02953
    
    parsed = {
        'tempf': f"{temperature_f:.1f}",
        'humidity': humidity,
        'barom': f"{pressure_inhg:.2f}",
        'software': 'PythonTuyaWeatherScript 1.0'
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
    
    if response.status_code != 200 or "success" not in response.text.lower():
        print("Figyelem: A Weather Underground nem jelzett sikeres feldolgozást.")

if __name__ == "__main__":
    try:
        raw_data = get_tuya_weather_data()
        print(f"Nyers adatok: {raw_data}")
        
        weather_payload = parse_sensor_data(raw_data)
        print(f"Feldolgozott adatok: {weather_payload}")
        
        upload_to_wunderground(weather_payload)
        print("Sikeres futtatás!")
    except Exception as e:
        print(f"Hiba történt a szkript futtatása során: {e}")
        exit(1)
