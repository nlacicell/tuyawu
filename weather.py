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
TUYA_LOCAL_IP = os.environ.get("TUYA_LOCAL_IP", "")       # Opcionális helyi IP
TUYA_LOCAL_KEY = os.environ.get("TUYA_LOCAL_KEY", "")     # Opcionális helyi Local Key

def get_tuya_weather_data():
    """Lekéri az adatokat a Tuya Cloud-ból vagy helyi eszközként."""
    print("Kapcsolódás a Tuya Cloud API-hoz tinytuya-val...")
    
    cloud = tinytuya.Cloud(
        apiRegion="eu",
        apiKey=TUYA_ACCESS_ID,
        apiSecret=TUYA_ACCESS_SECRET
    )
    
    data = {}
    
    # 1. Próbáljuk meg a felhőből a /functions vagy /specifications végpontot is lekérni, ha létezik
    try:
        spec = cloud.getdevice(TUYA_DEVICE_ID)
        print(f"Eszközspecifikáció (getdevice): {spec}")
    except Exception as e:
        print(f"Nem sikerült a getdevice: {e}")

    # 2. Hagyományos getstatus
    try:
        response = cloud.getstatus(TUYA_DEVICE_ID)
        print(f"Teljes getstatus válasz: {response}")
        if isinstance(response, dict):
            res = response.get("result", [])
            if isinstance(res, list):
                for item in res:
                    if isinstance(item, dict):
                        code = item.get("code")
                        value = item.get("value")
                        if code:
                            data[code] = value
            elif isinstance(res, dict):
                for k, v in res.items():
                    data[k] = v
    except Exception as e:
        print(f"Hiba a getstatus lekérdezésekor: {e}")

    # 3. Ha van helyi IP és Local Key megadva, próbáljuk meg helyben is lekérni (helyi Tuya protokoll)
    if TUYA_LOCAL_IP and TUYA_LOCAL_KEY:
        try:
            print(f"Helyi csatlakozás az eszközhöz ({TUYA_LOCAL_IP})...")
            d = tinytuya.Device(TUYA_DEVICE_ID, TUYA_LOCAL_IP, TUYA_LOCAL_KEY)
            d.set_version(3.3) # vagy 3.4
            payload = d.status()
            print(f"Helyi eszköz státusz (DPS): {payload}")
            if "dps" in payload:
                for dps_id, val in payload["dps"].items():
                    data[f"dps_{dps_id}"] = val
        except Exception as e:
            print(f"Helyi lekérdezési hiba: {e}")

    return data

def parse_sensor_data(raw_data):
    """Feldolgozza és a Weather Underground által elvárt formátumra alakítja az adatokat."""
    print(f"Összes gyűjtött kulcs-érték: {raw_data}")
    
    # Keresünk minden lehetséges kulcsot (beleértve a helyi DPS azonosítókat is, ha lennének)
    temp_raw = (
        raw_data.get("va_temperature") or 
        raw_data.get("temp_current") or 
        raw_data.get("temperature") or 
        raw_data.get("solar_temperature") or 
        raw_data.get("outdoor_temp") or 
        raw_data.get("dps_1") or 
        raw_data.get("dps_2") or 0
    )
    
    humidity = (
        raw_data.get("humidity") or 
        raw_data.get("va_humidity") or 
        raw_data.get("outdoor_humidity") or 
        raw_data.get("dps_3") or 50
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
        'software': 'PythonTinyTuyaWeatherScript 1.3'
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
