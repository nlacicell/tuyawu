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
    """Lekéri az adatokat a Tuya Cloud API státuszából a cloud.get() segítségével."""
    print("Kapcsolódás a Tuya Cloud API-hoz tinytuya-val...")
    
    cloud = tinytuya.Cloud(
        apiRegion="eu",
        apiKey=TUYA_ACCESS_ID,
        apiSecret=TUYA_ACCESS_SECRET
    )
    
    data = {}
    
    # 1. Alap getstatus
    try:
        response = cloud.getstatus(TUYA_DEVICE_ID)
        print(f"Alap getstatus válasz: {response}")
        if isinstance(response, dict):
            res = response.get("result", [])
            if isinstance(res, list):
                for item in res:
                    if isinstance(item, dict):
                        code = item.get("code")
                        value = item.get("value")
                        if code:
                            data[code] = value
    except Exception as e:
        print(f"Hiba a getstatus lekérdezésekor: {e}")

    # 2. Részletes felhő státusz lekérdezése a helyes cloud.get() metódussal
    try:
        endpoint = f"/v1.0/iot-03/devices/{TUYA_DEVICE_ID}/status"
        log_response = cloud.get(endpoint)
        print(f"Felhő státusz válasz (cloud.get): {log_response}")
        
        if isinstance(log_response, dict) and "result" in log_response:
            res = log_response.get("result", [])
            if isinstance(res, list):
                for item in res:
                    if isinstance(item, dict):
                        code = item.get("code")
                        value = item.get("value")
                        if code:
                            data[code] = value
    except Exception as e:
        print(f"Nem sikerült lekérni a felhő státuszt: {e}")

    return data

def parse_sensor_data(raw_data):
    """Feldolgozza és a Weather Underground által elvárt formátumra alakítja az adatokat."""
    print(f"Összes gyűjtött kulcs-érték: {raw_data}")
    
    temp_raw = (
        raw_data.get("va_temperature") or 
        raw_data.get("temp_current") or 
        raw_data.get("temperature") or 
        raw_data.get("solar_temperature") or 
        raw_data.get("outdoor_temp") or 
        raw_data.get("temp") or 0
    )
    
    humidity = (
        raw_data.get("humidity") or 
        raw_data.get("va_humidity") or 
        raw_data.get("outdoor_humidity") or 
        raw_data.get("hum") or 50
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
        'software': 'PythonTinyTuyaCloudLogScript 2.1'
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
