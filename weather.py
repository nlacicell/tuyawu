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
    """Lekéri az adatokat a Tuya Cloud-ból, megvizsgálva az összes lehetséges státuszforrást."""
    print("Kapcsolódás a Tuya Cloud API-hoz tinytuya-val...")
    
    cloud = tinytuya.Cloud(
        apiRegion="eu",
        apiKey=TUYA_ACCESS_ID,
        apiSecret=TUYA_ACCESS_SECRET
    )
    
    # 1. Próbálkozás: standard getstatus
    response = cloud.getstatus(TUYA_DEVICE_ID)
    print(f"Teljes getstatus válasz: {response}")
    
    data = {}
    
    # Ha a válasz direkt tartalmazza a kulcsokat vagy a result listát
    status_list = []
    if isinstance(response, dict):
        if "result" in response:
            res = response.get("result")
            if isinstance(res, list):
                status_list = res
            elif isinstance(res, dict):
                # Ha dict, alakítsuk listává
                status_list = [{"code": k, "value": v} for k, v in res.items()]
        elif "status" in response:
            status_list = response.get("status", [])
        else:
            status_list = [{"code": k, "value": v} for k, v in response.items() if k not in ["success", "tid"]]

    for item in status_list:
        if isinstance(item, dict):
            code = item.get("code")
            value = item.get("value")
            if code:
                data[code] = value
                
    # 2. Ha a fenti adatokból hiányoznak a szenzorok, próbáljuk meg lekérni az eszközspecifikus leírást/tulajdonságokat is
    try:
        properties = cloud.getproperties(TUYA_DEVICE_ID)
        print(f"Eszköz tulajdonságok (properties): {properties}")
        if isinstance(properties, dict) and "result" in properties:
            prop_list = properties.get("result", [])
            for p in prop_list:
                code = p.get("code") or p.get("dp_id")
                value = p.get("value") or p.get("status")
                if code and value is not None and code not in data:
                    data[code] = value
    except Exception as e:
        print(f"Nem sikerült lekérni a tulajdonságokat: {e}")

    return data

def parse_sensor_data(raw_data):
    """Feldolgozza és a Weather Underground által elvárt formátumra alakítja az adatokat."""
    print(raw_data)
    # Részletesebb keresés a lehetséges Tuya szenzor kódokra (Vevor / Tuya weather station specifikus)
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
        'software': 'PythonTinyTuyaWeatherScript 1.1'
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
        print(f"Kigyűjtött nyers adatok: {raw_data}")
        
        weather_payload = parse_sensor_data(raw_data)
        print(f"Feldolgozott adatok: {weather_payload}")
        
        upload_to_wunderground(weather_payload)
        print("Sikeres futtatás!")
    except Exception as e:
        print(f"Hiba történt a szkript futtatása során: {e}")
        exit(1)
